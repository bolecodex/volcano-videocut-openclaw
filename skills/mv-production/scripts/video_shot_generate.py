#!/usr/bin/env python3
"""
根据分镜 JSON 调用火山方舟 Doubao Seedance 为每个镜头生成视频。
- 严格按分镜顺序**串行**生成（shot_001 → shot_002 → …），无批量/并行；
- 创建任务时设置 return_last_frame=True，通过查询任务接口获取生成视频的尾帧图像（PNG，与视频同分辨率，无水印）；
- 将返回的尾帧图像下载保存，作为下一个分镜的首帧图（first_frame）传入，保证镜头衔接。

接口说明：reference/视频生成接口文档.md（相对 Skill 根目录）
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from output_dir_utils import resolve_output_dir

load_dotenv(_SCRIPT_DIR / ".env")

# 默认接口地址与模型名称均允许通过 .env 覆盖，便于与不同环境或版本对齐
ARK_DEFAULT_URL = os.getenv(
    "VIDEO_API_URL",
    "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
)
ARK_DEFAULT_MODEL = os.getenv(
    "VIDEO_MODEL",
    "doubao-seedance-1-5-pro-251215",  # 默认使用 1.5 pro，可被 .env 覆盖
)

DEFAULT_MAX_WORKERS = 20

# Seedance 接口对 image_url.url 的要求：
# - 可以是图片 URL，或形如 data:image/<ext>;base64,<base64> 的字符串
# - <ext> 需小写，常见为 png/jpg/jpeg/webp 等
ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif", "heic", "heif"}


ASSETS_DATA: Optional[Dict[str, Any]] = None


def _is_truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def _to_image_data_url_if_local(path_or_url: str) -> str:
    """
    将本地图片路径自动转为符合 Seedance 规范的 data URL，其余情况原样返回。

    规范：data:image/<图片格式>;base64,<Base64编码>，<图片格式> 为小写。
    - 若字符串已以 http://、https:// 或 data:image/ 开头，则认为是 URL/已编码好的 data URL，直接返回。
    - 若字符串对应本地文件，则根据后缀推断图片格式并做 base64 编码。
    """
    s = path_or_url.strip()
    if not s:
        return s
    lower = s.lower()
    if lower.startswith("http://") or lower.startswith("https://") or lower.startswith("data:image/"):
        return s

    p = Path(s)
    if not p.is_file():
        # 既不是 URL 也不是本地文件，当普通字符串直接返回，交由服务端兜底/报错
        return s

    ext = (p.suffix.lstrip(".") or "").lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        # 不在白名单内仍然尝试，但统一按 ext 写入 MIME
        pass

    mime_ext = ext or "png"
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/{mime_ext};base64,{b64}"


def validate_storyboard(data: Any) -> Tuple[bool, List[str]]:
    """自检分镜结构与关键字段；返回 (ok, issues)。"""
    issues: List[str] = []
    if not isinstance(data, list):
        return False, ["storyboard JSON 必须是数组。"]
    if not data:
        issues.append("storyboard 为空数组。")
        return False, issues

    for i, shot in enumerate(data):
        if not isinstance(shot, dict):
            issues.append(f"[{i}] 分镜不是对象(dict)。")
            continue
        shot_id = shot.get("shot_id") or f"shot_{i:03d}"
        visual_prompt = shot.get("visual_prompt") or shot.get("prompt") or shot.get("video_description") or ""
        if not str(visual_prompt).strip():
            issues.append(f"[{shot_id}] 缺少 visual_prompt/prompt/video_description。")
        # 时间字段只做弱校验（不同上游可能用 duration 或 start/end）
        start = shot.get("start_time", None)
        end = shot.get("end_time", None)
        dur = shot.get("duration", None)
        try:
            if start is not None:
                float(start)
            if end is not None:
                float(end)
            if dur is not None and float(dur) <= 0:
                issues.append(f"[{shot_id}] duration <= 0。")
        except Exception:
            issues.append(f"[{shot_id}] start_time/end_time/duration 存在非数字值。")
    return (len(issues) == 0), issues


def _build_fallback_visual_prompt(shot: Dict[str, Any]) -> str:
    """
    当分镜缺少 visual_prompt 时的兜底生成（仅用于自检修复/不中断，不追求最优质量）。
    """
    parts: List[str] = []
    for k in ["style", "character", "scene", "camera", "lyric_line", "dialogue"]:
        v = shot.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        parts.append(s)
    base = " ".join(parts).strip()
    if not base:
        return ""
    return f"{base}, cinematic lighting, high quality"


def autofix_storyboard_missing_prompts(data: Any) -> Tuple[Any, bool, List[str]]:
    """
    对分镜做最小自修复：补齐缺失的 visual_prompt。
    返回：(fixed_data, changed, notes)
    """
    notes: List[str] = []
    if not isinstance(data, list):
        return data, False, ["storyboard JSON 必须是数组，无法自动修复。"]
    changed = False
    fixed: List[Any] = []
    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            fixed.append(raw)
            continue
        shot = dict(raw)
        shot_id = shot.get("shot_id") or f"shot_{i:03d}"
        visual_prompt = shot.get("visual_prompt") or shot.get("prompt") or shot.get("video_description") or ""
        if not str(visual_prompt).strip():
            fallback = _build_fallback_visual_prompt(shot)
            if fallback:
                shot["visual_prompt"] = fallback
                shot["autofixed_prompt"] = True
                changed = True
                notes.append(f"[{shot_id}] 已自动补齐 visual_prompt。")
            else:
                notes.append(f"[{shot_id}] 缺少 visual_prompt 且无足够信息自动补齐。")
        fixed.append(shot)
    return fixed, changed, notes


def call_video_api(
    api_url: str,
    api_key: str,
    shot: Dict[str, Any],
    duration_fallback: float,
    max_attempts: int = 60,
    interval: float = 5.0,
    return_last_frame: bool = True,
) -> Tuple[str, Optional[str]]:
    """创建图生视频任务并轮询直至返回 video_url；若 return_last_frame=True，同时返回尾帧图像 URL（供下一镜首帧使用）。

    文本提示词中会自动注入分镜中的画面描述与资产信息：
    - 以 visual_prompt/prompt/video_description 为基础；
    - 若存在 image_description，则追加到提示词中；
    - 若存在人物/场景/道具等资产字段，则追加一段资产摘要，帮助模型保持人物与场景一致性。
    """
    # 文本提示词由多个字段“相加”融合，而不是互斥择一：
    # - visual_prompt
    # - prompt
    # - video_description
    # 再叠加 image_description 与资产信息，最终拼成一个长 prompt。
    parts: List[str] = []

    for key in ["visual_prompt", "prompt", "video_description"]:
        v = shot.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())

    # 将分镜中的静态画面描述也合并进提示词，保证资产设定与画面细节被模型看到
    image_desc = str(shot.get("image_description") or "").strip()
    if image_desc:
        parts.append(f"静态画面描述：{image_desc}")

    # 追加资产信息摘要（人物、场景、道具等），便于模型在不同镜头间保持统一设定。
    # 优先使用 reference_assets.json 中按 id 定义的 description，其次退回到分镜里的简单 ID/名称。
    asset_bits: List[str] = []

    global ASSETS_DATA
    assets = ASSETS_DATA or {}

    # ---- 角色资产 ----
    characters_field = shot.get("characters") or shot.get("character") or shot.get("roles")
    character_ids: List[str] = []
    if isinstance(characters_field, (list, tuple)):
        character_ids = [str(c).strip() for c in characters_field if str(c).strip()]
    elif isinstance(characters_field, str) and characters_field.strip():
        character_ids = [characters_field.strip()]

    char_descs: List[str] = []
    # 约定：assets["characters"] 为 [{id,description,...}]
    for cid in character_ids:
        found_desc: Optional[str] = None
        # 新格式：characters 数组
        for item in assets.get("characters", []):
            if not isinstance(item, dict):
                continue
            if item.get("id") == cid and isinstance(item.get("description"), str):
                found_desc = item["description"].strip()
                break
        # 兼容旧格式：单个 "character" 描述映射到主角，如 character_girl
        if not found_desc and cid == "character_girl":
            desc = (assets.get("character") or {}).get("description")
            if isinstance(desc, str) and desc.strip():
                found_desc = desc.strip()
        if found_desc:
            char_descs.append(f"{cid}: {found_desc}")
        else:
            char_descs.append(cid)
    if char_descs:
        asset_bits.append("角色设定：" + "； ".join(char_descs))

    # ---- 场景资产 ----
    scene_id = None
    scene_field = shot.get("scene") or shot.get("location")
    if isinstance(scene_field, str) and scene_field.strip():
        scene_id = scene_field.strip()

    if scene_id:
        scene_desc = None
        for s in assets.get("scenes", []):
            if not isinstance(s, dict):
                continue
            if s.get("id") == scene_id and isinstance(s.get("description"), str):
                scene_desc = s["description"].strip()
                break
        if scene_desc:
            asset_bits.append(f"场景设定：{scene_id}: {scene_desc}")
        else:
            asset_bits.append(f"场景设定：{scene_id}")

    # ---- 道具资产 ----
    props_field = shot.get("props") or shot.get("objects")
    prop_ids: List[str] = []
    if isinstance(props_field, (list, tuple)):
        prop_ids = [str(p).strip() for p in props_field if str(p).strip()]
    elif isinstance(props_field, str) and props_field.strip():
        prop_ids = [props_field.strip()]

    prop_descs: List[str] = []
    for pid in prop_ids:
        found_desc = None
        for p in assets.get("props", []):
            if not isinstance(p, dict):
                continue
            if p.get("id") == pid and isinstance(p.get("description"), str):
                found_desc = p["description"].strip()
                break
        if found_desc:
            prop_descs.append(f"{pid}: {found_desc}")
        else:
            prop_descs.append(pid)
    if prop_descs:
        asset_bits.append("道具设定：" + "； ".join(prop_descs))

    if asset_bits:
        parts.append("资产设定（供模型保持一致性）： " + "； ".join(asset_bits))

    if not parts:
        raise ValueError("分镜对象缺少可用的文本提示字段（visual_prompt/prompt/video_description/image_description/资产信息）。")

    visual_prompt = " ".join(p for p in parts if p)

    start = shot.get("start_time", 0.0)
    end = shot.get("end_time", 0.0)
    duration = shot.get("duration", max(0.5, float(end) - float(start) or duration_fallback))
    # Seedance 参考图模式（i2v）通常要求 duration 在 [4, 12]（见 reference/视频生成接口文档.md）
    # 为避免短镜头（如 2.6s）直接 400，这里做兜底裁剪。
    try:
        duration = float(duration)
    except Exception:
        duration = float(duration_fallback)
    duration = max(4.0, min(12.0, duration))

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 构造 content：支持首帧 / 尾帧图生视频模式，其后附加文本提示词。
    # 说明：根据最新接口文档，首帧图生、首尾帧图生与参考图生互斥；本脚本仅实现首帧/首尾帧模式，
    # 不再传 reference_image 参考图，避免与首帧模式混用。
    content: List[Dict[str, Any]] = []

    # 首帧：使用显式 first_frame_* 字段
    first_frame_url = (
        shot.get("first_frame_image_url")
        or shot.get("first_frame_url")
        or shot.get("first_frame")
    )
    if isinstance(first_frame_url, str) and first_frame_url.strip():
        first_frame_url = _to_image_data_url_if_local(first_frame_url)
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": first_frame_url.strip()},
                "role": "first_frame",
            }
        )

    # 尾帧：兼容多种字段名 last_frame_*
    last_frame_url = (
        shot.get("last_frame_image_url")
        or shot.get("last_frame_url")
        or shot.get("last_frame")
    )
    if isinstance(last_frame_url, str) and last_frame_url.strip():
        last_frame_url = _to_image_data_url_if_local(last_frame_url)
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": last_frame_url.strip()},
                "role": "last_frame",
            }
        )

    # 文本提示词始终追加在最后
    content.append(
        {
            "type": "text",
            "text": visual_prompt,
        }
    )

    model = ARK_DEFAULT_MODEL
    print(f"[{shot.get('shot_id','')}] model={model} (first_frame/last_frame/text)")

    # 按推荐方式在 body 中直接传参；return_last_frame=True 时查询任务接口可返回尾帧图像（PNG，与视频同分辨率，无水印）
    payload: Dict[str, Any] = {
        "model": model,
        "content": content,
        "duration": int(duration),
        "camera_fixed": False,
        "watermark": True,
        "return_last_frame": bool(return_last_frame),
    }

    resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"视频生成接口 HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    task_id = data.get("id") or data.get("task_id") or data.get("data", {}).get("id")
    if not task_id:
        raise RuntimeError(f"未返回任务 ID: {json.dumps(data, ensure_ascii=False)}")

    detail_url = api_url.rstrip("/") + f"/{task_id}"
    for attempt in range(1, max_attempts + 1):
        time.sleep(interval)
        detail_resp = requests.get(detail_url, headers=headers, timeout=60)
        if detail_resp.status_code != 200:
            raise RuntimeError(f"查询任务失败 HTTP {detail_resp.status_code}: {detail_resp.text}")

        detail = detail_resp.json()
        status = (
            detail.get("status")
            or detail.get("task_status")
            or detail.get("data", {}).get("status")
        )
        shot_id = shot.get("shot_id", "")
        print(f"[{shot_id}] 轮询 {task_id} 第 {attempt}/{max_attempts} 次，状态：{status}")

        if status and str(status).lower() in {"succeeded", "success", "finished", "done"}:
            result = detail.get("result") or detail.get("data") or detail
            video_url = (
                result.get("video_url")
                or result.get("url")
                or (result.get("output") or [{}])[0].get("url")
                or detail.get("content", {}).get("video_url")
            )
            if not video_url:
                raise RuntimeError(f"任务成功但无 video_url: {json.dumps(detail, ensure_ascii=False)}")
            # 若请求时 return_last_frame=True，从查询结果中取尾帧图像 URL（PNG，与视频同分辨率，无水印）
            last_frame_url: Optional[str] = (
                # 官方文档字段：content.last_frame_url（见 reference/视频生成接口文档.md）
                detail.get("content", {}).get("last_frame_url")
                or (result.get("content", {}) if isinstance(result.get("content", {}), dict) else {}).get("last_frame_url")
                # 兼容历史字段
                or result.get("last_frame_url")
                or result.get("last_frame_image_url")
                or result.get("last_frame")
                or (result.get("last_frame_image") or {}).get("url")
                or detail.get("last_frame_url")
            )
            return (video_url, last_frame_url)

        if status and str(status).lower() in {"failed", "error"}:
            raise RuntimeError(f"视频任务失败: {json.dumps(detail, ensure_ascii=False)}")

    raise TimeoutError(f"轮询超时 task_id={task_id}")


def download_image(url: str, output_path: Path, timeout: int = 120) -> None:
    """将图片 URL 下载到本地（用于尾帧等）。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def download_video(url: str, output_path: Path, timeout: int = 300) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def process_one_shot(
    idx: int,
    shot: Dict[str, Any],
    output_dir: Path,
    api_url: str,
    api_key: str,
    max_attempts: int,
    interval: float,
    skip_existing: bool,
    prev_last_frame_path: Optional[Path] = None,
) -> Tuple[int, Dict[str, Any]]:
    """单个分镜：生成视频并下载，返回 (idx, shot_with_video_path)。"""
    shot_id = shot.get("shot_id") or f"shot_{idx:03d}"
    shot = dict(shot)
    shot["shot_id"] = shot_id

    # 若已有 video_path 且文件存在，默认跳过（便于断点续跑）
    if skip_existing:
        existing = shot.get("video_path")
        if existing:
            p = Path(str(existing))
            if not p.is_absolute():
                p = output_dir / p
            if p.exists():
                shot["video_path"] = str(p)
                shot["status"] = "skipped_existing"
                return (idx, shot)
        # 若按 shot_id 命名的 mp4 已存在，也跳过
        p2 = output_dir / f"{shot_id}.mp4"
        if p2.exists():
            shot["video_path"] = str(p2)
            shot["status"] = "skipped_existing"
            return (idx, shot)

    video_url, last_frame_url = call_video_api(
        api_url=api_url,
        api_key=api_key,
        shot=shot,
        duration_fallback=3.0,
        max_attempts=max_attempts,
        interval=interval,
        return_last_frame=True,
    )
    output_path = output_dir / f"{shot_id}.mp4"
    download_video(video_url, output_path)
    shot["video_path"] = str(output_path)
    shot["status"] = "succeeded"
    if isinstance(last_frame_url, str) and last_frame_url.strip():
        shot["last_frame_url"] = last_frame_url.strip()
    # 若接口返回尾帧图像 URL，下载为 PNG 供下一镜作为首帧使用
    if isinstance(last_frame_url, str) and last_frame_url.strip():
        last_frame_path = output_dir / f"{shot_id}_last.png"
        try:
            download_image(last_frame_url.strip(), last_frame_path)
            shot["last_frame_path"] = str(last_frame_path)
        except Exception as e:
            print(f"[{shot_id}] 尾帧图像下载失败，下一镜将不使用本镜尾帧: {e}")
    return (idx, shot)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="根据分镜 JSON 串行生成每个镜头视频（shot_001 → shot_002 → …），无批量并行。"
    )
    parser.add_argument("--storyboard", required=True, help="分镜 JSON 文件路径（数组）。")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="各分镜视频输出目录；未指定时由 --song-name 或随机 6 位数决定，见 music_output/<歌曲名|随机数>。",
    )
    parser.add_argument(
        "--song-name",
        default=None,
        help="歌曲名称，用于生成任务子目录 music_output/<歌曲名>；未提供则使用 6 位随机数。",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("VIDEO_API_URL", ARK_DEFAULT_URL),
        help="视频任务创建接口，默认从 .env 的 VIDEO_API_URL 读取。",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("ARK_API_KEY", ""),
        help="鉴权密钥，从 .env 的 ARK_API_KEY 读取。",
    )
    parser.add_argument(
        "--out-storyboard",
        default=None,
        help="输出分镜 JSON 路径；未指定时写入 output_dir/storyboard_updated.json（所有中间产物均在 output_dir）。",
    )
    parser.add_argument(
        "--precheck",
        action="store_true",
        help="仅做分镜与环境自检，不执行生成（用于提前发现缺字段等问题）。",
    )
    parser.add_argument(
        "--autofix-missing-prompts",
        action="store_true",
        default=True,
        help="自检失败时尝试自动补齐缺失的 visual_prompt（默认开启）。",
    )
    parser.add_argument(
        "--no-autofix-missing-prompts",
        action="store_true",
        help="关闭自动补齐 visual_prompt。",
    )
    parser.add_argument(
        "--precheck-report",
        default=None,
        help="自检报告输出路径（JSON）。默认写入 output_dir/storyboard_precheck_report.json。",
    )
    parser.add_argument(
        "--fixed-storyboard",
        default=None,
        help="自动修复后的分镜输出路径（JSON）。默认写入 output_dir/storyboard_fixed.json。",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        default=True,
        help="遇到单个分镜失败时不中断，继续生成并记录失败原因（默认开启）。",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="任一分镜失败即立刻中断（与 --continue-on-error 相反）。",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="若 output_dir 中已存在分镜视频则跳过（便于断点续跑，默认开启）。",
    )
    parser.add_argument(
        "--progress-save",
        action="store_true",
        default=True,
        help="每完成一个分镜就写一次输出分镜 JSON（默认开启，避免中途失败丢进度）。",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="已废弃：本脚本仅支持串行生成，该参数保留仅为兼容，不生效。",
    )
    parser.add_argument("--max-attempts", type=int, default=60, help="单任务轮询次数。")
    parser.add_argument("--interval", type=float, default=5.0, help="轮询间隔秒数。")
    parser.add_argument(
        "--assets",
        default=None,
        help="资产设定 JSON 路径（如 reference_assets.json），用于将人物/场景/道具的精细描述自动融合进每个分镜的 prompt。",
    )

    args = parser.parse_args()

    if not args.api_key:
        raise RuntimeError("未配置 ARK_API_KEY，请在 mv-production/scripts/.env 中设置。")
    if args.fail_fast:
        args.continue_on_error = False

    storyboard_path = Path(args.storyboard)
    if not storyboard_path.exists():
        raise FileNotFoundError(f"找不到分镜文件: {storyboard_path}")

    output_dir = resolve_output_dir(output_dir=args.output_dir, song_name=args.song_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载资产设定（若存在），用于在生成视频 prompt 时注入精细人物/场景/道具描述。
    global ASSETS_DATA
    assets_path: Optional[Path] = None
    if args.assets:
        assets_path = Path(args.assets)
    else:
        candidate = output_dir / "reference_assets.json"
        if candidate.exists():
            assets_path = candidate
    if assets_path and assets_path.exists():
        try:
            ASSETS_DATA = json.loads(assets_path.read_text(encoding="utf-8"))
            print(f"已加载资产设定: {assets_path}")
        except Exception as e:
            print(f"加载资产设定失败（忽略，仅不会注入资产描述）: {assets_path} -> {e}")

    raw = storyboard_path.read_text(encoding="utf-8")
    data: List[Dict[str, Any]] = json.loads(raw)
    if args.no_autofix_missing_prompts:
        args.autofix_missing_prompts = False

    precheck_report_path = Path(args.precheck_report) if args.precheck_report else (output_dir / "storyboard_precheck_report.json")
    fixed_storyboard_path = Path(args.fixed_storyboard) if args.fixed_storyboard else (output_dir / "storyboard_fixed.json")

    ok, issues = validate_storyboard(data)
    fixed_notes: List[str] = []
    fixed_changed = False
    fixed_data: Any = data
    if (not ok) and args.autofix_missing_prompts:
        fixed_data, fixed_changed, fixed_notes = autofix_storyboard_missing_prompts(data)
        ok2, issues2 = validate_storyboard(fixed_data)
        if ok2:
            ok, issues = ok2, issues2
        else:
            ok, issues = ok2, issues2
    if issues:
        print("分镜自检发现问题：")
        for msg in issues[:200]:
            print(f"- {msg}")
        if len(issues) > 200:
            print(f"... 还有 {len(issues)-200} 条未展示")
    if fixed_notes:
        print("自检自动修复（visual_prompt）记录：")
        for msg in fixed_notes[:200]:
            print(f"- {msg}")
        if len(fixed_notes) > 200:
            print(f"... 还有 {len(fixed_notes)-200} 条未展示")

    # 写自检报告，便于上游“自检不通过 -> 重新生成”
    precheck_report = {
        "ok": ok,
        "issues": issues,
        "autofix_missing_prompts": bool(args.autofix_missing_prompts),
        "autofix_changed": bool(fixed_changed),
        "autofix_notes": fixed_notes,
        "storyboard_path": str(storyboard_path),
        "output_dir": str(output_dir),
    }
    precheck_report_path.write_text(json.dumps(precheck_report, ensure_ascii=False, indent=2), encoding="utf-8")

    if fixed_changed:
        fixed_storyboard_path.write_text(json.dumps(fixed_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入修复版分镜: {fixed_storyboard_path}")
    print(f"已写入自检报告: {precheck_report_path}")

    if args.precheck:
        if not ok:
            raise SystemExit(2)
        print("自检通过。")
        return

    # 若自动修复有变更，则后续生成使用修复版分镜
    if fixed_changed:
        data = fixed_data  # type: ignore[assignment]
    if not isinstance(data, list):
        raise ValueError("storyboard JSON 必须是数组。")

    # 串行生成：严格按 shot_001 → shot_002 → … 顺序，无批量/并行
    results_by_idx: Dict[int, Dict[str, Any]] = {}
    failures: List[Dict[str, Any]] = []
    out_path = Path(args.out_storyboard) if args.out_storyboard else (output_dir / "storyboard_updated.json")

    def save_progress() -> None:
        updated = [results_by_idx.get(i) or data[i] for i in range(len(data))]
        out_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")

    prev_last_frame_path: Optional[Path] = None
    for idx, raw_shot in enumerate(data):
        try:
            shot_dict = dict(raw_shot) if isinstance(raw_shot, dict) else {"shot_id": f"shot_{idx:03d}"}

            # 若当前未显式设置 first_frame_*，且上一镜返回了尾帧图像，则作为本镜首帧，
            # 即「上一条视频的尾帧作为下一条视频的首帧」。
            has_first = any(
                isinstance(shot_dict.get(k), str) and shot_dict.get(k).strip()
                for k in ["first_frame_image_url", "first_frame_url", "first_frame"]
            )
            if (not has_first) and prev_last_frame_path is not None and prev_last_frame_path.exists():
                shot_dict["first_frame_image_url"] = str(prev_last_frame_path)

            i, updated_shot = process_one_shot(
                idx,
                shot_dict,
                output_dir,
                args.api_url,
                args.api_key,
                args.max_attempts,
                args.interval,
                args.skip_existing,
                prev_last_frame_path=prev_last_frame_path,
            )
            results_by_idx[i] = updated_shot
            print(f"完成 [{i+1}/{len(data)}] {updated_shot.get('shot_id')}")

            # 本镜返回的尾帧图像路径，供下一镜作为首帧使用；若本镜被跳过则尝试使用已存在的 _last.png
            lp = updated_shot.get("last_frame_path")
            if isinstance(lp, str):
                prev_last_frame_path = Path(lp)
            elif isinstance(lp, Path):
                prev_last_frame_path = lp
            elif updated_shot.get("status") == "skipped_existing":
                existing_last = output_dir / f"{updated_shot.get('shot_id')}_last.png"
                prev_last_frame_path = existing_last if existing_last.exists() else None
            else:
                prev_last_frame_path = None

            if args.progress_save:
                save_progress()
        except Exception as e:
            shot_id = (raw_shot.get("shot_id") if isinstance(raw_shot, dict) else None) or f"shot_{idx:03d}"
            err = str(e)
            print(f"分镜 {idx} ({shot_id}) 失败: {err}")
            failed_shot = dict(raw_shot) if isinstance(raw_shot, dict) else {"shot_id": shot_id}
            failed_shot["shot_id"] = failed_shot.get("shot_id") or shot_id
            failed_shot["status"] = "failed"
            failed_shot["error"] = err
            results_by_idx[idx] = failed_shot
            failures.append({"idx": idx, "shot_id": failed_shot["shot_id"], "error": err})
            if args.progress_save:
                save_progress()
            if not args.continue_on_error:
                raise

    # 最终落盘一次
    save_progress()
    if failures:
        (output_dir / "shot_failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"存在失败分镜 {len(failures)}/{len(data)}，详情见 {output_dir/'shot_failures.json'}")
    print(f"已写入 {out_path}")


if __name__ == "__main__":
    main()

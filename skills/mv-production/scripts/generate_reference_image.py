#!/usr/bin/env python3
"""
基于 Doubao Seedream 5.0 生成 MV 所需图片，保证与分镜一致性：
- 角色三视图（character_views）：正面 / 侧面 / 背面
- 场景图（key_scenes）：根据分镜/资产中的场景列表生成
- 道具图（props）：根据分镜/资产中的道具列表生成
 - 首帧图（first_frame.png）：供首个视频分镜作为 first_frame_image_url 使用

支持两种用法：
1) 配置驱动：--config assets.json --output-dir output_dir [--mode all|character|scenes|props|first_frame]
2) 单图（兼容）：--prompt "..." --output path/to/image.jpg

支持参考图（文生图接口的 image 参数，URL 或 Base64，最多 14 张）：
- CLI: --reference-image 可多次传入
- Config: reference_images/ref_images

风格收敛策略：
- 若提供用户参考图：以用户参考图为风格基准
- 若未提供用户参考图：默认启用 auto-style-anchor，先生成角色正面作为后续场景/道具的参考图输入
"""

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from dotenv import load_dotenv

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

load_dotenv(_SCRIPT_DIR / ".env")

ARK_IMAGE_API_URL = os.getenv(
    "IMAGE_API_URL",
    "https://ark.cn-beijing.volces.com/api/v3/images/generations",
)
ARK_IMAGE_MODEL = os.getenv(
    "IMAGE_MODEL",
    "doubao-seedream-5-0-260128",
)
ARK_API_KEY = os.getenv("ARK_API_KEY")

# 角色三视图视角描述，用于 prompt 后缀
CHARACTER_VIEW_PROMPTS = {
    "front": "front view, character turnaround front, full body reference",
    "side": "side view, character turnaround side, full body reference",
    "back": "back view, character turnaround back, full body reference",
}


def _sanitize_id(s: str) -> str:
    """将 id 转为可做文件名的字符串。"""
    return re.sub(r"[^\w\-]", "_", s).strip("_") or "item"


def _image_to_api_format(image: str) -> str:
    """
    将参考图输入转为 API 可用的形式：
    - 远程 URL / data URL：原样返回
    - 本地文件路径：读取并转为 data:<mime>;base64,<...>
    - 纯 base64：去掉空白与换行后，保持为 base64（或补 data:image/png;base64, 前缀）
    """
    s = image.strip()
    if not s:
        return s
    if s.startswith(("http://", "https://", "data:")):
        return s
    # 显式 base64 前缀支持：base64:<...>
    if s.lower().startswith("base64:"):
        b = re.sub(r"\s+", "", s.split(":", 1)[1])
        return f"data:image/png;base64,{b}"
    # 本地路径：支持 ~、相对路径；会在常见工作目录下探测真实文件后再转 base64
    p0 = Path(s).expanduser()
    candidates: List[Path] = []
    if p0.is_absolute():
        candidates.append(p0)
    else:
        # 运行目录可能是 mv-production/ 或 mv-production/scripts/，都尝试一次
        candidates.extend(
            [
                Path.cwd() / p0,
                _SCRIPT_DIR / p0,
                _SCRIPT_DIR.parent / p0,
                _SCRIPT_DIR.parent.parent / p0,
            ]
        )
    p: Optional[Path] = next((pp for pp in candidates if pp.is_file()), None)
    if p is not None:
        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        suffix = p.suffix.lower()
        mime = "image/png"
        if suffix in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif suffix == ".webp":
            mime = "image/webp"
        elif suffix == ".gif":
            mime = "image/gif"
        return f"data:{mime};base64,{b64}"
    # 纯 base64：清理空白/换行；若看起来像 base64 则补一个默认的 png data URL 前缀
    compact = re.sub(r"\s+", "", s)
    if len(compact) >= 200 and re.fullmatch(r"[A-Za-z0-9+/=]+", compact or ""):
        return f"data:image/png;base64,{compact}"
    return compact


def call_image_api(
    prompt: str,
    api_url: str,
    api_key: str,
    model: Optional[str] = None,
    image: Optional[Union[str, List[str]]] = None,
) -> str:
    """调用文生图 API 并返回图片 URL。支持可选参考图 image（URL 或 Base64，最多 14 张）。"""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: Dict[str, Any] = {
        "model": model or ARK_IMAGE_MODEL,
        "prompt": prompt,
        "size": "2K",
        "sequential_image_generation": "disabled",
        "output_format": "png",
        "response_format": "url",
        "stream": False,
        "watermark": False,
    }

    if image is not None:
        if isinstance(image, str):
            image = [image]
        if image:
            images_for_api = [_image_to_api_format(im) for im in image[:14]]
            payload["image"] = images_for_api[0] if len(images_for_api) == 1 else images_for_api

    resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"文生图接口 HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    image_url = (
        data.get("data", [{}])[0].get("url")
        or data.get("url")
        or (data.get("output") or [{}])[0].get("url")
    )
    if not image_url:
        raise RuntimeError(f"未返回图片 URL: {json.dumps(data, ensure_ascii=False)}")
    return image_url


def download_image(url: str, output_path: Path, timeout: int = 300) -> None:
    """下载图片到本地。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def generate_character_views(
    character_description: str,
    output_dir: Path,
    api_url: str,
    api_key: str,
    style_suffix: str = "high detail, consistent style for MV reference",
    reference_images: Optional[List[str]] = None,
) -> Dict[str, str]:
    """生成角色三视图，返回 { front: path, side: path, back: path }。"""
    base_prompt = f"{character_description.strip()}, {style_suffix}"
    out: Dict[str, str] = {}
    for view_name, view_suffix in CHARACTER_VIEW_PROMPTS.items():
        prompt = f"{base_prompt}, {view_suffix}"
        print(f"[角色三视图] 生成 {view_name} ...")
        url = call_image_api(prompt, api_url, api_key, image=reference_images)
        path = output_dir / "character_views" / f"{view_name}.png"
        download_image(url, path)
        out[view_name] = str(path)
    return out


def generate_scenes(
    scenes: List[Dict[str, Any]],
    output_dir: Path,
    api_url: str,
    api_key: str,
    style_suffix: str = "consistent style for MV reference, cinematic",
    reference_images: Optional[List[str]] = None,
) -> Dict[str, str]:
    """根据场景列表生成场景图，返回 { scene_id: path }。"""
    out: Dict[str, str] = {}
    for i, item in enumerate(scenes):
        scene_id = item.get("id") or item.get("scene_id") or f"scene_{i+1:02d}"
        desc = item.get("description") or item.get("prompt") or item.get("name") or str(item)
        scene_id_safe = _sanitize_id(scene_id)
        prompt = f"{desc.strip()}, {style_suffix}"
        print(f"[场景图] 生成 {scene_id} ...")
        url = call_image_api(prompt, api_url, api_key, image=reference_images)
        path = output_dir / "key_scenes" / f"{scene_id_safe}.png"
        download_image(url, path)
        out[scene_id] = str(path)
    return out


def generate_props(
    props: List[Dict[str, Any]],
    output_dir: Path,
    api_url: str,
    api_key: str,
    style_suffix: str = "isolated on transparent or neutral background, consistent style for MV reference",
    reference_images: Optional[List[str]] = None,
) -> Dict[str, str]:
    """根据道具列表生成道具图，返回 { prop_id: path }。"""
    out: Dict[str, str] = {}
    for i, item in enumerate(props):
        prop_id = item.get("id") or item.get("prop_id") or f"prop_{i+1:02d}"
        desc = item.get("description") or item.get("prompt") or item.get("name") or str(item)
        prop_id_safe = _sanitize_id(prop_id)
        prompt = f"{desc.strip()}, {style_suffix}"
        print(f"[道具图] 生成 {prop_id} ...")
        url = call_image_api(prompt, api_url, api_key, image=reference_images)
        path = output_dir / "props" / f"{prop_id_safe}.png"
        download_image(url, path)
        out[prop_id] = str(path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="根据分镜/资产生成参考图（角色三视图、场景图、道具图），保证与分镜一致。"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="资产 JSON 路径，含 character、scenes、props，见 reference/参考图生成规则.md。",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="参考图输出根目录（character_views、key_scenes、props 将写在此目录下）。",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "character", "scenes", "props", "first_frame"],
        default="all",
        help="生成范围：all=全部，character=仅角色三视图，scenes=仅场景图，props=仅道具图，first_frame=仅生成首帧图 first_frame.png。",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="单图模式：文生图提示词（与 --output 搭配，兼容旧用法）。",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="单图模式：输出图片路径。",
    )
    parser.add_argument(
        "--api-url",
        default=ARK_IMAGE_API_URL,
        help="文生图 API 地址。",
    )
    parser.add_argument(
        "--api-key",
        default=ARK_API_KEY,
        help="文生图 API 密钥。",
    )
    parser.add_argument(
        "--reference-image",
        dest="reference_images",
        action="append",
        default=None,
        help="参考图路径或 URL，可多次传入（最多 14 张）。生成时以参考图作风格/构图，实现「单图生图/多图生图」。",
    )
    parser.add_argument(
        "--style-suffix-all",
        default=None,
        help="统一覆盖角色/场景/道具的 style_suffix（用于收敛风格）。未提供则使用各类别默认值。",
    )
    parser.add_argument(
        "--auto-style-anchor",
        action="store_true",
        default=True,
        help="当未提供任何参考图时，自动使用生成的角色正面图作为后续场景/道具的参考图以收敛风格（默认开启）。",
    )
    parser.add_argument(
        "--no-auto-style-anchor",
        action="store_true",
        help="关闭自动风格锚点：无参考图时，场景/道具仅按文本生成，风格可能更发散。",
    )

    args = parser.parse_args()

    if not args.api_key:
        raise RuntimeError("未配置 API 密钥，请在 .env 中设置 ARK_API_KEY。")

    # 单图模式（兼容）
    if args.prompt is not None and args.output is not None:
        print("正在生成参考图（单图模式）...")
        image_url = call_image_api(
            args.prompt, args.api_url, args.api_key, image=args.reference_images
        )
        output_path = Path(args.output)
        download_image(image_url, output_path)
        print(f"参考图已保存: {output_path}")
        return

    # 配置驱动模式
    if not args.config or not args.output_dir:
        parser.error("配置驱动模式需要同时提供 --config 和 --output-dir；或使用单图模式 --prompt + --output。")

    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    config: Dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))

    # 参考图：命令行优先，否则从 config 的 reference_images / ref_images 读取（最多 14 张）
    ref_images: Optional[List[str]] = args.reference_images
    if ref_images is None:
        ref_images = config.get("reference_images") or config.get("ref_images")
        if isinstance(ref_images, str):
            ref_images = [ref_images]
        if ref_images and len(ref_images) > 14:
            ref_images = ref_images[:14]

    if args.no_auto_style_anchor:
        args.auto_style_anchor = False

    result: Dict[str, Any] = {"character_views": {}, "key_scenes": {}, "props": {}, "first_frame": ""}

    # 首帧模式：仅生成 first_frame.png（首个视频分镜的首帧图）
    if args.mode == "first_frame":
        # 1) 优先使用 config.first_frame.description/prompt
        first_cfg = config.get("first_frame") or {}
        desc = (
            first_cfg.get("description")
            or first_cfg.get("prompt")
            or ""
        )
        # 2) 退回：角色 + 第一个场景
        if not desc:
            char = config.get("character") or config.get("characters")
            char_desc = ""
            if isinstance(char, dict):
                char_desc = (char.get("description") or char.get("prompt") or char.get("name") or "").strip()
            elif isinstance(char, list) and len(char) > 0 and isinstance(char[0], dict):
                char_desc = (char[0].get("description") or char[0].get("prompt") or char[0].get("name") or "").strip()
            scenes = config.get("scenes") or config.get("key_scenes") or []
            scene_desc = ""
            if isinstance(scenes, list) and scenes and isinstance(scenes[0], dict):
                scene_desc = (
                    scenes[0].get("description") or scenes[0].get("prompt") or scenes[0].get("name") or ""
                ).strip()
            parts = [p for p in [char_desc, scene_desc] if p]
            base = "，".join(parts) if parts else "MV 开场镜头，主角在主场景中，高清电影感画面"
            desc = f"{base}，作为整支 MV 的首帧画面，16:9 构图，电影级灯光，高清细节"
        prompt_first = desc.strip()
        print("[首帧] 生成 first_frame.png ...")
        url = call_image_api(prompt_first, args.api_url, args.api_key, image=ref_images)
        first_path = output_dir / "first_frame.png"
        download_image(url, first_path)
        result["first_frame"] = str(first_path)
    # 普通模式：角色三视图 / 场景图 / 道具图
    if args.mode in ("all", "character"):
        char = config.get("character") or config.get("characters")
        desc = ""
        if isinstance(char, dict):
            desc = (char.get("description") or char.get("prompt") or char.get("name") or "").strip()
        elif isinstance(char, list) and len(char) > 0 and isinstance(char[0], dict):
            desc = (char[0].get("description") or char[0].get("prompt") or char[0].get("name") or "").strip()
        if desc:
            result["character_views"] = generate_character_views(
                desc,
                output_dir,
                args.api_url,
                args.api_key,
                style_suffix=(args.style_suffix_all or "high detail, consistent style for MV reference"),
                reference_images=ref_images,
            )

    # 若未提供参考图，且开启自动风格锚点：用生成的角色正面作为后续场景/道具参考
    if args.mode != "first_frame" and (not ref_images) and args.auto_style_anchor:
        cv = result.get("character_views")
        if isinstance(cv, dict):
            front = cv.get("front")
            if isinstance(front, str) and front.strip() and Path(front).exists():
                ref_images = [front.strip()]

    if args.mode in ("all", "scenes"):
        scenes = config.get("scenes") or config.get("key_scenes") or []
        if isinstance(scenes, list) and scenes:
            result["key_scenes"] = generate_scenes(
                scenes,
                output_dir,
                args.api_url,
                args.api_key,
                style_suffix=(args.style_suffix_all or "consistent style for MV reference, cinematic"),
                reference_images=ref_images,
            )

    if args.mode in ("all", "props"):
        props = config.get("props") or config.get("props_list") or []
        if isinstance(props, list) and props:
            result["props"] = generate_props(
                props,
                output_dir,
                args.api_url,
                args.api_key,
                style_suffix=(args.style_suffix_all or "isolated on transparent or neutral background, consistent style for MV reference"),
                reference_images=ref_images,
            )

    # 写一份生成结果索引，便于分镜引用（并附 meta 便于追溯风格基准）
    index_path = output_dir / "reference_images_index.json"
    index_payload = dict(result)
    index_payload["_meta"] = {
        "reference_images_input": ref_images or [],
        "style_suffix_all": args.style_suffix_all or "",
        "auto_style_anchor": bool(args.auto_style_anchor),
        "image_model": ARK_IMAGE_MODEL,
        "image_api_url": ARK_IMAGE_API_URL,
    }
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"参考图生成完成，索引已写入: {index_path}")


if __name__ == "__main__":
    main()

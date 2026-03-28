#!/usr/bin/env python3
"""
upload_media.py — 上传媒资到 VOD，返回 Vid

支持两种输入：
  1) 本地文件路径：直接上传（同步返回 Vid）
  2) http/https 链接：URL 拉取上传（异步），拿 JobId 后轮询 QueryUploadTaskInfo 直到返回 Vid

用法:
  python <SKILL_DIR>/scripts/upload_media.py "<local_file_path_or_http_url>" [space_name]

输出:
  {"Vid":"vxxxx","Source":"vid://vxxxx","PosterUri":"...","FileName":"...","SpaceName":"..."}
"""
import os
import sys
import json
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vod_common import (
    ensure_deps,
    load_credentials,
    build_service,
    get_space_name,
    out,
    bail,
    POLL_INTERVAL,
    POLL_MAX,
)

# ══════════════════════════════════════════════════════
# 安全：本地文件路径白名单
# 只允许上传 workspace/ 和 userdata/ 下的文件，防止读取系统敏感文件
# ══════════════════════════════════════════════════════

_ALLOWED_PATH_PREFIXES = None  # 延迟初始化

def _get_allowed_prefixes():
    global _ALLOWED_PATH_PREFIXES
    if _ALLOWED_PATH_PREFIXES is None:
        prefixes = []
        # workspace 目录（当前工作目录或 WORKSPACE 环境变量）
        ws = os.environ.get("WORKSPACE", os.getcwd())
        prefixes.append(os.path.realpath(ws))
        # userdata 目录
        ud = os.path.join(os.path.dirname(ws), "userdata") if ws else ""
        if ud:
            prefixes.append(os.path.realpath(ud))
        # 也允许 /tmp 目录（sandbox 常用临时目录）
        prefixes.append("/tmp")
        _ALLOWED_PATH_PREFIXES = prefixes
    return _ALLOWED_PATH_PREFIXES

def _validate_local_path(file_path: str):
    """校验本地文件路径是否在允许的目录范围内。"""
    real = os.path.realpath(file_path)
    for prefix in _get_allowed_prefixes():
        if real.startswith(prefix + os.sep) or real == prefix:
            return
    bail(
        f"安全限制：只允许上传 workspace/、userdata/ 或 /tmp 下的文件。"
        f"拒绝路径：{file_path}"
    )


def _guess_ext_from_path(path: str) -> str:
    _, ext = os.path.splitext(path or "")
    ext = (ext or "").strip()
    if not ext:
        bail("上传文件必须携带文件后缀（例如 .mp4 / .mp3）")
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def _is_http_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith("http://") or s.startswith("https://")


def _poll_url_upload(client, job_id: str) -> dict:
    """
    轮询 QueryUploadTaskInfo 直到:
      - 成功: 返回 Vid
      - 失败: 返回错误
      - 超时: 返回 resume_hint
    """
    if not job_id:
        bail("URL 上传未返回 JobId")

    last_state = ""
    for i in range(1, POLL_MAX + 1):
        try:
            raw = client.skill_get("SkillQueryUploadTaskInfo", {"JobIds": job_id})
        except Exception as e:
            bail(f"QueryUploadTaskInfo 调用失败: {e}")

        result = raw.get("Result", raw) or {}
        data = result.get("Data", {}) or {}
        not_exist = data.get("NotExistJobIds") or []
        if job_id in not_exist:
            bail(f"JobId 不存在或已过期：{job_id}")

        info_list = data.get("MediaInfoList") or []
        info = info_list[0] if info_list else {}
        state = info.get("State", "") or ""
        last_state = state or last_state
        vid = info.get("Vid", "") or ""

        # 成功：拿到 Vid 即可返回（有些状态值文档未强约束，这里以 Vid 为准）
        if vid:
            return info

        # 失败：尽量覆盖常见失败状态
        state_l = state.lower()
        if state_l in {"fail", "failed", "error"}:
            bail(f"URL 拉取上传失败：State={state!r} JobId={job_id}")

        time.sleep(POLL_INTERVAL)

    return {
        "error": f"轮询超时（{POLL_MAX} 次 × {POLL_INTERVAL}s），URL 拉取上传仍在处理中",
        "resume_hint": {
            "description": "URL 上传尚未完成，可用以下命令重试（会重新发起 URL 上传并再次轮询）",
            "command": 'python <SKILL_DIR>/scripts/upload_media.py "<http_url>" [space_name]',
        },
        "JobId": job_id,
        "State": last_state,
    }


def _upload_local_file(client, sp: str, file_path: str) -> dict:
    from volcengine.vod.models.request.request_vod_pb2 import VodUploadMediaRequest

    svc = client.svc  # 底层 VodService

    req = VodUploadMediaRequest()
    req.SpaceName = sp
    req.FilePath = file_path
    req.FileExtension = _guess_ext_from_path(file_path)
    try:
        resp = svc.upload_media(req)
    except Exception as e:
        bail(f"upload_media 调用失败: {e}")

    err = getattr(getattr(resp, "ResponseMetadata", None), "Error", None)
    if err and getattr(err, "Code", ""):
        bail(f"上传失败: {getattr(err, 'Code', '')} {getattr(err, 'Message', '')}".strip())

    result_data = getattr(getattr(resp, "Result", None), "Data", None)
    vid = getattr(result_data, "Vid", "") if result_data else ""
    if not vid:
        bail("上传成功但未返回 Vid（请检查账号权限/空间配置）")

    poster = getattr(result_data, "PosterUri", "") if result_data else ""
    src_info = getattr(result_data, "SourceInfo", None) if result_data else None
    file_name = getattr(src_info, "FileName", "") if src_info else ""
    return {"Vid": vid, "PosterUri": poster, "FileName": file_name}


def _upload_by_url(client, sp: str, http_url: str) -> dict:
    from volcengine.vod.models.request.request_vod_pb2 import VodUrlUploadRequest

    svc = client.svc  # 底层 VodService

    parsed = urlparse(http_url)
    ext = _guess_ext_from_path(parsed.path)

    req = VodUrlUploadRequest()
    req.SpaceName = sp
    url_set = req.URLSets.add()
    url_set.SourceUrl = http_url
    url_set.FileExtension = ext
    url_set.CallbackArgs = ""

    try:
        resp = svc.upload_media_by_url(req)
    except Exception as e:
        bail(f"upload_media_by_url 调用失败: {e}")

    err = getattr(getattr(resp, "ResponseMetadata", None), "Error", None)
    if err and getattr(err, "Code", ""):
        bail(f"URL 上传提交失败: {getattr(err, 'Code', '')} {getattr(err, 'Message', '')}".strip())

    result = getattr(resp, "Result", None)
    data = getattr(result, "Data", None)
    first = data[0] if data and len(data) > 0 else None
    job_id = getattr(first, "JobId", "") if first else ""
    if not job_id:
        bail("URL 上传提交成功但未返回 JobId")

    info = _poll_url_upload(client, job_id)
    if "error" in info:
        out(info)
        return {}
    vid = info.get("Vid", "")
    if not vid:
        bail(f"URL 上传已完成但未返回 Vid：JobId={job_id}")

    source_info = info.get("SourceInfo") or {}
    file_name = source_info.get("FileName", "") or ""
    return {"Vid": vid, "FileName": file_name, "JobId": job_id, "SourceUrl": http_url}


def main():
    if len(sys.argv) < 2:
        bail('用法: python <SKILL_DIR>/scripts/upload_media.py "<local_file_path_or_http_url>" [space_name]')

    src = sys.argv[1].strip()

    ensure_deps()
    ak, sk = load_credentials()
    client = build_service(ak, sk)
    sp = get_space_name(argv_pos=2)

    if _is_http_url(src):
        meta = _upload_by_url(client, sp, src)
        if not meta:
            return
        vid = meta.get("Vid", "")
        file_name = meta.get("FileName", "")
        out(
            {
                "Vid": vid,
                "Source": f"vid://{vid}",
                "PosterUri": "",
                "FileName": file_name,
                "SpaceName": sp,
                "SourceUrl": meta.get("SourceUrl", ""),
                "JobId": meta.get("JobId", ""),
            }
        )
        return

    # 默认按本地文件处理
    file_path = src
    _validate_local_path(file_path)  # 安全校验：路径白名单
    if not os.path.isfile(file_path):
        bail(f"本地文件不存在：{file_path}")

    meta = _upload_local_file(client, sp, file_path)
    vid = meta.get("Vid", "")
    file_name = meta.get("FileName", "")
    poster = meta.get("PosterUri", "")

    out(
        {
            "Vid": vid,
            "Source": f"vid://{vid}",
            "PosterUri": poster,
            "FileName": file_name,
            "SpaceName": sp,
        }
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ASR -> LRC（火山引擎 openspeech）

输入：视频/音频文件路径
处理：ffmpeg 提取/转码为 mp3 -> base64 -> 调用火山引擎异步转录 -> 生成 .lrc 歌词文件

依赖：
  - 本机可用 ffmpeg
  - 项目根目录（或本脚本上级目录）存在 .env 且包含 DOUBAO_SPEECH_API_KEY=...

用法：
  python .cursor/skills/ktv-video-production/scripts/asr-to-lrc.py input.mp4 -o lyrics.lrc
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
except ImportError:  # pragma: no cover
    from urllib2 import Request, urlopen, HTTPError  # type: ignore


def project_root() -> Path:
    # .../ktv/.cursor/skills/ktv-video-production/scripts/asr-to-lrc.py -> parents[4] == .../ktv
    return Path(__file__).resolve().parents[4]


def load_api_key() -> str:
    """
    从项目根目录（优先）或 ktv-video-production skill 目录读取 .env 的 DOUBAO_SPEECH_API_KEY。
    """
    candidates = [
        project_root() / ".env",
        Path(__file__).resolve().parents[2] / ".env",  # .../.cursor/skills/ktv-video-production/.env
        Path(__file__).resolve().parents[3] / ".env",  # .../.cursor/skills/.env
        Path(__file__).resolve().parents[4] / ".env",  # .../.cursor/.env
    ]
    for env_file in candidates:
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("DOUBAO_SPEECH_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("❌ 找不到 DOUBAO_SPEECH_API_KEY。请在项目根目录创建 .env 并写入：DOUBAO_SPEECH_API_KEY=...", file=sys.stderr)
    sys.exit(1)


def http_post(
    url: str, headers: dict[str, str], body: str, *, ssl_context: ssl.SSLContext | None
) -> tuple[str, dict[str, str]]:
    req = Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    try:
        resp = urlopen(req, timeout=60, context=ssl_context)
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        return resp.read().decode("utf-8", errors="replace"), resp_headers
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if getattr(e, "fp", None) else ""
        print(f"❌ HTTP {e.code} 响应: {err_body[:1000]}", file=sys.stderr)
        raise


def to_raw_base64(s: str) -> str:
    s = s.strip()
    if s.startswith("data:"):
        idx = s.find(",")
        if idx != -1:
            return s[idx + 1 :].strip()
    return s


def submit_task(
    api_key: str,
    audio_base64_or_data_url: str,
    request_id: str,
    *,
    audio_type: str = "mp3",
    ssl_context: ssl.SSLContext | None,
) -> str:
    submit_url = f"https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit?api_key={api_key}"
    raw_b64 = to_raw_base64(audio_base64_or_data_url)
    payload = {
        "audio": {"data": raw_b64, "type": audio_type},
        "request": {
            "modal_name": "bigmodel",
            "enable_emotion_detection": False,
            "enable_gender_detection": False,
            "enable_speaker_info": False,
            "enable_poi_fc": False,
            "use_itn": True,
            "use_punc": True,
            "enable_lid": True,
        },
        "user": {"uid": "ktv-video-production"},
    }
    headers = {
        "Accept": "*/*",
        "x-api-key": api_key,
        "x-api-request-id": request_id,
        "x-api-resource-id": "volc.seedasr.auc",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
    }
    response, _ = http_post(submit_url, headers, json.dumps(payload, ensure_ascii=False), ssl_context=ssl_context)
    if response.strip() in ("{}", ""):
        return request_id
    match = re.search(r'"(?:id|task_id)"\s*:\s*"([^"]+)"', response) or re.search(
        r'"(?:id|task_id)"\s*:\s*(\d+)', response
    )
    if match:
        return match.group(1)
    print("❌ 提交失败，响应如下（截断）:", file=sys.stderr)
    print(response[:2000], file=sys.stderr)
    sys.exit(1)


def query_task(api_key: str, request_id: str, *, ssl_context: ssl.SSLContext | None) -> tuple[int, dict[str, Any]]:
    query_url = f"https://openspeech.bytedance.com/api/v3/auc/bigmodel/query?api_key={api_key}"
    headers = {
        "Accept": "*/*",
        "x-api-key": api_key,
        "x-api-request-id": request_id,
        "x-api-resource-id": "volc.seedasr.auc",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
    }
    response_text, _ = http_post(query_url, headers, "{}", ssl_context=ssl_context)
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        data = {"code": -1, "raw": response_text}
    return int(data.get("code", -1)), data


def run_ffmpeg_extract_mp3(input_path: Path, out_mp3: Path) -> None:
    """
    将任意音频/视频转为 mp3（单声道、16k 采样，便于 ASR）。
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "64k",
        str(out_mp3),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("❌ 未找到 ffmpeg，请先安装并确保在 PATH 中可用。", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("❌ ffmpeg 转码失败。你可以手动执行以下命令查看错误输出：", file=sys.stderr)
        print(" ".join(cmd), file=sys.stderr)
        sys.exit(1)


def probe_duration_sec(media_path: Path) -> float:
    """
    用 ffprobe 获取媒体时长（秒）。失败时返回 0。
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    try:
        p = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        s = (p.stdout or "").strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def audio_file_to_data_url_base64(audio_path: Path) -> str:
    """
    读取音频文件并转为 data URL base64（与 audio_base64.py 兼容的输出风格）。
    火山侧实际只需要 raw base64，本脚本内部会剥离前缀。
    """
    mime_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
    }
    ext = audio_path.suffix.lower()
    mime = mime_map.get(ext, "audio/octet-stream")
    audio_bytes = audio_path.read_bytes()
    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


@dataclass(frozen=True)
class Word:
    start_sec: float
    text: str


@dataclass(frozen=True)
class Utterance:
    start_sec: float
    end_sec: float
    text: str
    words: tuple[Word, ...]


def _get_float(d: dict[str, Any], keys: Iterable[str], default: float = 0.0) -> float:
    for k in keys:
        if k in d:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                pass
    return default


def _choose_time_scale(max_raw_time: float, duration_sec: float) -> float:
    """
    火山返回的时间字段可能是秒 / 毫秒 / 百分秒 / 十分秒。
    这里用“最大时间是否接近音频时长”来推断缩放因子。
    """
    if max_raw_time <= 0 or duration_sec <= 0:
        return 1.0
    if max_raw_time <= duration_sec * 2.5:
        return 1.0
    candidates = [1.0 / 1000.0, 1.0 / 100.0, 1.0 / 10.0]
    best = 1.0
    best_ratio = float("inf")
    for s in candidates:
        scaled = max_raw_time * s
        ratio = abs(scaled - duration_sec) / max(duration_sec, 1e-6)
        if ratio < best_ratio:
            best_ratio = ratio
            best = s
    # 如果缩放后仍然离谱（比如 >10 倍），就保守不缩放
    if max_raw_time * best > duration_sec * 10:
        return 1.0
    return best


def parse_result_to_utterances(data: dict[str, Any], *, duration_sec: float) -> list[Utterance]:
    """
    尽量兼容火山返回结构的差异：优先走 result.utterances；找不到时做一些降级解析。
    """
    result = data.get("result") or {}
    utterances_raw = result.get("utterances")
    if not isinstance(utterances_raw, list):
        utterances_raw = []

    out: list[Utterance] = []
    max_time_raw = 0.0
    for u in utterances_raw:
        if not isinstance(u, dict):
            continue
        start = _get_float(u, ("start_time", "start", "begin_time"), 0.0)
        end = _get_float(u, ("end_time", "end", "finish_time"), start)
        text = str(u.get("text") or u.get("utterance") or "").strip()
        max_time_raw = max(max_time_raw, start, end)

        words: list[Word] = []
        words_raw = u.get("words") or u.get("word_list") or []
        if isinstance(words_raw, list):
            for w in words_raw:
                if not isinstance(w, dict):
                    continue
                w_start = _get_float(w, ("start_time", "start", "begin_time"), start)
                w_text = str(w.get("text") or w.get("word") or w.get("token") or "").strip()
                if w_text:
                    words.append(Word(start_sec=w_start, text=w_text))
                    max_time_raw = max(max_time_raw, w_start)

        if not text and words:
            text = "".join(w.text for w in words)
        if not text:
            continue
        out.append(Utterance(start_sec=start, end_sec=end, text=text, words=tuple(words)))

    if out:
        scale = _choose_time_scale(max_time_raw, duration_sec)
        if scale == 1.0:
            return out
        scaled: list[Utterance] = []
        for u in out:
            scaled_words = tuple(Word(start_sec=w.start_sec * scale, text=w.text) for w in u.words)
            scaled.append(
                Utterance(
                    start_sec=u.start_sec * scale,
                    end_sec=u.end_sec * scale,
                    text=u.text,
                    words=scaled_words,
                )
            )
        return scaled

    # 兜底：如果只有 result.text，就当成一段
    text = str((result.get("text") or data.get("text") or "")).strip()
    if text:
        return [Utterance(start_sec=0.0, end_sec=0.0, text=text, words=tuple())]
    return []


def format_lrc_timestamp(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    mm = int(sec // 60)
    ss = sec - mm * 60
    return f"{mm:02d}:{ss:05.2f}"


def utterances_to_lrc_lines(utterances: list[Utterance], enhanced: bool) -> list[str]:
    lines: list[str] = []
    for u in utterances:
        ts = format_lrc_timestamp(u.start_sec)
        if enhanced and u.words:
            parts = [f"[{ts}] "]
            for w in u.words:
                wts = format_lrc_timestamp(w.start_sec)
                parts.append(f"<{wts}>{w.text}")
            lines.append("".join(parts).rstrip())
        else:
            lines.append(f"[{ts}] {u.text}".rstrip())
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="从视频/音频生成 LRC 歌词（火山 ASR）")
    parser.add_argument("media", help="输入视频/音频文件路径（mp4/mov/mp3/wav/...）")
    parser.add_argument("-o", "--output", default="lyrics.lrc", help="输出 LRC 文件路径（默认: lyrics.lrc）")
    parser.add_argument(
        "--result-json",
        default="",
        help="保存火山 ASR 的完整结果 JSON（默认与 -o 同名，后缀改为 .asr.json）",
    )
    parser.add_argument(
        "--no-enhanced",
        action="store_true",
        help="输出普通 LRC（禁用逐词时间戳）；默认会尽量输出逐词时间戳（若返回中含 words 字段）",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="轮询间隔秒数（默认 5）",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=10 * 60,
        help="超时秒数（默认 600）",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留临时 mp3 文件（默认删除）",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="跳过 HTTPS 证书校验（仅在公司代理/自签名证书环境下使用）",
    )
    args = parser.parse_args()

    media_path = Path(os.path.expanduser(args.media)).resolve()
    if not media_path.is_file():
        print(f"❌ 输入文件不存在：{media_path}", file=sys.stderr)
        sys.exit(1)

    api_key = load_api_key()
    ssl_context = ssl._create_unverified_context() if args.insecure else None

    tmp_dir = Path(os.environ.get("TMPDIR") or "/tmp")
    tmp_mp3 = tmp_dir / f"ktv-video-production-asr-{uuid.uuid4().hex}.mp3"
    run_ffmpeg_extract_mp3(media_path, tmp_mp3)
    duration_sec = probe_duration_sec(tmp_mp3) or probe_duration_sec(media_path)

    try:
        audio_data_url = audio_file_to_data_url_base64(tmp_mp3)
        request_id = str(uuid.uuid4())
        submit_task(api_key, audio_data_url, request_id, audio_type="mp3", ssl_context=ssl_context)

        deadline = time.time() + float(args.timeout_sec)
        while True:
            if time.time() > deadline:
                print("❌ 转录超时（任务未完成）", file=sys.stderr)
                sys.exit(1)
            time.sleep(float(args.poll_interval))
            code, data = query_task(api_key, request_id, ssl_context=ssl_context)
            result = data.get("result") if isinstance(data, dict) else None
            if isinstance(result, dict) and result.get("additions") is not None:
                break
            if code == 0:
                break
            if code == 1000:
                continue
            # 兼容部分“处理中”结构：result.text 为空时继续
            if isinstance(result, dict) and (result.get("text") or "") == "":
                continue
            print("❌ 转录失败，响应如下（截断）:", file=sys.stderr)
            raw = json.dumps(data, ensure_ascii=False)
            print(raw[:2000], file=sys.stderr)
            sys.exit(1)

        out_path = Path(os.path.expanduser(args.output)).resolve()
        result_json_path = (
            Path(os.path.expanduser(args.result_json)).resolve()
            if str(args.result_json).strip()
            else out_path.with_suffix(".asr.json")
        )
        # 保存完整响应，方便排查时间单位/断句/words 结构
        to_save: dict[str, Any] = {"meta": {"request_id": request_id, "duration_sec": duration_sec}, "response": data}
        result_json_path.write_text(json.dumps(to_save, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        utterances = parse_result_to_utterances(data, duration_sec=duration_sec)
        if not utterances:
            print("❌ 未解析到任何转录结果（utterances 为空）", file=sys.stderr)
            sys.exit(1)

        lrc_lines = utterances_to_lrc_lines(utterances, enhanced=not bool(args.no_enhanced))
        out_path.write_text("\n".join(lrc_lines) + "\n", encoding="utf-8")
        print(f"✅ 已生成 LRC：{out_path}", file=sys.stderr)
        print(f"✅ 已保存 ASR JSON：{result_json_path}", file=sys.stderr)
    finally:
        if args.keep_temp:
            print(f"ℹ️ 临时音频保留在：{tmp_mp3}", file=sys.stderr)
        else:
            try:
                tmp_mp3.unlink(missing_ok=True)  # py3.8+: missing_ok
            except TypeError:  # pragma: no cover (py<3.8)
                if tmp_mp3.exists():
                    tmp_mp3.unlink()


if __name__ == "__main__":
    main()


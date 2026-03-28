#!/usr/bin/env python3
#
# 火山引擎语音识别（异步模式）
#
# 输入：音频 data URL（base64）或 raw base64（建议先用 audio_base64.py 生成）
# 输出：asr_raw.json（保留完整返回，含 utterances/words）
#
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
except ImportError:  # pragma: no cover
    from urllib2 import Request, urlopen, HTTPError  # type: ignore


def load_api_key() -> str:
    """
    优先从 mv-production/scripts/.env 读取 DOUBAO_SPEECH_API_KEY。
    兼容：若不存在则回退到仓库根目录 .env（仅兜底）。
    """
    script_env = Path(__file__).resolve().parent / ".env"
    root_env = Path(__file__).resolve().parents[3] / ".env"
    env_file = script_env if script_env.is_file() else root_env
    if not env_file.is_file():
        print("❌ 找不到 .env（已检查 mv-production/scripts/.env 与仓库根 .env）")
        print("请在 mv-production/scripts/.env 中设置 DOUBAO_SPEECH_API_KEY")
        sys.exit(1)
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("DOUBAO_SPEECH_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value
    print("❌ .env 中未找到 DOUBAO_SPEECH_API_KEY")
    sys.exit(1)


def http_post(url: str, headers: dict, body: str) -> tuple[str, dict]:
    req = Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    try:
        resp = urlopen(req, timeout=60)
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        return resp.read().decode("utf-8", errors="replace"), resp_headers
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"❌ HTTP {e.code} 响应: {err_body[:500]}")
        raise


def to_raw_base64(audio_input: str) -> str:
    """若为 data URL 则去掉前缀，只保留 base64 内容。"""
    s = audio_input.strip()
    if s.startswith("data:"):
        idx = s.find(",")
        if idx != -1:
            return s[idx + 1 :].strip()
    return s


def submit_task(api_key: str, audio_b64_or_data_url: str, request_id: str, audio_type: str) -> str:
    submit_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit?api_key=" + api_key
    raw_b64 = to_raw_base64(audio_b64_or_data_url)
    payload = {
        "audio": {"data": raw_b64, "type": audio_type},
        "request": {
            "modal_name": "bigmodel",
            "enable_emotion_detection": True,
            "enable_gender_detection": True,
            "enable_speaker_info": True,
            "enable_poi_fc": False,
            "use_itn": True,
            "use_punc": True,
        },
        "user": {"uid": "mv-production"},
    }
    body = json.dumps(payload, ensure_ascii=False)
    headers = {
        "Accept": "*/*",
        "x-api-key": api_key,
        "x-api-request-id": request_id,
        "x-api-resource-id": "volc.seedasr.auc",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
    }
    response, _ = http_post(submit_url, headers, body)
    if response.strip() in ("{}", ""):
        return request_id
    match = re.search(r'"(?:id|task_id)"\s*:\s*"([^"]*)"', response) or re.search(
        r'"(?:id|task_id)"\s*:\s*(\d+)', response
    )
    if match:
        return match.group(1)
    print("❌ 提交失败，响应:")
    print(response[:2000] if len(response) > 2000 else response)
    sys.exit(1)


def query_task(api_key: str, request_id: str) -> tuple[int, str]:
    query_url = f"https://openspeech.bytedance.com/api/v3/auc/bigmodel/query?api_key={api_key}"
    headers = {
        "Accept": "*/*",
        "x-api-key": api_key,
        "x-api-request-id": request_id,
        "x-api-resource-id": "volc.seedasr.auc",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
    }
    response, _ = http_post(query_url, headers, "{}")
    data = json.loads(response)
    code = data.get("code", -1)
    return code, response


def main() -> None:
    parser = argparse.ArgumentParser(description="火山引擎语音识别（异步）")
    parser.add_argument(
        "audio",
        nargs="?",
        default="",
        help="音频 data URL（base64）或 raw base64；过长时用 -f 从文件读取",
    )
    parser.add_argument("-f", "--audio-file", help="从文件读取 audio（data URL 或 base64），与 audio 二选一")
    parser.add_argument(
        "--audio-type",
        default="mp3",
        help="音频类型（默认 mp3）。若输入为 wav/m4a 等请手动指定。",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="asr_raw.json",
        help="输出 JSON 文件路径（默认: asr_raw.json）",
    )
    parser.add_argument("--poll-interval", type=float, default=5.0, help="轮询间隔秒数")
    parser.add_argument("--max-attempts", type=int, default=120, help="最大轮询次数（默认约 10 分钟）")
    args = parser.parse_args()

    if args.audio_file:
        audio = Path(args.audio_file).read_text(encoding="utf-8").strip()
    else:
        audio = (args.audio or "").strip()
    if not audio:
        print("❌ 请提供 audio 或使用 -f <文件> 从文件读取")
        sys.exit(1)

    api_key = load_api_key()
    request_id = str(uuid.uuid4())

    print("🎤 提交火山引擎转录任务...")
    submit_task(api_key, audio, request_id, args.audio_type)
    print("✅ 任务已提交")
    print("⏳ 等待转录完成...")

    for _ in range(args.max_attempts):
        time.sleep(args.poll_interval)
        code, response_text = query_task(api_key, request_id)
        try:
            data = json.loads(response_text)
            result = data.get("result") or {}
        except Exception:
            data = {}
            result = {}
        if isinstance(result, dict) and (result.get("additions") is not None or code == 0):
            out_path = Path(args.output)
            out_path.write_text(response_text, encoding="utf-8")
            utterances = (result.get("utterances") if isinstance(result, dict) else None) or []
            cnt = len(utterances) if isinstance(utterances, list) else len(re.findall(r'"text"', response_text))
            print(f"✅ 转录完成，已保存 {out_path}（utterances={cnt}）")
            return
        if code == 1000:
            print(".", end="", flush=True)
            continue
        if isinstance(result, dict) and "result" in data and (result.get("text") or "") == "":
            print(".", end="", flush=True)
            continue
        print("\n❌ 转录失败，响应:")
        print(response_text)
        sys.exit(1)

    print("\n❌ 超时，任务未完成")
    sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
#
# 火山引擎语音识别（异步模式）
#
# 用法: python volcengine_transcribe.py <audio_url>
# 输出: volcengine_result.json
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
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError


def get_project_root() -> Path:
    """脚本所在目录的上一级的上一级（项目根目录，.env 所在）。"""
    # 审核/scripts -> 审核 -> 项目根
    return Path(__file__).resolve().parent.parent.parent


def load_api_key() -> str:
    """从项目根目录或审核目录的 .env 读取 VOLCENGINE_API_KEY。"""
    env_file = get_project_root() / ".env"
    if not env_file.is_file():
        env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        print(f"❌ 找不到 .env（已检查项目根与审核目录）")
        print("请创建 .env 并填入 VOLCENGINE_API_KEY")
        sys.exit(1)
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("VOLCENGINE_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value
    print("❌ .env 中未找到 VOLCENGINE_API_KEY")
    sys.exit(1)


# def load_hot_words() -> list[str]:
#     """从 审核/字幕/词典.txt 加载热词列表。"""
#     script_dir = Path(__file__).resolve().parent
#     dict_file = script_dir.parent / "字幕" / "词典.txt"
#     if not dict_file.is_file():
#         return []
#     words = [
#         line.strip()
#         for line in dict_file.read_text(encoding="utf-8", errors="ignore").splitlines()
#         if line.strip()
#     ]
#     return words


def http_post(url: str, headers: dict, body: str) -> tuple[str, dict]:
    """发送 POST 请求，返回 (响应文本, 响应头字典)。"""
    req = Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    try:
        resp = urlopen(req, timeout=60)
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        return resp.read().decode("utf-8", errors="replace"), resp_headers
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"❌ HTTP {e.code} 响应: {err_body[:500]}")
        raise


def http_get(url: str, headers: dict) -> str:
    """发送 GET 请求，返回响应文本。"""
    req = Request(url, headers=headers, method="GET")
    resp = urlopen(req, timeout=30)
    return resp.read().decode("utf-8", errors="replace")


def to_raw_base64(audio_input: str) -> str:
    """若为 data URL 则去掉前缀，只保留 base64 内容。"""
    s = audio_input.strip()
    if s.startswith("data:"):
        # data:audio/mpeg;base64,xxxxx -> xxxxx
        idx = s.find(",")
        if idx != -1:
            return s[idx + 1 :].strip()
    return s


def submit_task(api_key: str, audio_url: str, hot_words: list[str], request_id: str) -> str:
    """提交转录任务。成功时接口返回 {}，用 request_id 作为轮询依据。"""
    submit_url = (
        "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
        "?api_key=" + api_key
    )
    raw_b64 = to_raw_base64(audio_url)
    payload = {
        "audio": {"data": raw_b64, "type": "mp3"},
        "request": {
            "modal_name": "bigmodel",
            "enable_emotion_detection": True,
            "enable_gender_detection": True,
            "enable_speaker_info": True,
            "enable_poi_fc": False,
            "use_itn": True,
            "use_punc": True,
        },
        "user": {
            "uid": "Speech Experience"
        },
    }
    if hot_words:
        payload["hot_words"] = hot_words
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
    match = re.search(r'"(?:id|task_id)"\s*:\s*"([^"]*)"', response)
    if not match:
        match = re.search(r'"(?:id|task_id)"\s*:\s*(\d+)', response)
    if match:
        return match.group(1)
    print("❌ 提交失败，响应:")
    print(response[:2000] if len(response) > 2000 else response)
    sys.exit(1)


def query_task(api_key: str, request_id: str) -> tuple[int, str]:
    """查询任务状态（按 request_id）。返回 (code, 完整响应文本)。"""
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
        "audio_url",
        nargs="?",
        default="",
        help="音频 URL 或 data URL（base64）；过长时用 -f 从文件读取",
    )
    parser.add_argument(
        "-f", "--audio-url-file",
        help="从文件读取音频 URL（如 base64 的 data URL），与 audio_url 二选一",
    )
    parser.add_argument(
        "-o", "--output",
        default="volcengine_result.json",
        help="输出 JSON 文件路径（默认: volcengine_result.json）",
    )
    args = parser.parse_args()
    if args.audio_url_file:
        audio_url = Path(args.audio_url_file).read_text(encoding="utf-8").strip()
    else:
        audio_url = (args.audio_url or "").strip()
    if not audio_url:
        print("❌ 请提供 audio_url 或使用 -f <文件> 从文件读取")
        sys.exit(1)

    api_key = load_api_key()

    print("🎤 提交火山引擎转录任务...")
    url_preview = audio_url[:80] + "..." if len(audio_url) > 80 else audio_url
    print(f"音频 URL: {url_preview}")

    hot_words: list[str] = []
    request_id = str(uuid.uuid4())
    submit_task(api_key, audio_url, hot_words, request_id)
    print("✅ 任务已提交")
    print("⏳ 等待转录完成...")

    max_attempts = 120  # 最多约 10 分钟（每 5 秒查一次）
    for attempt in range(max_attempts):
        time.sleep(5)
        code, response_text = query_task(api_key, request_id)
        try:
            data = json.loads(response_text)
            result = data.get("result") or {}
        except (json.JSONDecodeError, TypeError):
            data = {}
            result = {}
        # result 下存在 additions 则表明处理完成
        if isinstance(result, dict) and result.get("additions") is not None:
            out_path = Path(args.output)
            out_path.write_text(response_text, encoding="utf-8")
            print(f"✅ 转录完成，已保存 {out_path}")
            utterances = result.get("utterances") or []
            count = len(utterances) if isinstance(utterances, list) else len(re.findall(r'"text"', response_text))
            print(f"📝 识别到 {count} 段语音")
            return
        if code == 0:
            out_path = Path(args.output)
            out_path.write_text(response_text, encoding="utf-8")
            print(f"✅ 转录完成，已保存 {out_path}")
            utterances = data.get("result", {}).get("utterances") or []
            count = len(utterances) if isinstance(utterances, list) else len(re.findall(r'"text"', response_text))
            print(f"📝 识别到 {count} 段语音")
            return
        if code == 1000:
            print(".", end="", flush=True)
            continue
        # 未处理完成：result 无 additions 且 text 为空，继续轮询
        if isinstance(result, dict) and "result" in data and (result.get("text") or "") == "":
            print(".", end="", flush=True)
            continue
        print()
        print("❌ 转录失败，响应:")
        print(response_text)
        sys.exit(1)

    print()
    print("❌ 超时，任务未完成")
    sys.exit(1)


if __name__ == "__main__":
    main()

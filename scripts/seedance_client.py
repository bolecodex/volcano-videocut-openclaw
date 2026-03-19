#!/usr/bin/env python3
"""
Seedance 2.0 API Client

Shared async task client for all Seedance-powered skills.
Handles task creation, polling, and video download via the Ark content generation API.

API: POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from dotenv import load_dotenv


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_config() -> dict:
    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        print("ERROR: ARK_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    model = os.getenv("SEEDANCE_MODEL", "doubao-seedance-2-0-260128")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    return {"api_key": api_key, "model": model, "base_url": base_url}


def _api_request(method: str, url: str, api_key: str, data: dict | None = None) -> dict:
    """Make an authenticated API request to the Ark endpoint."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"  API error {e.code}: {error_body[:500]}", file=sys.stderr)
        raise RuntimeError(f"Seedance API error {e.code}: {error_body[:200]}")


def create_task(
    content: list[dict],
    model: str | None = None,
    duration: int = 8,
    ratio: str = "adaptive",
    resolution: str = "720p",
    generate_audio: bool = True,
    watermark: bool = False,
    tools: list[dict] | None = None,
) -> str:
    """
    Create a Seedance video generation task.
    Returns the task ID for polling.
    """
    cfg = _load_config()
    url = f"{cfg['base_url']}/contents/generations/tasks"
    model = model or cfg["model"]

    payload = {
        "model": model,
        "content": content,
        "duration": duration,
        "ratio": ratio,
        "resolution": resolution,
        "generate_audio": generate_audio,
        "watermark": watermark,
    }
    if tools:
        payload["tools"] = tools

    print(f"  Creating Seedance task (model={model}, dur={duration}s, ratio={ratio})...")
    result = _api_request("POST", url, cfg["api_key"], payload)

    task_id = result.get("id")
    if not task_id:
        raise RuntimeError(f"No task ID returned: {json.dumps(result)[:300]}")

    print(f"  Task created: {task_id}")
    return task_id


def poll_task(
    task_id: str,
    poll_interval: float = 10.0,
    max_wait: float = 600.0,
) -> dict:
    """
    Poll a Seedance task until it completes or fails.
    Returns the full task result dict.
    """
    cfg = _load_config()
    url = f"{cfg['base_url']}/contents/generations/tasks/{task_id}"

    start = time.time()
    attempt = 0
    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            raise TimeoutError(f"Task {task_id} timed out after {max_wait:.0f}s")

        attempt += 1
        result = _api_request("GET", url, cfg["api_key"])
        status = result.get("status", "unknown")

        if status == "succeeded":
            print(f"  Task succeeded in {elapsed:.0f}s")
            return result
        elif status == "failed":
            error = result.get("error", {})
            raise RuntimeError(f"Task failed: {json.dumps(error)[:300]}")
        else:
            print(f"  [{attempt}] Status: {status} ({elapsed:.0f}s elapsed)")
            time.sleep(poll_interval)


def download_video(task_result: dict, output_path: str) -> str:
    """Download the generated video from a completed task result."""
    content = task_result.get("content", {})
    video_url = None

    if isinstance(content, dict):
        video_url = content.get("video_url")
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "video_url":
                    video_url = item.get("video_url", {}).get("url")
                elif "video_url" in item:
                    video_url = item["video_url"] if isinstance(item["video_url"], str) else item["video_url"].get("url")
            if video_url:
                break

    if not video_url:
        for key in ("video", "output", "result"):
            if isinstance(content, dict) and key in content:
                candidate = content[key]
                if isinstance(candidate, str) and candidate.startswith("http"):
                    video_url = candidate
                    break
                elif isinstance(candidate, dict) and "url" in candidate:
                    video_url = candidate["url"]
                    break

    if not video_url:
        raise RuntimeError(f"No video URL found in task result: {json.dumps(task_result)[:500]}")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    print(f"  Downloading to {output_path}...")
    urllib.request.urlretrieve(video_url, output_path)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Downloaded: {size_mb:.1f}MB")
    return output_path


def generate_video(
    content: list[dict],
    output_path: str,
    model: str | None = None,
    duration: int = 8,
    ratio: str = "adaptive",
    resolution: str = "720p",
    generate_audio: bool = True,
    watermark: bool = False,
    tools: list[dict] | None = None,
    poll_interval: float = 10.0,
    max_wait: float = 600.0,
) -> str:
    """
    End-to-end: create task, poll until done, download result.
    Returns the output file path.
    """
    task_id = create_task(
        content=content,
        model=model,
        duration=duration,
        ratio=ratio,
        resolution=resolution,
        generate_audio=generate_audio,
        watermark=watermark,
        tools=tools,
    )
    result = poll_task(task_id, poll_interval, max_wait)
    return download_video(result, output_path)


def prepare_video_for_reference(video_path: str, max_duration: float = 15.0) -> str:
    """
    Trim and compress a video to meet Seedance reference input requirements:
    - Duration: [2, 15]s
    - Resolution: 480p or 720p
    - Size: <= 50MB
    Returns path to a conforming file (may be the original if already valid).
    """
    import subprocess
    import tempfile

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    duration = float(result.stdout.strip()) if result.returncode == 0 else 0

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if duration <= max_duration and size_mb <= 45:
        return video_path

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()

    trim_dur = min(duration, max_duration)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-t", str(trim_dur),
            "-vf", "scale='min(720,iw)':-2",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            tmp.name,
        ],
        capture_output=True, text=True,
    )
    print(f"  Prepared reference: {size_mb:.0f}MB/{duration:.0f}s -> {os.path.getsize(tmp.name)/(1024*1024):.1f}MB/{trim_dur:.0f}s")
    return tmp.name


def encode_image_data_uri(image_path: str) -> str:
    """Encode a local image as a data URI for the API."""
    import base64
    ext = Path(image_path).suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{ext};base64,{b64}"


def extract_frame(video_path: str, timestamp: float, output_path: str) -> str:
    """Extract a single frame from a video at the given timestamp."""
    import subprocess
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path, "-vframes", "1", "-q:v", "2", output_path],
        capture_output=True, text=True,
    )
    return output_path

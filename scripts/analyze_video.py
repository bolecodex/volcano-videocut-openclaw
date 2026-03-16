#!/usr/bin/env python3
"""
短剧视频跨集分析脚本
使用豆包 Seed 2.0 模型（通过火山引擎 Ark API）分析多集视频，
跨集提取主线剧情，输出统一的剪辑方案 JSON。

支持两种模式：
- 目录模式（默认）：分析目录下所有视频，输出一个跨集合并的 JSON
- 单文件模式：分析单个视频文件
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MAX_MB = 2  # single video analysis: keep small for reliable upload
MULTI_MAX_MB = 2  # per-video limit when sending multiple videos in one request
MAX_VIDEOS_PER_BATCH = 3  # max videos per API call to avoid payload/timeout issues


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_prompt(prompt_path: Path | None = None) -> str:
    if prompt_path is None:
        prompt_path = get_project_root() / "scripts" / "prompts" / "highlight_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def get_video_duration(video_path: str) -> str:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return "unknown"
    seconds = float(result.stdout.strip())
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_video_duration_seconds(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    return float(result.stdout.strip())


def get_video_size_mb(video_path: str) -> float:
    return os.path.getsize(video_path) / (1024 * 1024)


def compress_video(video_path: str, target_mb: float = DEFAULT_MAX_MB) -> str:
    """Compress video for API upload. Uses ultrafast preset and low resolution for speed."""
    size_mb = get_video_size_mb(video_path)
    if size_mb <= target_mb:
        return video_path

    if target_mb <= 2:
        scale = "scale='min(240,iw)':-2"
    elif target_mb <= 5:
        scale = "scale='min(360,iw)':-2"
    else:
        scale = "scale='min(480,iw)':-2"
    print(f"    Compressing ({size_mb:.0f}MB -> ~{target_mb}MB)...")

    duration_sec = get_video_duration_seconds(video_path)
    if duration_sec <= 0:
        duration_sec = 300

    target_bitrate_kbps = int((target_mb * 8 * 1024) / duration_sec * 0.85)
    audio_bitrate = 24 if target_mb <= 2 else 32
    video_bitrate = max(target_bitrate_kbps - audio_bitrate, 80)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()

    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", scale,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-b:v", f"{video_bitrate}k",
            "-c:a", "aac", "-b:a", f"{audio_bitrate}k", "-ac", "1",
            "-movflags", "+faststart",
            tmp.name,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"    Compression failed: {result.stderr[-200:]}", file=sys.stderr)
        os.unlink(tmp.name)
        return video_path

    new_size = get_video_size_mb(tmp.name)
    print(f"    Compressed: {size_mb:.0f}MB -> {new_size:.0f}MB")
    return tmp.name


def encode_video_base64(video_path: str) -> str:
    with open(video_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def create_client() -> OpenAI:
    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    if not api_key:
        print("ERROR: ARK_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    import httpx
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(1200.0, connect=60.0, write=600.0, read=1200.0),
        max_retries=3,
    )


def _parse_response(response) -> dict:
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("WARNING: Could not parse response as JSON, returning raw text", file=sys.stderr)
        return {"raw_response": content}


def _call_api_for_batch(
    client,
    model: str,
    video_paths: list[str],
    prompt: str,
    per_video_mb: float,
    batch_label: str = "",
) -> dict:
    """Send a batch of videos to the API and return parsed result."""
    content_parts = []
    temp_files = []
    video_info_lines = []
    total_duration = 0

    for vp in video_paths:
        name = Path(vp).stem
        duration = get_video_duration(vp)
        dur_sec = get_video_duration_seconds(vp)
        total_duration += dur_sec
        size_mb = get_video_size_mb(vp)
        print(f"  [{name}] {duration}, {size_mb:.0f}MB")

        compressed_path = compress_video(vp, per_video_mb)
        if compressed_path != vp:
            temp_files.append(compressed_path)

        print(f"    Encoding to base64...")
        video_b64 = encode_video_base64(compressed_path)
        b64_mb = len(video_b64) / (1024 * 1024)
        print(f"    Base64: {b64_mb:.0f}MB")

        content_parts.append({
            "type": "video_url",
            "video_url": {"url": f"data:video/mp4;base64,{video_b64}"},
        })
        video_info_lines.append(f"- {Path(vp).name}: 时长 {duration}")

    video_list_str = "\n".join(video_info_lines)
    user_prompt = (
        f"以下是 {len(video_paths)} 集短剧视频，请作为一个完整故事跨集分析：\n"
        f"{video_list_str}\n"
        f"所有视频总时长约 {int(total_duration)}秒 ({total_duration/60:.1f}分钟)\n\n"
        f"注意：每个视频的 source_file 字段请使用对应的文件名（不含路径，含扩展名）。\n\n"
        f"{prompt}"
    )
    content_parts.append({"type": "text", "text": user_prompt})

    label = f" {batch_label}" if batch_label else ""
    print(f"\n  Calling {model}{label}...")
    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=16384,
            temperature=0.2,
        )
        result = _parse_response(response)
    finally:
        for tf in temp_files:
            try:
                os.unlink(tf)
            except OSError:
                pass

    elapsed = time.time() - start_time
    print(f"  Batch completed in {elapsed:.1f}s")
    return result


def _merge_batch_results(batch_results: list[dict]) -> dict:
    """Merge multiple batch analysis results into a single combined result."""
    if len(batch_results) == 1:
        return batch_results[0]

    merged = {
        "drama_name": batch_results[0].get("drama_name", ""),
        "summary": "",
        "segments_to_keep": [],
        "segments_to_remove": [],
        "hook": {"enabled": False},
        "final_structure": {
            "segment_order": [],
            "estimated_duration_seconds": 0,
        },
    }

    summaries = []
    all_keep = []
    all_remove = []
    total_est = 0
    best_hook = None
    global_id = 1
    hook_old_to_new = {}

    for br in batch_results:
        if br.get("summary"):
            summaries.append(br["summary"])

        old_to_new = {}
        for seg in br.get("segments_to_keep", []):
            old_id = seg["id"]
            new_seg = dict(seg)
            new_seg["id"] = global_id
            old_to_new[old_id] = global_id
            all_keep.append(new_seg)
            global_id += 1

        all_remove.extend(br.get("segments_to_remove", []))

        fs = br.get("final_structure", {})
        total_est += fs.get("estimated_duration_seconds", 0)

        hook = br.get("hook", {})
        if hook.get("enabled") and not best_hook:
            best_hook = hook
            hook_old_to_new = old_to_new

    merged["summary"] = " ".join(summaries)
    merged["segments_to_keep"] = all_keep
    merged["segments_to_remove"] = all_remove
    merged["final_structure"]["estimated_duration_seconds"] = total_est
    if best_hook:
        merged["hook"] = best_hook

    segment_order = []
    if best_hook:
        segment_order.append({"type": "hook"})
    for seg in all_keep:
        segment_order.append({"type": "keep", "id": seg["id"]})
    merged["final_structure"]["segment_order"] = segment_order

    return merged


def analyze_multi_episode(
    video_paths: list[str],
    output_dir: str | None = None,
    model: str | None = None,
    prompt_path: str | None = None,
    output_name: str = "highlights_combined",
) -> dict:
    """
    Analyze multiple episodes together.
    Auto-batches when video count exceeds MAX_VIDEOS_PER_BATCH to avoid
    payload size / timeout issues, then merges batch results.
    """
    project_root = get_project_root()
    if output_dir is None:
        output_dir = str(project_root / "video" / "output")
    if model is None:
        load_dotenv(project_root / ".env")
        model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    os.makedirs(output_dir, exist_ok=True)
    prompt = load_prompt(Path(prompt_path) if prompt_path else None)
    client = create_client()

    n = len(video_paths)
    print(f"\n{'='*60}")
    print(f"Cross-episode analysis: {n} video(s)")
    print(f"{'='*60}")

    per_video_mb = MULTI_MAX_MB
    batch_size = min(n, MAX_VIDEOS_PER_BATCH)
    if batch_size > 3:
        per_video_mb = min(per_video_mb, max(3, 30 // batch_size))

    if n <= MAX_VIDEOS_PER_BATCH:
        result = _call_api_for_batch(client, model, video_paths, prompt, per_video_mb)
    else:
        batches = []
        for i in range(0, n, MAX_VIDEOS_PER_BATCH):
            batches.append(video_paths[i:i + MAX_VIDEOS_PER_BATCH])
        print(f"  Auto-splitting into {len(batches)} batches: {[len(b) for b in batches]}")

        batch_results = []
        for idx, batch in enumerate(batches, 1):
            print(f"\n  --- Batch {idx}/{len(batches)} ({len(batch)} videos) ---")
            br = _call_api_for_batch(
                client, model, batch, prompt, per_video_mb,
                batch_label=f"(batch {idx}/{len(batches)})",
            )
            batch_results.append(br)

            batch_path = os.path.join(output_dir, f"{output_name}_batch{idx}.json")
            with open(batch_path, "w", encoding="utf-8") as f:
                json.dump(br, f, ensure_ascii=False, indent=2)
            print(f"  Batch {idx} saved to: {batch_path}")

        print(f"\n  Merging {len(batch_results)} batch results...")
        result = _merge_batch_results(batch_results)

    output_path = os.path.join(output_dir, f"{output_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Results saved to: {output_path}")

    _print_summary(result)
    return result


def analyze_single_video(
    video_path: str,
    output_dir: str | None = None,
    model: str | None = None,
    prompt_path: str | None = None,
) -> dict:
    """Analyze a single video file."""
    project_root = get_project_root()
    if output_dir is None:
        output_dir = str(project_root / "video" / "output")
    if model is None:
        load_dotenv(project_root / ".env")
        model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    os.makedirs(output_dir, exist_ok=True)
    prompt = load_prompt(Path(prompt_path) if prompt_path else None)
    client = create_client()

    episode_name = Path(video_path).stem
    print(f"\n{'='*60}")
    print(f"Analyzing: {episode_name}")
    print(f"{'='*60}")

    compressed_path = compress_video(video_path, DEFAULT_MAX_MB)
    is_temp = compressed_path != video_path

    try:
        duration = get_video_duration(video_path)
        print(f"  Encoding to base64...")
        video_b64 = encode_video_base64(compressed_path)
        b64_mb = len(video_b64) / (1024 * 1024)
        print(f"  Base64: {b64_mb:.0f}MB")

        user_prompt = (
            f"视频文件: {Path(video_path).name}\n"
            f"视频时长: {duration}\n"
            f"注意: source_file 请使用 \"{Path(video_path).name}\"。\n\n"
            f"{prompt}"
        )

        print(f"  Calling {model}...")
        start_time = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{video_b64}"}},
                    {"type": "text", "text": user_prompt},
                ],
            }],
            max_tokens=8192,
            temperature=0.2,
        )
        result = _parse_response(response)
        elapsed = time.time() - start_time
        print(f"  Analysis completed in {elapsed:.1f}s")
    finally:
        if is_temp:
            os.unlink(compressed_path)

    output_path = os.path.join(output_dir, f"highlights_{episode_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Results saved to: {output_path}")

    _print_summary(result)
    return result


def _print_summary(result: dict):
    if "raw_response" in result:
        print(f"  Raw response (first 500 chars): {result['raw_response'][:500]}")
        return

    segments = result.get("segments_to_keep", [])
    hook = result.get("hook", {})
    final = result.get("final_structure", {})
    print(f"\n  Summary: {result.get('summary', 'N/A')[:200]}")
    print(f"  Segments to keep: {len(segments)}")
    for s in segments:
        src = s.get("source_file", "?")
        print(f"    [{s['id']}] {src} {s['start_time']}-{s['end_time']} ({s.get('duration_seconds', '?')}s) {s.get('content', '')[:50]}")
    if hook.get("enabled"):
        print(f"  Hook: {hook.get('source_file', '?')} {hook.get('source_start')}-{hook.get('source_end')}")
    est = final.get("estimated_duration_seconds", "?")
    print(f"  Estimated output: {est}s")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze short drama videos for cross-episode promotional editing"
    )
    parser.add_argument(
        "input",
        help="Path to a video file or directory of video files",
    )
    parser.add_argument(
        "-o", "--output-dir",
        help="Directory to save analysis results (default: video/output/)",
    )
    parser.add_argument(
        "-m", "--model",
        help="Model name or endpoint ID (default: from .env ARK_MODEL_NAME)",
    )
    parser.add_argument(
        "--prompt",
        help="Path to custom prompt template file",
    )
    parser.add_argument(
        "--name",
        default="highlights_combined",
        help="Output JSON file name (without .json extension)",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Analyze each video separately instead of cross-episode",
    )
    args = parser.parse_args()

    input_path = Path(args.input)

    if input_path.is_dir():
        video_files = sorted(
            p for p in input_path.iterdir()
            if p.suffix.lower() in {".mp4", ".mov", ".mpeg", ".webm", ".avi"}
        )
        if not video_files:
            print(f"No video files found in {args.input}")
            sys.exit(1)

        print(f"Found {len(video_files)} video(s)")

        if args.single:
            for vf in video_files:
                analyze_single_video(str(vf), args.output_dir, args.model, args.prompt)
        else:
            analyze_multi_episode(
                [str(vf) for vf in video_files],
                args.output_dir, args.model, args.prompt, args.name,
            )
    elif input_path.is_file():
        analyze_single_video(str(input_path), args.output_dir, args.model, args.prompt)
    else:
        print(f"ERROR: {args.input} is not a valid file or directory", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

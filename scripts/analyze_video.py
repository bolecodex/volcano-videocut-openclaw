#!/usr/bin/env python3
"""
短剧视频跨集分析脚本 (S-Level Enhanced)

使用豆包 Seed 2.0 模型（通过火山引擎 Ark API）分析多集视频，
跨集提取主线剧情，输出统一的剪辑方案 JSON。

增强功能：
- 高清分析：480p / 10-15MB 视频输入，大幅提升画面识别精度
- 关键帧采样模式：超长视频可用图片序列 + ASR 文本替代低质量视频
- 多轮精修：第一轮粗分析 → 第二轮精细切点校验
- ASR 辅助：自动加载台词文本辅助精确切点定位
- 多版本输出：一次分析生成激进/标准/保守三个版本方案
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

DEFAULT_MAX_MB = 12
MULTI_MAX_MB = 8
MAX_VIDEOS_PER_BATCH = 3
KEYFRAME_INTERVAL_SEC = 2
KEYFRAME_MAX_FRAMES = 60


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
    """Compress video for API upload with quality-preserving settings."""
    size_mb = get_video_size_mb(video_path)
    if size_mb <= target_mb:
        return video_path

    if target_mb <= 3:
        scale = "scale='min(360,iw)':-2"
    elif target_mb <= 8:
        scale = "scale='min(480,iw)':-2"
    else:
        scale = "scale='min(720,iw)':-2"
    print(f"    Compressing ({size_mb:.0f}MB -> ~{target_mb}MB, {'480p' if target_mb <= 8 else '720p'})...")

    duration_sec = get_video_duration_seconds(video_path)
    if duration_sec <= 0:
        duration_sec = 300

    target_bitrate_kbps = int((target_mb * 8 * 1024) / duration_sec * 0.85)
    audio_bitrate = 48 if target_mb >= 8 else 32
    video_bitrate = max(target_bitrate_kbps - audio_bitrate, 150)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()

    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", scale,
            "-c:v", "libx264", "-preset", "fast",
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
    print(f"    Compressed: {size_mb:.0f}MB -> {new_size:.1f}MB")
    return tmp.name


def extract_keyframes(video_path: str, output_dir: str, interval_sec: float = KEYFRAME_INTERVAL_SEC) -> list[dict]:
    """Extract keyframes as images with timestamps for frame-based analysis."""
    os.makedirs(output_dir, exist_ok=True)
    duration = get_video_duration_seconds(video_path)
    if duration <= 0:
        return []

    effective_interval = max(interval_sec, duration / KEYFRAME_MAX_FRAMES)
    pattern = os.path.join(output_dir, "frame_%05d.jpg")

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps=1/{effective_interval},scale='min(720,iw)':-2",
            "-q:v", "3",
            pattern,
        ],
        capture_output=True, text=True,
    )

    frames = []
    for f in sorted(Path(output_dir).glob("frame_*.jpg")):
        idx = int(f.stem.split("_")[1]) - 1
        ts = idx * effective_interval
        h, m, s = int(ts // 3600), int((ts % 3600) // 60), int(ts % 60)
        frames.append({
            "path": str(f),
            "timestamp": f"{h:02d}:{m:02d}:{s:02d}",
            "seconds": ts,
        })
    print(f"    Extracted {len(frames)} keyframes (every {effective_interval:.1f}s)")
    return frames


def encode_video_base64(video_path: str) -> str:
    with open(video_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def load_asr_transcript(video_path: str, output_dir: str | None = None) -> str | None:
    """Try to load pre-existing ASR transcript for a video."""
    stem = Path(video_path).stem
    search_dirs = []
    if output_dir:
        search_dirs.append(output_dir)
    search_dirs.append(str(Path(video_path).parent))
    search_dirs.append(str(get_project_root() / "video" / "output"))

    for d in search_dirs:
        for suffix in [f"asr_{stem}.json", f"{stem}_asr.json", f"asr_{stem}.txt"]:
            candidate = os.path.join(d, suffix)
            if os.path.exists(candidate):
                print(f"    Found ASR transcript: {candidate}")
                with open(candidate, "r", encoding="utf-8") as f:
                    content = f.read()
                if candidate.endswith(".json"):
                    try:
                        data = json.loads(content)
                        if isinstance(data, list):
                            lines = [f"[{item.get('start', '?')}-{item.get('end', '?')}] {item.get('text', '')}" for item in data]
                            return "\n".join(lines)
                        elif isinstance(data, dict) and "utterances" in data:
                            lines = [f"[{u.get('start_time', '?')}-{u.get('end_time', '?')}] {u.get('text', '')}" for u in data["utterances"]]
                            return "\n".join(lines)
                    except json.JSONDecodeError:
                        pass
                return content
    return None


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


def _build_asr_context(video_paths: list[str], output_dir: str | None) -> str:
    """Build ASR transcript context for all videos."""
    asr_sections = []
    for vp in video_paths:
        transcript = load_asr_transcript(vp, output_dir)
        if transcript:
            name = Path(vp).name
            asr_sections.append(f"\n### {name} 台词文本\n{transcript}")
    if asr_sections:
        header = "\n\n## ASR 台词参考（精确到秒的对白文本，用于辅助切点定位）\n"
        return header + "\n".join(asr_sections)
    return ""


def _call_api_for_batch(
    client,
    model: str,
    video_paths: list[str],
    prompt: str,
    per_video_mb: float,
    batch_label: str = "",
    output_dir: str | None = None,
    use_keyframes: bool = False,
    multi_version: bool = False,
) -> dict:
    """Send a batch of videos to the API and return parsed result."""
    content_parts = []
    temp_files = []
    temp_dirs = []
    video_info_lines = []
    total_duration = 0

    for vp in video_paths:
        name = Path(vp).stem
        duration = get_video_duration(vp)
        dur_sec = get_video_duration_seconds(vp)
        total_duration += dur_sec
        size_mb = get_video_size_mb(vp)
        print(f"  [{name}] {duration}, {size_mb:.0f}MB")

        if use_keyframes:
            kf_dir = tempfile.mkdtemp(prefix="kf_")
            temp_dirs.append(kf_dir)
            frames = extract_keyframes(vp, kf_dir)
            for frame in frames:
                img_b64 = encode_image_base64(frame["path"])
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                })
            video_info_lines.append(f"- {Path(vp).name}: 时长 {duration} ({len(frames)} 帧截图)")
        else:
            compressed_path = compress_video(vp, per_video_mb)
            if compressed_path != vp:
                temp_files.append(compressed_path)

            print(f"    Encoding to base64...")
            video_b64 = encode_video_base64(compressed_path)
            b64_mb = len(video_b64) / (1024 * 1024)
            print(f"    Base64: {b64_mb:.1f}MB")

            content_parts.append({
                "type": "video_url",
                "video_url": {"url": f"data:video/mp4;base64,{video_b64}"},
            })
            video_info_lines.append(f"- {Path(vp).name}: 时长 {duration}")

    asr_context = _build_asr_context(video_paths, output_dir)

    video_list_str = "\n".join(video_info_lines)
    mode_note = "（关键帧截图模式）" if use_keyframes else ""
    user_prompt = (
        f"以下是 {len(video_paths)} 集短剧视频{mode_note}，请作为一个完整故事跨集分析：\n"
        f"{video_list_str}\n"
        f"所有视频总时长约 {int(total_duration)}秒 ({total_duration/60:.1f}分钟)\n\n"
        f"注意：每个视频的 source_file 字段请使用对应的文件名（不含路径，含扩展名）。\n"
    )

    if asr_context:
        user_prompt += asr_context + "\n\n请结合台词文本确定精确切点，确保每个切点都在完整台词结束后。\n\n"

    if multi_version:
        user_prompt += (
            "\n\n## 多版本要求\n"
            "请输出 3 个剪辑版本方案：\n"
            "1. **激进版** (aggressive): 节奏最快，只保留核心冲突和高潮，目标时长为原片的 30-40%\n"
            "2. **标准版** (standard): 平衡节奏，保留完整主线，目标时长为原片的 50-60%\n"
            "3. **保守版** (conservative): 保留更多细节和铺垫，目标时长为原片的 65-75%\n\n"
            "在 JSON 输出中增加 `versions` 数组，每个版本包含独立的 segments_to_keep、hook 和 final_structure。\n"
            "同时保留一个默认的顶层方案（标准版）。\n\n"
        )

    user_prompt += prompt
    content_parts.append({"type": "text", "text": user_prompt})

    label = f" {batch_label}" if batch_label else ""
    print(f"\n  Calling {model}{label}...")
    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=32768 if multi_version else 16384,
            temperature=0.1,
        )
        result = _parse_response(response)
    finally:
        for tf in temp_files:
            try:
                os.unlink(tf)
            except OSError:
                pass
        for td in temp_dirs:
            try:
                import shutil
                shutil.rmtree(td, ignore_errors=True)
            except OSError:
                pass

    elapsed = time.time() - start_time
    print(f"  Batch completed in {elapsed:.1f}s")
    return result


def _refine_cut_points(
    client,
    model: str,
    video_paths: list[str],
    coarse_result: dict,
    output_dir: str | None = None,
) -> dict:
    """Second-pass refinement: verify and adjust cut points using ASR data."""
    asr_context = _build_asr_context(video_paths, output_dir)
    if not asr_context:
        print("  [Refine] No ASR data available, skipping refinement pass")
        return coarse_result

    segments = coarse_result.get("segments_to_keep", [])
    if not segments:
        return coarse_result

    print(f"\n  [Refine] Verifying {len(segments)} cut points against ASR transcript...")

    segment_summary = json.dumps(segments, ensure_ascii=False, indent=2)
    refine_prompt = (
        "你是一位专业的短剧剪辑切点校验师。\n\n"
        "以下是第一轮分析得到的保留片段列表和 ASR 台词文本。\n"
        "请逐一检查每个片段的 start_time 和 end_time，确保：\n"
        "1. 切入点在一句完整台词开始之前（不切在说话中途）\n"
        "2. 切出点在一句完整台词结束之后（不切在说话中途）\n"
        "3. 如果发现切点不精确，调整到最近的台词边界\n"
        "4. 调整幅度通常在 +-2 秒以内\n\n"
        f"## 当前片段列表\n```json\n{segment_summary}\n```\n"
        f"{asr_context}\n\n"
        "请返回修正后的完整片段列表 JSON 数组（格式不变，只调整时间戳）。\n"
        "如果某个片段无需调整，保持原样。只返回 JSON 数组。"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": refine_prompt}],
            max_tokens=8192,
            temperature=0.05,
        )
        refined = _parse_response(response)

        if isinstance(refined, list):
            coarse_result["segments_to_keep"] = refined
            coarse_result["_refinement"] = "cut_points_verified"
            adjustments = sum(1 for r, o in zip(refined, segments)
                             if r.get("start_time") != o.get("start_time") or r.get("end_time") != o.get("end_time"))
            print(f"  [Refine] Adjusted {adjustments}/{len(segments)} cut points")
        elif isinstance(refined, dict) and "segments_to_keep" in refined:
            coarse_result["segments_to_keep"] = refined["segments_to_keep"]
            coarse_result["_refinement"] = "cut_points_verified"
        else:
            print("  [Refine] Unexpected response format, keeping original cut points")
    except Exception as e:
        print(f"  [Refine] Refinement failed: {e}, keeping original cut points")

    return coarse_result


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

    for br in batch_results:
        if br.get("summary"):
            summaries.append(br["summary"])

        for seg in br.get("segments_to_keep", []):
            new_seg = dict(seg)
            new_seg["id"] = global_id
            all_keep.append(new_seg)
            global_id += 1

        all_remove.extend(br.get("segments_to_remove", []))

        fs = br.get("final_structure", {})
        total_est += fs.get("estimated_duration_seconds", 0)

        hook = br.get("hook", {})
        if hook.get("enabled") and not best_hook:
            best_hook = hook

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

    all_versions = []
    for br in batch_results:
        all_versions.extend(br.get("versions", []))
    if all_versions:
        merged["versions"] = all_versions

    return merged


def analyze_multi_episode(
    video_paths: list[str],
    output_dir: str | None = None,
    model: str | None = None,
    prompt_path: str | None = None,
    output_name: str = "highlights_combined",
    use_keyframes: bool = False,
    multi_version: bool = False,
    refine: bool = True,
) -> dict:
    """
    Analyze multiple episodes together with S-level quality.
    Auto-batches when video count exceeds MAX_VIDEOS_PER_BATCH,
    optionally runs multi-pass refinement.
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
    print(f"Cross-episode analysis (S-Level): {n} video(s)")
    print(f"  Mode: {'keyframes' if use_keyframes else 'video'}")
    print(f"  Multi-version: {multi_version}")
    print(f"  Refinement: {refine}")
    print(f"{'='*60}")

    per_video_mb = MULTI_MAX_MB

    if n <= MAX_VIDEOS_PER_BATCH:
        result = _call_api_for_batch(
            client, model, video_paths, prompt, per_video_mb,
            output_dir=output_dir, use_keyframes=use_keyframes,
            multi_version=multi_version,
        )
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
                output_dir=output_dir, use_keyframes=use_keyframes,
                multi_version=multi_version,
            )
            batch_results.append(br)

            batch_path = os.path.join(output_dir, f"{output_name}_batch{idx}.json")
            with open(batch_path, "w", encoding="utf-8") as f:
                json.dump(br, f, ensure_ascii=False, indent=2)
            print(f"  Batch {idx} saved to: {batch_path}")

        print(f"\n  Merging {len(batch_results)} batch results...")
        result = _merge_batch_results(batch_results)

    if refine:
        result = _refine_cut_points(client, model, video_paths, result, output_dir)

    episodes = [Path(vp).name for vp in video_paths]
    if "episodes" not in result:
        result["episodes"] = episodes
    total_dur = sum(get_video_duration_seconds(vp) for vp in video_paths)
    if "total_source_duration_seconds" not in result:
        result["total_source_duration_seconds"] = round(total_dur)

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
    use_keyframes: bool = False,
    multi_version: bool = False,
    refine: bool = True,
) -> dict:
    """Analyze a single video file with S-level quality."""
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
    print(f"Analyzing (S-Level): {episode_name}")
    print(f"{'='*60}")

    if use_keyframes:
        result = _call_api_for_batch(
            client, model, [video_path], prompt, DEFAULT_MAX_MB,
            output_dir=output_dir, use_keyframes=True,
            multi_version=multi_version,
        )
    else:
        compressed_path = compress_video(video_path, DEFAULT_MAX_MB)
        is_temp = compressed_path != video_path

        try:
            duration = get_video_duration(video_path)
            print(f"  Encoding to base64...")
            video_b64 = encode_video_base64(compressed_path)
            b64_mb = len(video_b64) / (1024 * 1024)
            print(f"  Base64: {b64_mb:.1f}MB")

            asr_context = _build_asr_context([video_path], output_dir)

            user_prompt = (
                f"视频文件: {Path(video_path).name}\n"
                f"视频时长: {duration}\n"
                f"注意: source_file 请使用 \"{Path(video_path).name}\"。\n"
            )
            if asr_context:
                user_prompt += asr_context + "\n\n请结合台词文本确定精确切点。\n\n"
            if multi_version:
                user_prompt += (
                    "\n## 多版本要求\n"
                    "请输出激进版/标准版/保守版 3 个剪辑方案。\n\n"
                )
            user_prompt += prompt

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
                max_tokens=32768 if multi_version else 16384,
                temperature=0.1,
            )
            result = _parse_response(response)
            elapsed = time.time() - start_time
            print(f"  Analysis completed in {elapsed:.1f}s")
        finally:
            if is_temp:
                os.unlink(compressed_path)

    if refine:
        result = _refine_cut_points(client, model, [video_path], result, output_dir)

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
    if result.get("_refinement"):
        print(f"  Refinement: {result['_refinement']}")
    versions = result.get("versions", [])
    if versions:
        print(f"  Versions: {len(versions)}")
        for v in versions:
            vname = v.get("name", v.get("type", "?"))
            vsegs = len(v.get("segments_to_keep", []))
            vdur = v.get("final_structure", {}).get("estimated_duration_seconds", "?")
            print(f"    - {vname}: {vsegs} segments, ~{vdur}s")


def main():
    parser = argparse.ArgumentParser(
        description="S-Level short drama video analysis for promotional editing"
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
    parser.add_argument(
        "--keyframes",
        action="store_true",
        help="Use keyframe extraction mode (images + ASR) instead of video upload",
    )
    parser.add_argument(
        "--multi-version",
        action="store_true",
        help="Generate 3 versions: aggressive, standard, conservative",
    )
    parser.add_argument(
        "--no-refine",
        action="store_true",
        help="Skip the second-pass cut point refinement",
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
                analyze_single_video(
                    str(vf), args.output_dir, args.model, args.prompt,
                    use_keyframes=args.keyframes, multi_version=args.multi_version,
                    refine=not args.no_refine,
                )
        else:
            analyze_multi_episode(
                [str(vf) for vf in video_files],
                args.output_dir, args.model, args.prompt, args.name,
                use_keyframes=args.keyframes, multi_version=args.multi_version,
                refine=not args.no_refine,
            )
    elif input_path.is_file():
        analyze_single_video(
            str(input_path), args.output_dir, args.model, args.prompt,
            use_keyframes=args.keyframes, multi_version=args.multi_version,
            refine=not args.no_refine,
        )
    else:
        print(f"ERROR: {args.input} is not a valid file or directory", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
FFmpeg 视频切片合并脚本
支持跨集剪辑：从多个源视频文件中切取段落，合并成一个素材视频。
每个 segment 通过 source_file 指定来自哪个源视频。

切割默认使用 stream copy（极快），仅在合并阶段重编码以确保拼接流畅。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def time_to_seconds(t: str) -> float:
    parts = t.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def run_ffmpeg(args: list[str], desc: str = "") -> bool:
    cmd = ["ffmpeg", "-y"] + args
    if desc:
        print(f"  {desc}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[-500:]}", file=sys.stderr)
        return False
    return True


def cut_segment(
    source_video: str,
    start_time: str,
    end_time: str,
    output_path: str,
) -> bool:
    """Cut a segment using stream copy (fast, no re-encoding)."""
    start_sec = time_to_seconds(start_time)
    end_sec = time_to_seconds(end_time)
    duration = end_sec - start_sec

    if duration <= 0:
        print(f"  WARNING: Invalid segment {start_time}-{end_time}, skipping", file=sys.stderr)
        return False

    args = [
        "-ss", str(start_sec),
        "-i", source_video,
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]
    return run_ffmpeg(args, f"Cut {Path(source_video).name} {start_time}->{end_time} ({duration:.0f}s)")


def concat_segments(segment_files: list[str], output_path: str) -> bool:
    """Concatenate segments with re-encoding for seamless joins across different sources."""
    if not segment_files:
        print("  No segments to concatenate", file=sys.stderr)
        return False

    if len(segment_files) == 1:
        shutil.copy2(segment_files[0], output_path)
        print(f"  Single segment, copied to {Path(output_path).name}")
        return True

    filter_parts = []
    inputs = []
    for i, seg in enumerate(segment_files):
        inputs.extend(["-i", seg])
        filter_parts.append(f"[{i}:v:0][{i}:a:0]")
    filter_str = "".join(filter_parts) + f"concat=n={len(segment_files)}:v=1:a=1[outv][outa]"
    args = inputs + [
        "-filter_complex", filter_str,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    return run_ffmpeg(args, f"Merging {len(segment_files)} segments -> {Path(output_path).name}")


def resolve_source_path(source_file: str, video_dir: str) -> str:
    """Resolve source_file to an absolute path, searching in video_dir."""
    if os.path.isabs(source_file) and os.path.exists(source_file):
        return source_file
    candidate = os.path.join(video_dir, source_file)
    if os.path.exists(candidate):
        return candidate
    candidate = os.path.join(video_dir, os.path.basename(source_file))
    if os.path.exists(candidate):
        return candidate
    return source_file


def process_combined(
    analysis_json: str,
    video_dir: str,
    output_dir: str | None = None,
    output_name: str | None = None,
) -> str | None:
    """
    Process a cross-episode analysis JSON.
    Each segment has a source_file field pointing to the video it came from.
    """
    project_root = get_project_root()
    if output_dir is None:
        output_dir = str(project_root / "video" / "output")
    os.makedirs(output_dir, exist_ok=True)

    with open(analysis_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments_to_keep", [])
    if not segments:
        print("ERROR: No segments_to_keep found", file=sys.stderr)
        return None

    hook = data.get("hook", {})
    hook_enabled = hook.get("enabled", False)
    final_structure = data.get("final_structure", {})
    drama_name = data.get("drama_name", "combined")

    print(f"\n{'='*60}")
    print(f"Cross-episode cut: {drama_name}")
    print(f"Segments to keep: {len(segments)}")
    if hook_enabled:
        print(f"Hook: {hook.get('source_file')} {hook.get('source_start')}->{hook.get('source_end')}")
    print(f"{'='*60}")

    temp_dir = os.path.join(output_dir, "_temp_segments")
    os.makedirs(temp_dir, exist_ok=True)

    segment_order = final_structure.get("segment_order", [])
    if not segment_order:
        if hook_enabled:
            segment_order = [{"type": "hook"}] + [{"type": "keep", "id": s["id"]} for s in segments]
        else:
            segment_order = [{"type": "keep", "id": s["id"]} for s in segments]

    segments_by_id = {s["id"]: s for s in segments}
    cut_files = []
    total_dur = 0

    for idx, entry in enumerate(segment_order):
        seg_type = entry.get("type")

        if seg_type == "hook" and hook_enabled:
            src = resolve_source_path(hook["source_file"], video_dir)
            seg_path = os.path.join(temp_dir, f"seg_hook.mp4")
            ok = cut_segment(src, hook["source_start"], hook["source_end"], seg_path)
            if ok:
                cut_files.append(seg_path)
                total_dur += time_to_seconds(hook["source_end"]) - time_to_seconds(hook["source_start"])

        elif seg_type == "keep":
            sid = entry.get("id")
            seg = segments_by_id.get(sid)
            if seg is None:
                print(f"  WARNING: Segment ID {sid} not found, skipping")
                continue
            src = resolve_source_path(seg["source_file"], video_dir)
            seg_path = os.path.join(temp_dir, f"seg_{sid:03d}.mp4")
            ok = cut_segment(src, seg["start_time"], seg["end_time"], seg_path)
            if ok:
                cut_files.append(seg_path)
                total_dur += time_to_seconds(seg["end_time"]) - time_to_seconds(seg["start_time"])
            else:
                print(f"  WARNING: Failed to cut segment {sid}")

    if not cut_files:
        print("ERROR: All cuts failed", file=sys.stderr)
        return None

    print(f"\n  Total: {len(cut_files)} segments, {total_dur:.0f}s ({total_dur/60:.1f}min)")

    safe_name = output_name or drama_name.replace(" ", "_").replace("/", "_")
    output_path = os.path.join(output_dir, f"promo_{safe_name}.mp4")
    ok = concat_segments(cut_files, output_path)

    for sf in cut_files:
        try:
            os.unlink(sf)
        except OSError:
            pass
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass

    if ok:
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n  Output: {output_path} ({size_mb:.1f} MB)")
        return output_path
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Cut and merge video based on cross-episode analysis JSON"
    )
    parser.add_argument(
        "analysis_json",
        help="Path to the analysis JSON file",
    )
    parser.add_argument(
        "video_dir",
        help="Directory containing the source video files",
    )
    parser.add_argument(
        "-o", "--output-dir",
        help="Output directory (default: video/output/)",
    )
    parser.add_argument(
        "-n", "--name",
        help="Output file name (without extension)",
    )
    args = parser.parse_args()

    process_combined(args.analysis_json, args.video_dir, args.output_dir, args.name)


if __name__ == "__main__":
    main()

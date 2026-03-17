#!/usr/bin/env python3
"""
场景切割检测脚本

使用 FFmpeg 的场景变化检测滤镜识别视频中的场景切换点，
输出场景边界时间戳和代表帧截图。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_video_duration_seconds(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    return float(result.stdout.strip())


def seconds_to_hms(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def detect_scenes(
    video_path: str,
    threshold: float = 0.3,
    min_scene_duration: float = 2.0,
) -> list[dict]:
    """Detect scene changes using FFmpeg's scene filter."""
    print(f"  Detecting scenes (threshold={threshold})...")

    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_frames",
            "-select_streams", "v:0",
            "-of", "json",
            "-f", "lavfi",
            f"movie={video_path},select='gt(scene\\,{threshold})'",
        ],
        capture_output=True, text=True,
        timeout=300,
    )

    scene_times = []

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            for frame in data.get("frames", []):
                pts = float(frame.get("pts_time", frame.get("pkt_pts_time", 0)))
                scene_times.append(pts)
        except (json.JSONDecodeError, ValueError):
            pass

    if not scene_times:
        print("  Falling back to scene detection via stderr...")
        result2 = subprocess.run(
            [
                "ffmpeg", "-i", video_path,
                "-vf", f"select='gt(scene,{threshold})',showinfo",
                "-f", "null", "-",
            ],
            capture_output=True, text=True,
            timeout=300,
        )
        for line in result2.stderr.split("\n"):
            if "pts_time:" in line:
                try:
                    pts_part = line.split("pts_time:")[1].strip().split()[0]
                    scene_times.append(float(pts_part))
                except (ValueError, IndexError):
                    pass

    filtered = []
    prev_time = -min_scene_duration
    for t in sorted(scene_times):
        if t - prev_time >= min_scene_duration:
            filtered.append(t)
            prev_time = t

    return [{"timestamp": seconds_to_hms(t), "seconds": round(t, 2)} for t in filtered]


def extract_scene_thumbnails(
    video_path: str,
    scenes: list[dict],
    output_dir: str,
) -> list[dict]:
    """Extract a representative frame for each scene boundary."""
    thumb_dir = os.path.join(output_dir, "scene_thumbs")
    os.makedirs(thumb_dir, exist_ok=True)

    for i, scene in enumerate(scenes):
        ts = scene["seconds"]
        thumb_path = os.path.join(thumb_dir, f"scene_{i:03d}_{ts:.0f}s.jpg")
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(ts),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "3",
                "-vf", "scale='min(640,iw)':-2",
                thumb_path,
            ],
            capture_output=True, text=True,
        )
        if os.path.exists(thumb_path):
            scene["thumbnail"] = thumb_path
        else:
            scene["thumbnail"] = None

    return scenes


def process_video(
    video_path: str,
    output_dir: str | None = None,
    threshold: float = 0.3,
    min_duration: float = 2.0,
    thumbnails: bool = True,
) -> dict:
    """Full scene detection pipeline for a single video."""
    project_root = get_project_root()
    if output_dir is None:
        output_dir = str(project_root / "video" / "output")
    os.makedirs(output_dir, exist_ok=True)

    stem = Path(video_path).stem
    duration = get_video_duration_seconds(video_path)

    print(f"\n{'='*60}")
    print(f"Scene Detection: {Path(video_path).name} ({duration:.0f}s)")
    print(f"{'='*60}")

    scenes = detect_scenes(video_path, threshold, min_duration)

    if not scenes:
        print("  No scene changes detected")
        all_scenes = [{"timestamp": "00:00:00.00", "seconds": 0.0}]
    else:
        all_scenes = [{"timestamp": "00:00:00.00", "seconds": 0.0}] + scenes

    for i in range(len(all_scenes)):
        if i + 1 < len(all_scenes):
            all_scenes[i]["end_seconds"] = all_scenes[i + 1]["seconds"]
        else:
            all_scenes[i]["end_seconds"] = round(duration, 2)
        all_scenes[i]["duration"] = round(all_scenes[i]["end_seconds"] - all_scenes[i]["seconds"], 2)
        all_scenes[i]["scene_id"] = i + 1

    if thumbnails:
        all_scenes = extract_scene_thumbnails(video_path, all_scenes, output_dir)

    result = {
        "video": Path(video_path).name,
        "total_duration": round(duration, 2),
        "scene_count": len(all_scenes),
        "threshold": threshold,
        "scenes": all_scenes,
    }

    json_path = os.path.join(output_dir, f"scenes_{stem}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {json_path}")
    print(f"  Scenes: {len(all_scenes)} (avg {duration/max(len(all_scenes),1):.1f}s each)")

    return result


def main():
    parser = argparse.ArgumentParser(description="Detect scene changes in video files")
    parser.add_argument("input", help="Video file or directory")
    parser.add_argument("-o", "--output-dir", help="Output directory")
    parser.add_argument("-t", "--threshold", type=float, default=0.3, help="Scene change threshold (0-1)")
    parser.add_argument("--min-duration", type=float, default=2.0, help="Minimum scene duration in seconds")
    parser.add_argument("--no-thumbnails", action="store_true", help="Skip thumbnail extraction")
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
        for vf in video_files:
            process_video(str(vf), args.output_dir, args.threshold, args.min_duration, not args.no_thumbnails)
    elif input_path.is_file():
        process_video(str(input_path), args.output_dir, args.threshold, args.min_duration, not args.no_thumbnails)
    else:
        print(f"ERROR: {args.input} not found", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

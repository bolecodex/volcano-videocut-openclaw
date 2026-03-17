#!/usr/bin/env python3
"""
多平台规格导出脚本

一键将视频导出为多个平台所需的不同规格：
- 抖音/快手: 竖屏 9:16, 1080x1920
- 微信视频号: 竖屏 9:16 或 3:4
- 头条/穿山甲: 横屏 16:9
- 朋友圈广告: 方形 1:1
- 支持多时长版本裁剪
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


PLATFORM_PRESETS = {
    "douyin": {
        "name": "抖音/快手",
        "aspect": "9:16",
        "width": 1080,
        "height": 1920,
        "max_durations": [15, 30, 60],
        "bitrate": "4M",
        "fps": 30,
    },
    "wechat_video": {
        "name": "微信视频号",
        "aspect": "9:16",
        "width": 1080,
        "height": 1920,
        "max_durations": [30, 60, 180],
        "bitrate": "4M",
        "fps": 30,
    },
    "wechat_34": {
        "name": "微信视频号 3:4",
        "aspect": "3:4",
        "width": 1080,
        "height": 1440,
        "max_durations": [30, 60],
        "bitrate": "3.5M",
        "fps": 30,
    },
    "toutiao": {
        "name": "头条/穿山甲",
        "aspect": "16:9",
        "width": 1920,
        "height": 1080,
        "max_durations": [60, 120, 180],
        "bitrate": "5M",
        "fps": 30,
    },
    "moments": {
        "name": "朋友圈广告",
        "aspect": "1:1",
        "width": 1080,
        "height": 1080,
        "max_durations": [15, 30],
        "bitrate": "3M",
        "fps": 30,
    },
}


def get_video_info(video_path: str) -> dict:
    """Get video resolution, duration, and FPS."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "stream=width,height,r_frame_rate:format=duration",
            "-select_streams", "v:0",
            "-of", "json",
            video_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {}

    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]
    fmt = data.get("format", {})

    fps_str = stream.get("r_frame_rate", "30/1")
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
    except (ValueError, ZeroDivisionError):
        fps = 30.0

    return {
        "width": int(stream.get("width", 1920)),
        "height": int(stream.get("height", 1080)),
        "duration": float(fmt.get("duration", 0)),
        "fps": fps,
    }


def export_for_platform(
    video_path: str,
    output_dir: str,
    platform: str,
    durations: list[int] | None = None,
) -> list[str]:
    """Export video for a specific platform."""
    preset = PLATFORM_PRESETS.get(platform)
    if not preset:
        print(f"  Unknown platform: {platform}", file=sys.stderr)
        return []

    info = get_video_info(video_path)
    src_w, src_h = info["width"], info["height"]
    src_dur = info["duration"]
    dst_w, dst_h = preset["width"], preset["height"]

    print(f"\n  Platform: {preset['name']} ({dst_w}x{dst_h})")

    src_ratio = src_w / src_h
    dst_ratio = dst_w / dst_h

    if abs(src_ratio - dst_ratio) < 0.05:
        vf = f"scale={dst_w}:{dst_h}"
    elif src_ratio > dst_ratio:
        scale_h = dst_h
        scale_w = int(scale_h * src_ratio)
        crop_x = (scale_w - dst_w) // 2
        vf = f"scale={scale_w}:{scale_h},crop={dst_w}:{dst_h}:{crop_x}:0"
    else:
        scale_w = dst_w
        scale_h = int(scale_w / src_ratio)
        crop_y = (scale_h - dst_h) // 2
        vf = f"scale={scale_w}:{scale_h},crop={dst_w}:{dst_h}:0:{crop_y}"

    export_durs = durations or preset["max_durations"]
    stem = Path(video_path).stem
    output_files = []

    for max_dur in export_durs:
        if src_dur < max_dur * 0.8:
            actual_dur = src_dur
            dur_label = "full"
        else:
            actual_dur = max_dur
            dur_label = f"{max_dur}s"

        out_name = f"{stem}_{platform}_{dur_label}.mp4"
        out_path = os.path.join(output_dir, out_name)

        args = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-t", str(actual_dur),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium",
            "-b:v", preset["bitrate"],
            "-r", str(preset["fps"]),
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart",
            out_path,
        ]

        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode == 0:
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f"    {out_name} ({size_mb:.1f}MB, {actual_dur:.0f}s)")
            output_files.append(out_path)
        else:
            print(f"    FAILED: {out_name}", file=sys.stderr)

    return output_files


def export_all_platforms(
    video_path: str,
    output_dir: str | None = None,
    platforms: list[str] | None = None,
) -> dict:
    """Export video for all specified platforms."""
    if output_dir is None:
        output_dir = str(get_project_root() / "video" / "output" / "exports")
    os.makedirs(output_dir, exist_ok=True)

    platforms = platforms or list(PLATFORM_PRESETS.keys())
    stem = Path(video_path).stem

    print(f"\n{'='*60}")
    print(f"Multi-Platform Export: {stem}")
    print(f"  Platforms: {', '.join(platforms)}")
    print(f"{'='*60}")

    results = {}
    for p in platforms:
        files = export_for_platform(video_path, output_dir, p)
        results[p] = files

    total_files = sum(len(f) for f in results.values())
    print(f"\n  Total: {total_files} files exported")

    manifest = {
        "source": Path(video_path).name,
        "exports": {p: [Path(f).name for f in files] for p, files in results.items()},
    }
    manifest_path = os.path.join(output_dir, f"{stem}_exports.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return results


def main():
    parser = argparse.ArgumentParser(description="Export video for multiple platforms")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("-o", "--output-dir", help="Output directory")
    parser.add_argument(
        "-p", "--platforms", nargs="+",
        choices=list(PLATFORM_PRESETS.keys()),
        help="Target platforms (default: all)",
    )
    parser.add_argument("--list-platforms", action="store_true", help="List available platforms")
    args = parser.parse_args()

    if args.list_platforms:
        print("Available platforms:")
        for pid, p in PLATFORM_PRESETS.items():
            durs = ", ".join(f"{d}s" for d in p["max_durations"])
            print(f"  {pid}: {p['name']} ({p['width']}x{p['height']}, {p['aspect']}) [{durs}]")
        return

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    export_all_platforms(args.video, args.output_dir, args.platforms)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
自定义视频尺寸导出脚本

支持指定宽高，三种缩放方式：scale（等比例缩放+黑边）、crop（裁剪居中）、stretch（拉伸）。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_video_info(video_path: str) -> dict:
    """Get video width, height, duration, FPS."""
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


def resize_video(
    video_path: str,
    width: int,
    height: int,
    output_path: str,
    method: str = "scale",
) -> bool:
    """
    将视频缩放到指定尺寸。
    method:
      - scale: 等比例缩放，不足处用黑边填充 (default)
      - crop:  等比例放大后居中裁剪
      - stretch: 直接拉伸到目标尺寸
    """
    info = get_video_info(video_path)
    src_w = info.get("width", 1920)
    src_h = info.get("height", 1080)
    fps = info.get("fps", 30)

    dst_w = width
    dst_h = height
    src_ratio = src_w / src_h
    dst_ratio = dst_w / dst_h

    if method == "stretch":
        vf = f"scale={dst_w}:{dst_h}"
    elif method == "crop":
        if src_ratio > dst_ratio:
            scale_h = dst_h
            scale_w = int(scale_h * src_ratio)
            crop_x = (scale_w - dst_w) // 2
            vf = f"scale={scale_w}:{scale_h},crop={dst_w}:{dst_h}:{crop_x}:0"
        else:
            scale_w = dst_w
            scale_h = int(scale_w / src_ratio)
            crop_y = (scale_h - dst_h) // 2
            vf = f"scale={scale_w}:{scale_h},crop={dst_w}:{dst_h}:0:{crop_y}"
    else:
        # scale: pad to fit
        if abs(src_ratio - dst_ratio) < 0.01:
            vf = f"scale={dst_w}:{dst_h}"
        elif src_ratio > dst_ratio:
            scale_h = dst_h
            scale_w = int(scale_h * src_ratio)
            pad_x = (dst_w - scale_w) // 2
            vf = f"scale={scale_w}:{scale_h},pad={dst_w}:{dst_h}:{pad_x}:0:black"
        else:
            scale_w = dst_w
            scale_h = int(scale_w / src_ratio)
            pad_y = (dst_h - scale_h) // 2
            vf = f"scale={scale_w}:{scale_h},pad={dst_w}:{dst_h}:0:{pad_y}:black"

    args = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[-400:]}", file=sys.stderr)
        return False

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Resized: {src_w}x{src_h} -> {dst_w}x{dst_h} ({method}), {size_mb:.1f}MB")
    return True


def main():
    parser = argparse.ArgumentParser(description="Resize video to custom dimensions")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("width", type=int, help="Output width (pixels)")
    parser.add_argument("height", type=int, help="Output height (pixels)")
    parser.add_argument("-o", "--output", help="Output video path")
    parser.add_argument(
        "-m", "--method",
        choices=["scale", "crop", "stretch"],
        default="scale",
        help="scale=pad black bars, crop=center crop, stretch=stretch to fit",
    )
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    output = args.output or str(Path(args.video).parent / f"{Path(args.video).stem}_{args.width}x{args.height}.mp4")
    ok = resize_video(args.video, args.width, args.height, output, args.method)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

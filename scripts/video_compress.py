#!/usr/bin/env python3
"""
视频文件大小控制脚本

检查视频大小和时长，若超过 500MB 或 20 分钟则自动降码率压缩。
单条生成视频要求：小于 500MB，20 分钟以下。
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_video_duration_seconds(video_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration", "-of", "csv=p=0",
            video_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def get_video_size_mb(video_path: str) -> float:
    return os.path.getsize(video_path) / (1024 * 1024)


def check_and_compress(
    video_path: str,
    output_path: str | None = None,
    max_size_mb: float = 500,
    max_duration_sec: float = 1200,
    keep_resolution: bool = True,
) -> str:
    """
    检查视频大小和时长，超过限制则压缩并输出到 output_path。
    返回最终视频路径（原文件或压缩后路径）。
    """
    size_mb = get_video_size_mb(video_path)
    duration_sec = get_video_duration_seconds(video_path)

    if duration_sec <= 0:
        print("  WARNING: Could not get video duration, assuming 600s", file=sys.stderr)
        duration_sec = 600

    need_compress = size_mb > max_size_mb or duration_sec > max_duration_sec
    if not need_compress:
        print(f"  Video within limits: {size_mb:.1f}MB, {duration_sec:.0f}s")
        if output_path and output_path != video_path:
            import shutil
            shutil.copy2(video_path, output_path)
            return output_path
        return video_path

    target_mb = min(max_size_mb, (duration_sec / 60) * (500 / 20))  # 按 20min=500MB 比例
    target_mb = max(50, target_mb)

    if output_path is None:
        out_dir = str(Path(video_path).parent)
        stem = Path(video_path).stem
        output_path = os.path.join(out_dir, f"{stem}_compressed.mp4")

    print(f"  Compressing: {size_mb:.0f}MB, {duration_sec:.0f}s -> target ~{target_mb:.0f}MB")

    target_bitrate_kbps = int((target_mb * 8 * 1024) / duration_sec * 0.85)
    audio_bitrate = 48
    video_bitrate = max(target_bitrate_kbps - audio_bitrate, 200)

    if keep_resolution:
        vf = "scale='min(1080,iw)':-2"
    else:
        vf = "scale='min(720,iw)':-2"

    args = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium",
        "-b:v", f"{video_bitrate}k", "-maxrate", f"{int(video_bitrate * 1.2)}k", "-bufsize", f"{video_bitrate * 2}k",
        "-c:a", "aac", "-b:a", f"{audio_bitrate}k", "-ac", "1",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Compression failed: {result.stderr[-400:]}", file=sys.stderr)
        return video_path

    new_size = get_video_size_mb(output_path)
    print(f"  Compressed: {size_mb:.0f}MB -> {new_size:.1f}MB -> {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Check video size/duration and compress if over 500MB or 20min"
    )
    parser.add_argument("video", help="Input video path")
    parser.add_argument("-o", "--output", help="Output video path (default: input_compressed.mp4)")
    parser.add_argument("--max-size-mb", type=float, default=500, help="Max file size in MB")
    parser.add_argument("--max-duration", type=float, default=1200, help="Max duration in seconds (20min=1200)")
    parser.add_argument("--no-keep-resolution", action="store_true", help="Allow downscale to 720p")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    check_and_compress(
        args.video,
        output_path=args.output,
        max_size_mb=args.max_size_mb,
        max_duration_sec=args.max_duration,
        keep_resolution=not args.no_keep_resolution,
    )


if __name__ == "__main__":
    main()

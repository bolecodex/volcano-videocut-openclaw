#!/usr/bin/env python3
"""
删除结尾静帧放大段落

检测视频最后 3-5 秒是否为静帧（画面几乎静止）或缓慢放大效果，若是则剪掉该段。
"""

import argparse
import json
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


def get_video_fps(video_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "stream=r_frame_rate", "-select_streams", "v:0", "-of", "csv=p=0",
            video_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 30.0
    s = result.stdout.strip()
    try:
        if "/" in s:
            a, b = s.split("/")
            return float(a) / float(b)
        return float(s)
    except (ValueError, ZeroDivisionError):
        return 30.0


def detect_freeze_zoom(video_path: str, tail_seconds: float = 5.0) -> float:
    """
    检测结尾是否存在静帧或缓慢放大。若存在，返回应剪掉的秒数（从结尾往前），否则返回 0。
    方法：对最后 tail_seconds 内采样若干帧，计算帧间差异；若差异很小则视为静帧。
    可选：用 scdet 或 select 滤镜；这里用简单方案——抽帧比较 PSNR/差异。
    """
    duration = get_video_duration_seconds(video_path)
    if duration <= tail_seconds + 1:
        return 0.0

    start_t = max(0, duration - tail_seconds)
    tmp_dir = tempfile.mkdtemp(prefix="freeze_")
    # 从 start_t 开始每秒抽一帧（或每 0.5 秒）
    n_samples = max(3, int(tail_seconds * 2))
    fps = get_video_fps(video_path)
    interval = tail_seconds / n_samples

    frame_paths = []
    for i in range(n_samples):
        t = start_t + i * interval
        out = os.path.join(tmp_dir, f"f{i:02d}.jpg")
        r = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", video_path, "-vframes", "1", "-q:v", "2", out],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and os.path.exists(out):
            frame_paths.append(out)

    if len(frame_paths) < 2:
        for p in frame_paths:
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
        return 0.0

    # 计算连续帧之间的差异（用 FFmpeg 的 psnr 或 ssim）
    diffs = []
    for i in range(len(frame_paths) - 1):
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-i", frame_paths[i], "-i", frame_paths[i + 1],
                "-lavfi", "ssim", "-f", "null", "-",
            ],
            capture_output=True, text=True,
        )
        # ssim 输出在 stderr: SSIM Y:0.xxxx
        for line in r.stderr.split("\n"):
            if "SSIM" in line and "All" not in line:
                try:
                    part = line.split("SSIM")[-1].strip()
                    val = float(part.split(":")[1].strip().split()[0])
                    diffs.append(val)
                except (ValueError, IndexError):
                    pass
                break

    for p in frame_paths:
        try:
            os.unlink(p)
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    # 若所有帧间 SSIM 都很高（>0.98），说明几乎静止
    if len(diffs) >= 2 and sum(diffs) / len(diffs) > 0.98:
        return tail_seconds
    # 若后半段差异小，可能只有最后 2-3 秒是静帧
    if len(diffs) >= 4:
        half = diffs[len(diffs) // 2:]
        if half and sum(half) / len(half) > 0.99:
            return min(tail_seconds, interval * (len(diffs) // 2 + 1))
    return 0.0


def remove_tail_segment(video_path: str, cut_end_seconds: float, output_path: str) -> bool:
    """剪掉视频最后 cut_end_seconds 秒。"""
    duration = get_video_duration_seconds(video_path)
    if cut_end_seconds <= 0 or cut_end_seconds >= duration:
        import shutil
        shutil.copy2(video_path, output_path)
        return True

    new_duration = duration - cut_end_seconds
    args = [
        "ffmpeg", "-y", "-i", video_path,
        "-t", str(new_duration),
        "-c", "copy",
        output_path,
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[-300:]}", file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Remove trailing freeze/zoom segment (3-5s)")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("-o", "--output", help="Output video path")
    parser.add_argument("--tail", type=float, default=5.0, help="Seconds from end to analyze")
    parser.add_argument("--force", type=float, default=None, help="Force cut N seconds from end (skip detection)")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.video.replace(".mp4", "_trim.mp4")

    if args.force is not None:
        cut = max(0, args.force)
    else:
        cut = detect_freeze_zoom(args.video, tail_seconds=args.tail)

    if cut <= 0:
        import shutil
        shutil.copy2(args.video, output)
        print("  No trailing freeze detected, copied as-is.")
    else:
        print(f"  Trimming last {cut:.1f}s")
        ok = remove_tail_segment(args.video, cut, output)
        if not ok:
            sys.exit(1)
    print(f"  Done: {output}")
    sys.exit(0)


if __name__ == "__main__":
    main()

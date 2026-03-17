#!/usr/bin/env python3
"""
BGM 智能匹配与混音脚本

为投流素材视频叠加背景音乐，支持：
- 自动降低原声中的对白段 BGM 音量（ducking）
- 多种情绪预设匹配
- 片头强 BGM + 中间弱 BGM + 结尾卡点
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


BGM_CATEGORIES = {
    "tense": "紧张悬疑",
    "warm": "温馨治愈",
    "epic": "激昂史诗",
    "sad": "悲伤催泪",
    "funny": "搞笑轻松",
    "romantic": "浪漫甜蜜",
    "cool": "酷炫节奏",
}


def get_video_duration_seconds(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    return float(result.stdout.strip())


def detect_speech_segments(video_path: str, threshold_db: float = -28) -> list[tuple[float, float]]:
    """Detect speech segments for BGM ducking."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-af", f"silencedetect=n={threshold_db}dB:d=0.8",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )

    silence_ranges = []
    starts = []
    for line in result.stderr.split("\n"):
        if "silence_start" in line:
            try:
                val = float(line.split("silence_start:")[1].strip().split()[0])
                starts.append(val)
            except (ValueError, IndexError):
                pass
        elif "silence_end" in line:
            try:
                val = float(line.split("silence_end:")[1].strip().split()[0])
                if starts:
                    silence_ranges.append((starts.pop(), val))
            except (ValueError, IndexError):
                pass

    duration = get_video_duration_seconds(video_path)
    speech_segments = []

    if not silence_ranges:
        return [(0, duration)]

    if silence_ranges[0][0] > 0.5:
        speech_segments.append((0, silence_ranges[0][0]))

    for i in range(len(silence_ranges) - 1):
        seg_start = silence_ranges[i][1]
        seg_end = silence_ranges[i + 1][0]
        if seg_end - seg_start > 0.3:
            speech_segments.append((seg_start, seg_end))

    if silence_ranges[-1][1] < duration - 0.5:
        speech_segments.append((silence_ranges[-1][1], duration))

    return speech_segments


def mix_bgm(
    video_path: str,
    bgm_path: str,
    output_path: str,
    bgm_volume_db: float = -15,
    duck_volume_db: float = -25,
    ducking: bool = True,
    fade_in: float = 1.0,
    fade_out: float = 2.0,
) -> bool:
    """
    Mix BGM into video with automatic ducking during speech.
    
    Args:
        video_path: Input video
        bgm_path: BGM audio file
        output_path: Output video
        bgm_volume_db: Base BGM volume (dB)
        duck_volume_db: Ducked BGM volume during speech (dB)
        ducking: Enable auto-ducking
        fade_in: BGM fade-in duration
        fade_out: BGM fade-out duration
    """
    duration = get_video_duration_seconds(video_path)
    if duration <= 0:
        print("ERROR: Cannot determine video duration", file=sys.stderr)
        return False

    bgm_fade_out_start = max(0, duration - fade_out)

    if ducking:
        speech_segs = detect_speech_segments(video_path)
        print(f"  Detected {len(speech_segs)} speech segments for ducking")

        volume_expr_parts = []
        for start, end in speech_segs:
            volume_expr_parts.append(
                f"between(t,{start:.2f},{end:.2f})*{duck_volume_db}"
                f"+not(between(t,{start:.2f},{end:.2f}))*{bgm_volume_db}"
            )

        if volume_expr_parts:
            combined = "+".join(f"({p})" for p in volume_expr_parts)
            vol_expr = f"volume='{combined}':eval=frame"
        else:
            vol_expr = f"volume={bgm_volume_db}dB"

        bgm_af = (
            f"aloop=loop=-1:size=2e+09,"
            f"atrim=0:{duration:.2f},"
            f"{vol_expr},"
            f"afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={bgm_fade_out_start:.2f}:d={fade_out}"
        )
    else:
        bgm_af = (
            f"aloop=loop=-1:size=2e+09,"
            f"atrim=0:{duration:.2f},"
            f"volume={bgm_volume_db}dB,"
            f"afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={bgm_fade_out_start:.2f}:d={fade_out}"
        )

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", bgm_path,
            "-filter_complex",
            f"[1:a]{bgm_af}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        print(f"  Mix failed: {result.stderr[-300:]}", file=sys.stderr)
        result2 = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", bgm_path,
                "-filter_complex",
                f"[1:a]atrim=0:{duration:.2f},volume={bgm_volume_db}dB,"
                f"afade=t=in:st=0:d={fade_in},"
                f"afade=t=out:st={bgm_fade_out_start:.2f}:d={fade_out}[bgm];"
                f"[0:a][bgm]amix=inputs=2:duration=first[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ],
            capture_output=True, text=True,
        )
        if result2.returncode != 0:
            print(f"  Fallback mix also failed: {result2.stderr[-300:]}", file=sys.stderr)
            return False

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  BGM mixed: {output_path} ({size_mb:.1f}MB)")
    return True


def list_bgm_library(bgm_dir: str | None = None) -> list[dict]:
    """List available BGM files from the library."""
    if bgm_dir is None:
        bgm_dir = str(get_project_root() / "assets" / "bgm")
    if not os.path.isdir(bgm_dir):
        return []

    bgm_files = []
    for f in sorted(Path(bgm_dir).iterdir()):
        if f.suffix.lower() in {".mp3", ".wav", ".aac", ".m4a", ".ogg"}:
            category = "unknown"
            for cat in BGM_CATEGORIES:
                if cat in f.stem.lower():
                    category = cat
                    break
            bgm_files.append({
                "name": f.stem,
                "path": str(f),
                "category": category,
                "category_label": BGM_CATEGORIES.get(category, "其他"),
            })
    return bgm_files


def main():
    parser = argparse.ArgumentParser(description="Mix BGM into video with auto-ducking")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("bgm", help="BGM audio file")
    parser.add_argument("-o", "--output", help="Output video path")
    parser.add_argument("--bgm-volume", type=float, default=-15, help="BGM volume in dB (default: -15)")
    parser.add_argument("--duck-volume", type=float, default=-25, help="Ducked BGM volume in dB (default: -25)")
    parser.add_argument("--no-ducking", action="store_true", help="Disable auto-ducking")
    parser.add_argument("--fade-in", type=float, default=1.0, help="BGM fade-in seconds")
    parser.add_argument("--fade-out", type=float, default=2.0, help="BGM fade-out seconds")
    parser.add_argument("--list-bgm", action="store_true", help="List BGM library")
    args = parser.parse_args()

    if args.list_bgm:
        bgms = list_bgm_library()
        if not bgms:
            print("No BGM files found in assets/bgm/")
            print("Add .mp3/.wav files to assets/bgm/ with category prefixes: tense_, warm_, epic_, sad_, funny_, romantic_, cool_")
        else:
            for b in bgms:
                print(f"  [{b['category_label']}] {b['name']}: {b['path']}")
        return

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.bgm):
        print(f"ERROR: BGM not found: {args.bgm}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.video.replace(".mp4", "_bgm.mp4")
    print(f"\n{'='*60}")
    print(f"BGM Mix: {Path(args.video).name}")
    print(f"  BGM: {Path(args.bgm).name}")
    print(f"  Volume: {args.bgm_volume}dB, Duck: {args.duck_volume}dB")
    print(f"  Ducking: {not args.no_ducking}")
    print(f"{'='*60}")

    ok = mix_bgm(
        args.video, args.bgm, output,
        bgm_volume_db=args.bgm_volume,
        duck_volume_db=args.duck_volume,
        ducking=not args.no_ducking,
        fade_in=args.fade_in,
        fade_out=args.fade_out,
    )
    if ok:
        print(f"\n  Done: {output}")
    else:
        print(f"\n  FAILED", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

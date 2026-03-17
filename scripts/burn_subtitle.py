#!/usr/bin/env python3
"""
字幕烧录脚本

将 SRT 字幕文件硬烧入视频，支持多种样式预设。
S 级素材必须有字幕（大量用户静音浏览）。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


STYLE_PRESETS = {
    "center_large": {
        "description": "居中大字幕（投流推荐）",
        "fontsize": 28,
        "alignment": 2,
        "margin_v": 60,
        "font_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 3,
        "shadow": 2,
        "bold": 1,
    },
    "bottom_standard": {
        "description": "底部标准字幕",
        "fontsize": 22,
        "alignment": 2,
        "margin_v": 30,
        "font_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 2,
        "shadow": 1,
        "bold": 0,
    },
    "top_hint": {
        "description": "顶部提示字幕",
        "fontsize": 20,
        "alignment": 8,
        "margin_v": 20,
        "font_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "outline_width": 2,
        "shadow": 1,
        "bold": 1,
    },
    "dramatic": {
        "description": "戏剧化大字幕（白底黑边粗体）",
        "fontsize": 34,
        "alignment": 2,
        "margin_v": 80,
        "font_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 4,
        "shadow": 3,
        "bold": 1,
    },
}


def srt_to_ass(srt_path: str, style: dict, output_path: str | None = None) -> str:
    """Convert SRT to ASS format with custom styling."""
    if output_path is None:
        output_path = srt_path.replace(".srt", ".ass")

    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    font_name = style.get("font_name", "Noto Sans CJK SC")
    fs = style.get("fontsize", 24)
    alignment = style.get("alignment", 2)
    mv = style.get("margin_v", 40)
    fc = style.get("font_color", "&H00FFFFFF")
    oc = style.get("outline_color", "&H00000000")
    ow = style.get("outline_width", 2)
    shadow = style.get("shadow", 1)
    bold = style.get("bold", 0)

    ass_header = f"""[Script Info]
Title: Burned Subtitle
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{fs},{fc},&H000000FF,{oc},&H80000000,{bold},0,0,0,100,100,0,0,1,{ow},{shadow},{alignment},40,40,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    blocks = srt_content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        time_line = lines[1]
        text = " ".join(lines[2:]).replace("\n", "\\N")

        try:
            parts = time_line.split(" --> ")
            start = _srt_time_to_ass(parts[0].strip())
            end = _srt_time_to_ass(parts[1].strip())
        except (IndexError, ValueError):
            continue

        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    ass_content = ass_header + "\n".join(events) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return output_path


def _srt_time_to_ass(srt_time: str) -> str:
    """Convert SRT time (HH:MM:SS,mmm) to ASS time (H:MM:SS.cc)."""
    srt_time = srt_time.replace(",", ".")
    parts = srt_time.split(":")
    h = int(parts[0])
    m = parts[1]
    s_ms = parts[2]
    s, ms = s_ms.split(".")
    centiseconds = int(ms[:2]) if len(ms) >= 2 else int(ms) * 10
    return f"{h}:{m}:{s}.{centiseconds:02d}"


def burn_subtitle(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    style_name: str = "center_large",
    custom_style: dict | None = None,
) -> bool:
    """Burn subtitle into video using FFmpeg."""
    style = custom_style or STYLE_PRESETS.get(style_name, STYLE_PRESETS["center_large"])

    if subtitle_path.endswith(".srt"):
        ass_path = subtitle_path.replace(".srt", "_styled.ass")
        srt_to_ass(subtitle_path, style, ass_path)
        sub_filter = f"ass='{ass_path}'"
    else:
        sub_filter = f"ass='{subtitle_path}'"

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", sub_filter,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path,
        ],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        print(f"  Subtitle burn failed, trying subtitles filter...")
        result2 = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles='{subtitle_path}'",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "copy",
                "-movflags", "+faststart",
                output_path,
            ],
            capture_output=True, text=True,
        )
        if result2.returncode != 0:
            print(f"  FFmpeg error: {result2.stderr[-300:]}", file=sys.stderr)
            return False

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Subtitle burned: {output_path} ({size_mb:.1f}MB)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Burn SRT subtitles into video")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("subtitle", help="SRT or ASS subtitle file")
    parser.add_argument("-o", "--output", help="Output video path")
    parser.add_argument(
        "-s", "--style",
        choices=list(STYLE_PRESETS.keys()),
        default="center_large",
        help="Subtitle style preset",
    )
    parser.add_argument("--list-styles", action="store_true", help="List available styles")
    args = parser.parse_args()

    if args.list_styles:
        print("Available subtitle styles:")
        for name, style in STYLE_PRESETS.items():
            print(f"  {name}: {style['description']}")
        return

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.subtitle):
        print(f"ERROR: Subtitle not found: {args.subtitle}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.video.replace(".mp4", "_subtitled.mp4")
    stem = Path(args.video).stem
    print(f"\n{'='*60}")
    print(f"Subtitle Burn: {stem}")
    print(f"  Style: {args.style} ({STYLE_PRESETS[args.style]['description']})")
    print(f"{'='*60}")

    ok = burn_subtitle(args.video, args.subtitle, output, args.style)
    if ok:
        print(f"\n  Done: {output}")
    else:
        print(f"\n  FAILED", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

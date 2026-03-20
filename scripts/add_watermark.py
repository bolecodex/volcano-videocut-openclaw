#!/usr/bin/env python3
"""
成片自动添加剧名和风险语（如「热播短剧，本故事纯属虚构」）

支持两种模式：水印（半透明固定位置）和字幕叠加（drawtext）。
可自定义：位置、大小、颜色、字体。
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# 预设位置：(x, y) 或 FFmpeg 表达式
POSITION_PRESETS = {
    "top_center": "x=(w-text_w)/2:y=40",
    "top_left": "x=40:y=40",
    "top_right": "x=w-text_w-40:y=40",
    "bottom_center": "x=(w-text_w)/2:y=h-th-40",
    "bottom_left": "x=40:y=h-th-40",
    "bottom_right": "x=w-text_w-40:y=h-th-40",
    "center": "x=(w-text_w)/2:y=(h-th)/2",
}


def escape_drawtext(s: str) -> str:
    """Escape special chars for FFmpeg drawtext."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")


def add_text_overlay(
    video_path: str,
    output_path: str,
    title: str = "",
    disclaimer: str = "热播短剧，本故事纯属虚构",
    mode: str = "watermark",
    position: str = "bottom_center",
    fontsize: int = 24,
    fontcolor: str = "white",
    alpha: float = 0.8,
    fontfile: str | None = None,
    box: bool = False,
    boxcolor: str = "black@0.5",
    boxborderw: int = 2,
) -> bool:
    """
    在视频上叠加剧名和风险语。
    mode: 'watermark' 半透明水印风格, 'subtitle' 字幕风格（更醒目）
    position: 预设名或 FFmpeg 表达式如 "x=(w-text_w)/2:y=h-th-60"
    """
    lines = []
    if title:
        lines.append(title)
    if disclaimer:
        lines.append(disclaimer)

    if not lines:
        import shutil
        shutil.copy2(video_path, output_path)
        return True

    # 使用 \n 合并为多行，drawtext 用 textfile 或多段 drawtext
    # FFmpeg drawtext 多行可用 expansion=split 或多次 drawtext
    pos_expr = POSITION_PRESETS.get(position, position)
    font_conf = f":fontfile='{fontfile}'" if fontfile else ""

    # 构建多个 drawtext 滤镜：第一行剧名，第二行风险语
    drawtext_parts = []
    line_height = fontsize + 10
    for i, line in enumerate(lines):
        text_esc = escape_drawtext(line)
        if "h-th" in pos_expr:
            y_offset = 40 + (len(lines) - 1 - i) * line_height
            line_pos = pos_expr.replace("y=h-th-40", f"y=h-th-{y_offset}")
        elif "y=40" in pos_expr:
            line_pos = pos_expr.replace("y=40", f"y={40 + i * line_height}")
        else:
            line_pos = pos_expr

        alpha_str = f"{alpha:.2f}" if alpha < 1 else "1"
        fc = fontcolor if "@" in fontcolor else f"{fontcolor}@{alpha_str}"
        dt = (
            f"drawtext=text='{text_esc}'"
            f":fontsize={fontsize}{font_conf}"
            f":fontcolor={fc}"
            f":{line_pos}"
        )
        if box:
            dt += f":box=1:boxcolor={boxcolor}:boxborderw={boxborderw}"
        drawtext_parts.append(dt)

    vf = ",".join(drawtext_parts)

    args = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[-400:]}", file=sys.stderr)
        return False

    print(f"  Text overlay added -> {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Add drama title and disclaimer to video")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("-o", "--output", help="Output video path")
    parser.add_argument("--title", default="", help="Drama title")
    parser.add_argument("--disclaimer", default="热播短剧，本故事纯属虚构", help="Disclaimer text")
    parser.add_argument("--mode", choices=["watermark", "subtitle"], default="watermark")
    parser.add_argument("--position", default="bottom_center", help="Position preset or x/y expression")
    parser.add_argument("--fontsize", type=int, default=24)
    parser.add_argument("--fontcolor", default="white")
    parser.add_argument("--alpha", type=float, default=0.8)
    parser.add_argument("--fontfile", default=None)
    parser.add_argument("--box", action="store_true")
    parser.add_argument("--boxcolor", default="black@0.5")
    parser.add_argument("--boxborderw", type=int, default=2)
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.video.replace(".mp4", "_watermark.mp4")
    ok = add_text_overlay(
        args.video,
        output,
        title=args.title,
        disclaimer=args.disclaimer,
        mode=args.mode,
        position=args.position,
        fontsize=args.fontsize,
        fontcolor=args.fontcolor,
        alpha=args.alpha,
        fontfile=args.fontfile,
        box=args.box,
        boxcolor=args.boxcolor,
        boxborderw=args.boxborderw,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

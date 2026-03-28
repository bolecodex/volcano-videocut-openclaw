#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

import ffmpeg


def log(msg: str) -> None:
    print(f"[burn_subtitle] {msg}", flush=True)


def is_cjk_char(ch: str) -> bool:
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x3040 <= code <= 0x30FF
        or 0xAC00 <= code <= 0xD7AF
    )


def looks_cjk_text(text: str) -> bool:
    return any(is_cjk_char(ch) for ch in text)


def parse_transcript_segments(transcript_json: Path) -> list[dict[str, Any]]:
    with open(transcript_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        segments = data.get("segments") or []
    elif isinstance(data, list):
        segments = data
    else:
        segments = []

    out: list[dict[str, Any]] = []
    for i, seg in enumerate(segments, start=1):
        if "start" not in seg or "end" not in seg:
            continue
        start = float(seg["start"])
        end = float(seg["end"])
        if end <= start:
            continue
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        out.append({"id": int(seg.get("id", i)), "start": start, "end": end, "text": text})
    out.sort(key=lambda x: (x["start"], x["id"]))
    return out


def ffprobe_video_size(video_path: Path) -> tuple[int, int]:
    info = ffmpeg.probe(str(video_path))
    streams = info.get("streams", [])
    for s in streams:
        if s.get("codec_type") == "video":
            w = int(s["width"])
            h = int(s["height"])
            return w, h
    raise RuntimeError(f"no video stream found: {video_path}")


def auto_font_size(width: int, height: int) -> int:
    # Common market subtitle size: around 4.2%-4.8% of short edge.
    short_edge = min(width, height)
    return max(24, int(short_edge * 0.045))


def auto_margin_v(height: int) -> int:
    # Bottom safe area default: 10% video height.
    return max(24, int(height * 0.10))


def auto_margin_h(width: int) -> int:
    # Left/right safe area default: 5% video width.
    return max(24, int(width * 0.05))


def split_words(text: str) -> list[str]:
    # Keep spaces for better Western language wrapping.
    parts: list[str] = []
    buf = []
    for ch in text:
        if ch.isspace():
            if buf:
                parts.append("".join(buf))
                buf = []
            parts.append(" ")
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def wrap_text(text: str, max_chars_per_line: int, max_lines: int) -> str:
    text = " ".join(text.split())
    if not text:
        return text

    max_chars_per_line = max(8, max_chars_per_line)
    max_lines = max(1, max_lines)

    lines: list[str] = []
    if looks_cjk_text(text):
        idx = 0
        while idx < len(text):
            lines.append(text[idx : idx + max_chars_per_line])
            idx += max_chars_per_line
    else:
        tokens = split_words(text)
        current = ""
        for tk in tokens:
            candidate = (current + tk) if current else tk.lstrip()
            if len(candidate) <= max_chars_per_line:
                current = candidate
            else:
                if current:
                    lines.append(current.rstrip())
                current = tk.lstrip()
        if current:
            lines.append(current.rstrip())

    if not lines:
        lines = [text[:max_chars_per_line]]
    # Do not omit content by default. If max_lines is exceeded, keep all content on the last line.
    if len(lines) > max_lines:
        head = lines[: max_lines - 1]
        tail = "".join(lines[max_lines - 1 :]).strip()
        lines = head + [tail]
    return "\\N".join(line for line in lines if line)


def sec_to_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def to_ass_color(hex_color: str) -> str:
    # ASS color format: &HAABBGGRR
    c = hex_color.strip().lstrip("#")
    if len(c) == 6:
        rr, gg, bb = c[0:2], c[2:4], c[4:6]
        aa = "00"
    elif len(c) == 8:
        rr, gg, bb, aa = c[0:2], c[2:4], c[4:6], c[6:8]
    else:
        raise ValueError(f"invalid color: {hex_color}, expect #RRGGBB or #RRGGBBAA")
    return f"&H{aa}{bb}{gg}{rr}"


def build_ass_text(
    segments: list[dict[str, Any]],
    width: int,
    height: int,
    font_name: str,
    font_size: int,
    font_color: str,
    outline_color: str,
    shadow_color: str,
    outline: float,
    shadow: float,
    margin_l: int,
    margin_r: int,
    margin_v: int,
    max_lines: int,
    max_width_ratio: float,
) -> str:
    # Estimate max characters per line from render width and font size.
    # CJK average glyph width ~= 1.0 * font_size, Latin ~= 0.55 * font_size.
    max_render_width = width * max(0.4, min(max_width_ratio, 0.95))
    cjk_chars = int(max_render_width / (font_size * 1.02))
    latin_chars = int(max_render_width / (font_size * 0.58))
    max_chars_per_line = max(8, min(cjk_chars, latin_chars))

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,"
        f"{font_name},{font_size},{to_ass_color(font_color)},{to_ass_color(font_color)},"
        f"{to_ass_color(outline_color)},{to_ass_color(shadow_color)},"
        f"0,0,0,0,100,100,0,0,1,{outline:.1f},{shadow:.1f},2,{margin_l},{margin_r},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for seg in segments:
        start = sec_to_ass_time(float(seg["start"]))
        end = sec_to_ass_time(float(seg["end"]))
        text = wrap_text(str(seg["text"]), max_chars_per_line=max_chars_per_line, max_lines=max_lines)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def burn_subtitles(video_in: Path, ass_path: Path, video_out: Path, retry_times: int) -> None:
    escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    last_exc: Exception | None = None
    for i in range(1, retry_times + 1):
        try:
            (
                ffmpeg.input(str(video_in))
                .output(str(video_out), vf=f"ass='{escaped}'", acodec="copy")
                .overwrite_output()
                .run(quiet=True)
            )
            return
        except Exception as exc:
            last_exc = exc
            log(f"burn attempt {i}/{retry_times} failed: {exc}")
    raise RuntimeError(f"subtitle burn failed after {retry_times} retries: {last_exc}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="字幕压制：根据视频分辨率自动设定默认样式，支持居中靠下安全区与自动折行（不省略）。"
    )
    parser.add_argument("--video-input", required=True, help="输入视频路径（通常为合并后的视频）")
    parser.add_argument("--transcript-json", required=True, help="翻译结果 JSON（包含 segments.start/end/text）")
    parser.add_argument("--output-video", required=True, help="输出压制字幕后的视频路径")
    parser.add_argument("--ass-output", default=None, help="可选，输出 ASS 字幕路径（默认写临时文件）")
    parser.add_argument("--font-name", default="Arial", help="字体名（默认 Arial）")
    parser.add_argument("--font-size", type=int, default=0, help="字体大小（0=自动按分辨率）")
    parser.add_argument("--font-color", default="#FFFFFF", help="字体颜色，默认白色 #FFFFFF")
    parser.add_argument("--outline-color", default="#000000", help="描边颜色，默认黑色 #000000")
    parser.add_argument("--shadow-color", default="#000000", help="阴影颜色，默认黑色 #000000")
    parser.add_argument("--outline", type=float, default=1.5, help="描边宽度，默认 1.5")
    parser.add_argument("--shadow", type=float, default=2.0, help="阴影大小，默认 2.0")
    parser.add_argument("--margin-l", type=int, default=0, help="左侧安全边距像素（0=自动，默认视频宽 5%）")
    parser.add_argument("--margin-r", type=int, default=0, help="右侧安全边距像素（0=自动，默认视频宽 5%）")
    parser.add_argument("--margin-v", type=int, default=0, help="底部安全边距像素（0=自动）")
    parser.add_argument("--max-lines", type=int, default=2, help="最多行数，默认 2")
    parser.add_argument("--max-width-ratio", type=float, default=0.90, help="字幕最大宽度占视频宽比例，默认 0.90")
    parser.add_argument("--retry-times", type=int, default=3, help="压制阶段失败重试次数，默认 3")
    args = parser.parse_args()

    video_in = Path(args.video_input).resolve()
    transcript_json = Path(args.transcript_json).resolve()
    video_out = Path(args.output_video).resolve()
    video_out.parent.mkdir(parents=True, exist_ok=True)

    if not video_in.exists():
        print(f"错误: 输入视频不存在: {video_in}")
        return 1
    if not transcript_json.exists():
        print(f"错误: transcript json 不存在: {transcript_json}")
        return 1

    try:
        segments = parse_transcript_segments(transcript_json)
        if not segments:
            print(f"错误: transcript 无有效 segments: {transcript_json}")
            return 1

        width, height = ffprobe_video_size(video_in)
        font_size = args.font_size if args.font_size > 0 else auto_font_size(width, height)
        margin_l = args.margin_l if args.margin_l > 0 else auto_margin_h(width)
        margin_r = args.margin_r if args.margin_r > 0 else auto_margin_h(width)
        margin_v = args.margin_v if args.margin_v > 0 else auto_margin_v(height)
        log(
            f"video={width}x{height}, segments={len(segments)}, font_size={font_size}, "
            f"margin_l={margin_l}, margin_r={margin_r}, margin_v={margin_v}, max_lines={args.max_lines}"
        )

        ass_text = build_ass_text(
            segments=segments,
            width=width,
            height=height,
            font_name=args.font_name,
            font_size=font_size,
            font_color=args.font_color,
            outline_color=args.outline_color,
            shadow_color=args.shadow_color,
            outline=max(0.0, args.outline),
            shadow=max(0.0, args.shadow),
            margin_l=margin_l,
            margin_r=margin_r,
            margin_v=margin_v,
            max_lines=max(1, args.max_lines),
            max_width_ratio=args.max_width_ratio,
        )

        if args.ass_output:
            ass_path = Path(args.ass_output).resolve()
            ass_path.parent.mkdir(parents=True, exist_ok=True)
            ass_path.write_text(ass_text, encoding="utf-8")
            burn_subtitles(video_in, ass_path, video_out, retry_times=max(1, args.retry_times))
        else:
            with tempfile.TemporaryDirectory(prefix="burn_sub_") as td:
                ass_path = Path(td) / "subtitle.ass"
                ass_path.write_text(ass_text, encoding="utf-8")
                burn_subtitles(video_in, ass_path, video_out, retry_times=max(1, args.retry_times))

        log(f"subtitle burned video generated: {video_out}")
        return 0
    except Exception as exc:
        print(f"错误: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

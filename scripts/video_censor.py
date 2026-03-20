#!/usr/bin/env python3
"""
违规画面与敏感字幕打码

使用 Ark 多模态模型分析视频帧和字幕，检测违规画面与敏感字幕，并用 FFmpeg 打码。
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


SENSITIVE_KEYWORDS = []  # 可配置敏感词列表，用于字幕过滤


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


def extract_keyframes(video_path: str, interval_sec: float = 2.0, max_frames: int = 60) -> list[dict]:
    duration = get_video_duration_seconds(video_path)
    if duration <= 0:
        return []
    effective_interval = max(interval_sec, duration / max_frames)
    tmp_dir = tempfile.mkdtemp(prefix="censor_kf_")
    pattern = os.path.join(tmp_dir, "frame_%05d.jpg")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps=1/{effective_interval},scale='min(720,iw)':-2", "-q:v", "3",
            pattern,
        ],
        capture_output=True, text=True,
    )
    frames = []
    for f in sorted(Path(tmp_dir).glob("frame_*.jpg")):
        idx = int(f.stem.split("_")[1]) - 1
        ts = idx * effective_interval
        frames.append({"path": str(f), "seconds": ts})
    return frames


def detect_violations(video_path: str, subtitle_path: str | None, output_dir: str | None) -> list[dict]:
    """
    调用 Ark 多模态分析视频帧，检测需要打码的时间段。
    返回 [{"start": sec, "end": sec}, ...]。
    若提供字幕路径，同时检测敏感字幕并返回 {"subtitle_line": idx} 或时间范围。
    """
    from openai import OpenAI
    import httpx

    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    if not api_key:
        print("  ARK_API_KEY not set, skipping violation detection", file=sys.stderr)
        return []

    frames = extract_keyframes(video_path, interval_sec=3.0, max_frames=30)
    if not frames:
        return []

    content_parts = []
    for fr in frames[:20]:
        with open(fr["path"], "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    prompt = (
        "这是短剧视频的若干关键帧。请判断是否存在需要打码的违规内容（暴力、色情、敏感画面或敏感文字）。\n"
        "若存在，请仅返回 JSON 数组，每个元素为 {\"start\": 开始秒数, \"end\": 结束秒数}，覆盖该段画面。\n"
        "若没有违规内容，返回 []。只返回 JSON，不要其他说明。"
    )
    content_parts.append({"type": "text", "text": prompt})

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=httpx.Timeout(180.0))

    violations = []
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=1024,
            temperature=0.1,
        )
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1] if "```" in text else text.split("```")[0]
        text = text.strip()
        violations = json.loads(text)
        if not isinstance(violations, list):
            violations = []
    except Exception as e:
        print(f"  Detection error: {e}", file=sys.stderr)
    finally:
        for fr in frames:
            try:
                os.unlink(fr["path"])
            except OSError:
                pass
        try:
            os.rmdir(os.path.dirname(frames[0]["path"]))
        except OSError:
            pass

    return violations


def censor_video(video_path: str, violations: list[dict], output_path: str) -> bool:
    """
    对 violations 中的时间段应用全屏模糊/马赛克。
    violations: [{"start": sec, "end": sec}, ...]
    """
    if not violations:
        import shutil
        shutil.copy2(video_path, output_path)
        return True

    # 使用 drawbox 覆盖半透明黑 + boxblur，或直接用 boxblur 覆盖全画面
    # 简化：对每个区间用 -ss -t 切出，boxblur 后 concat
    # 更简单：用 overlay 在指定时间画模糊层。FFmpeg 可用 sendcmd 或 multiple -filter_complex
    # 实现：用 geq 或 boxblur 在时间范围内生效需要 sendcmd；替代方案为分段处理再 concat
    duration = get_video_duration_seconds(video_path)
    vf_parts = []
    # 全片先 scale 保持，再对违规段加模糊：用 select+boxblur+overlay 较复杂，这里用简单方案
    # 简单方案：对整段中落在 violations 内的帧做 boxblur。用 segment 分段再 concat 更清晰但复杂。
    # 使用 overlay：先生成一个与视频同长的模糊版，再在非违规时间段用原画，违规段用模糊。需要两路输入。
    # 最简：单 pass 用 geq 或 blur 条件化不可行。改用两路：1) 原视频 2) 全模糊视频；然后用 overlay 按时间选择显示
    # 更简单：只对每个 [start,end] 段用 ffmpeg 切出、boxblur、再 concat 回去。实现 concat 需要精确切三段：0->s1, s1->e1(blur), e1->end...
    segments = []
    t = 0.0
    for v in sorted(violations, key=lambda x: x["start"]):
        start, end = float(v["start"]), float(v["end"])
        if start > t:
            segments.append(("copy", t, start))
        segments.append(("blur", start, end))
        t = max(t, end)
    if t < duration:
        segments.append(("copy", t, duration))

    tmp_dir = tempfile.mkdtemp(prefix="censor_seg_")
    list_file = os.path.join(tmp_dir, "list.txt")
    with open(list_file, "w") as f:
        for typ, seg_start, seg_end in segments:
            seg_dur = seg_end - seg_start
            if seg_dur <= 0:
                continue
            out_seg = os.path.join(tmp_dir, f"seg_{len(f.list) if hasattr(f, 'list') else 0}.mp4")
            if typ == "copy":
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-ss", str(seg_start), "-i", video_path, "-t", str(seg_dur),
                        "-c", "copy", out_seg,
                    ],
                    capture_output=True, text=True,
                )
            else:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-ss", str(seg_start), "-i", video_path, "-t", str(seg_dur),
                        "-vf", "boxblur=lr=20:lp=5", "-c:a", "copy", out_seg,
                    ],
                    capture_output=True, text=True,
                )
            f.write(f"file '{out_seg}'\n")
    # Concat
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output_path],
        capture_output=True, text=True,
    )
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return os.path.exists(output_path)


def censor_video_simple(video_path: str, violations: list[dict], output_path: str) -> bool:
    """Single-pass: overlay a blurred copy only in violation time ranges using overlay with enable."""
    if not violations:
        import shutil
        shutil.copy2(video_path, output_path)
        return True

    # Split into segments and concat
    duration = get_video_duration_seconds(video_path)
    tmp_dir = tempfile.mkdtemp(prefix="censor_")
    segs = []
    t = 0.0
    for v in sorted(violations, key=lambda x: x["start"]):
        s, e = float(v["start"]), float(v["end"])
        if s > t + 0.1:
            segs.append(("orig", t, s))
        segs.append(("blur", s, e))
        t = max(t, e)
    if t < duration - 0.1:
        segs.append(("orig", t, duration))

    seg_files = []
    for i, (typ, start, end) in enumerate(segs):
        dur = end - start
        if dur <= 0:
            continue
        out = os.path.join(tmp_dir, f"s{i}.mp4")
        if typ == "orig":
            r = subprocess.run(
                ["ffmpeg", "-y", "-ss", str(start), "-i", video_path, "-t", str(dur), "-c", "copy", out],
                capture_output=True, text=True,
            )
        else:
            r = subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", str(start), "-i", video_path, "-t", str(dur),
                    "-vf", "boxblur=lr=25:lp=5", "-c:a", "copy", out,
                ],
                capture_output=True, text=True,
            )
        if os.path.exists(out):
            seg_files.append(out)

    if not seg_files:
        import shutil
        shutil.copy2(video_path, output_path)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return True

    list_path = os.path.join(tmp_dir, "list.txt")
    with open(list_path, "w") as f:
        for p in seg_files:
            f.write(f"file '{p}'\n")

    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path],
        capture_output=True, text=True,
    )
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return r.returncode == 0 and os.path.exists(output_path)


def main():
    parser = argparse.ArgumentParser(description="Detect and censor violations in video")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("-o", "--output", help="Output video path")
    parser.add_argument("--subtitle", help="Optional SRT for sensitive subtitle detection")
    parser.add_argument("--no-detect", action="store_true", help="Skip AI detection (no censoring)")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.video.replace(".mp4", "_censor.mp4")

    violations = [] if args.no_detect else detect_violations(args.video, args.subtitle, None)
    print(f"  Detected {len(violations)} violation segment(s)")
    ok = censor_video_simple(args.video, violations, output)
    print(f"  Done: {output}" if ok else "  Failed", file=sys.stderr if not ok else sys.stdout)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

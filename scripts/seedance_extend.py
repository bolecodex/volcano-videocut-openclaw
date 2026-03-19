#!/usr/bin/env python3
"""
Seedance Smart Video Extender

Extend short video clips by generating AI continuation frames using
Seedance 2.0 video extension capabilities.

Usage:
    python seedance_extend.py <video> [options]
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seedance_client as sc


def get_video_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip()) if result.returncode == 0 else 0


def extract_tail(video_path: str, tail_seconds: float, output_path: str) -> str:
    """Extract the tail portion of a video for use as reference."""
    duration = get_video_duration(video_path)
    start = max(0, duration - tail_seconds)
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", str(start), "-i", video_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ],
        capture_output=True, text=True,
    )
    return output_path


def extend_video(
    video_path: str,
    output_path: str,
    prompt: str | None = None,
    tail_seconds: float = 5.0,
    extend_duration: int = 8,
    chain_count: int = 1,
    ratio: str = "adaptive",
    resolution: str = "720p",
    model: str | None = None,
    fast: bool = False,
) -> str:
    """
    Extend a video clip with AI-generated continuation.
    Can chain multiple extensions for longer output.
    """
    print("=== Seedance Video Extender ===")
    print(f"  Source: {video_path} ({get_video_duration(video_path):.1f}s)")
    print(f"  Extensions: {chain_count} x {extend_duration}s")

    current_video = video_path
    outputs = []

    for i in range(chain_count):
        print(f"\n  --- Extension {i+1}/{chain_count} ---")

        tail_path = output_path.replace(".mp4", f"_tail_{i}.mp4")
        extract_tail(current_video, tail_seconds, tail_path)

        ref_path = sc.prepare_video_for_reference(tail_path)
        with open(ref_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode("utf-8")
        video_data_uri = f"data:video/mp4;base64,{video_b64}"

        ext_prompt = prompt or (
            "Continue this video naturally. Maintain the same visual style, "
            "camera movement, lighting, and scene composition. "
            "Create a smooth continuation of the action."
        )

        content = [
            {"type": "video_url", "video_url": {"url": video_data_uri}},
            {"type": "text", "text": ext_prompt},
        ]

        use_model = model
        if fast and not use_model:
            use_model = "doubao-seedance-2-0-fast-260128"

        ext_output = output_path.replace(".mp4", f"_ext_{i}.mp4")
        sc.generate_video(
            content=content,
            output_path=ext_output,
            model=use_model,
            duration=extend_duration,
            ratio=ratio,
            resolution=resolution,
        )
        outputs.append(ext_output)
        current_video = ext_output

        for f in [tail_path]:
            if os.path.exists(f):
                os.unlink(f)
        if ref_path != tail_path and os.path.exists(ref_path):
            os.unlink(ref_path)

    if chain_count == 1:
        concat_original_and_extension(video_path, outputs[0], output_path)
    else:
        all_parts = [video_path] + outputs
        concat_multiple(all_parts, output_path)

    for f in outputs:
        if os.path.exists(f) and f != output_path:
            os.unlink(f)

    final_dur = get_video_duration(output_path)
    print(f"\n  Final output: {output_path} ({final_dur:.1f}s)")
    return output_path


def concat_original_and_extension(original: str, extension: str, output: str):
    """Concatenate the original video with its AI extension."""
    import tempfile
    list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    list_file.write(f"file '{os.path.abspath(original)}'\n")
    list_file.write(f"file '{os.path.abspath(extension)}'\n")
    list_file.close()

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file.name,
         "-c:v", "libx264", "-preset", "fast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", output],
        capture_output=True, text=True,
    )
    os.unlink(list_file.name)


def concat_multiple(parts: list[str], output: str):
    """Concatenate multiple video parts."""
    import tempfile
    list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    for p in parts:
        list_file.write(f"file '{os.path.abspath(p)}'\n")
    list_file.close()

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file.name,
         "-c:v", "libx264", "-preset", "fast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", output],
        capture_output=True, text=True,
    )
    os.unlink(list_file.name)


def main():
    parser = argparse.ArgumentParser(description="Seedance Smart Video Extender")
    parser.add_argument("video", help="Path to the video clip to extend")
    parser.add_argument("-o", "--output", help="Output directory", default="video/output")
    parser.add_argument("-n", "--name", help="Output filename (without extension)")
    parser.add_argument("-p", "--prompt", help="Continuation prompt")
    parser.add_argument("-t", "--tail", type=float, default=5.0, help="Tail seconds to use as reference (default 5)")
    parser.add_argument("-d", "--duration", type=int, default=8, help="Extension duration per segment (4-15)")
    parser.add_argument("-c", "--chain", type=int, default=1, help="Number of chained extensions")
    parser.add_argument("-r", "--ratio", default="adaptive", help="Aspect ratio")
    parser.add_argument("--resolution", default="720p", choices=["480p", "720p"])
    parser.add_argument("--fast", action="store_true", help="Use fast model")
    parser.add_argument("--model", help="Override model ID")

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    name = args.name or f"extended_{Path(args.video).stem}"
    output_path = os.path.join(args.output, f"{name}.mp4")

    try:
        result = extend_video(
            video_path=args.video,
            output_path=output_path,
            prompt=args.prompt,
            tail_seconds=args.tail,
            extend_duration=args.duration,
            chain_count=args.chain,
            ratio=args.ratio,
            resolution=args.resolution,
            model=args.model,
            fast=args.fast,
        )
        print(json.dumps({"success": True, "output": result}))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()

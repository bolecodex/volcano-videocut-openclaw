#!/usr/bin/env python3
"""
Seedance Viral Video Replicator

Replicate a trending/viral video's style, motion, and camera work with new content
using Seedance 2.0 multi-modal reference capabilities.

Usage:
    python seedance_replicate.py <reference_video> [options]
"""

import argparse
import json
import os
import sys
import base64
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seedance_client as sc


DEFAULT_PROMPT = (
    "Replicate the camera movement, visual rhythm, and editing style of the reference video. "
    "Maintain the same dynamic energy and transitions while generating fresh visual content."
)

STYLE_PRESETS = {
    "cinematic": "Cinematic wide shots with dramatic lighting and slow dolly movements, film grain texture",
    "tiktok_trend": "Fast-paced vertical TikTok style with quick cuts, dynamic zooms, and energetic pacing",
    "product_showcase": "Smooth tracking shots showcasing a product with soft lighting and clean aesthetic",
    "emotional_drama": "Intimate close-ups, shallow depth of field, emotional expressions, warm color grading",
    "action_packed": "High-energy action sequence with quick zooms, shaky cam, and explosive transitions",
}


def build_content(
    reference_video: str,
    prompt: str,
    reference_images: list[str] | None = None,
) -> list[dict]:
    """Build the multi-modal content array for the Seedance API."""
    content = []

    content.append({
        "type": "video_url",
        "video_url": {"url": reference_video},
    })

    if reference_images:
        for img_path in reference_images:
            data_uri = sc.encode_image_data_uri(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": data_uri},
            })

    content.append({"type": "text", "text": prompt})
    return content


def replicate_video(
    reference_video: str,
    output_path: str,
    prompt: str | None = None,
    style_preset: str | None = None,
    reference_images: list[str] | None = None,
    duration: int = 8,
    ratio: str = "adaptive",
    resolution: str = "720p",
    model: str | None = None,
    fast: bool = False,
) -> str:
    """
    Replicate a viral video with optional style preset and reference images.
    """
    print(f"=== Seedance Viral Replicator ===")
    print(f"  Reference: {reference_video}")

    ref_path = sc.prepare_video_for_reference(reference_video)

    with open(ref_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode("utf-8")
    video_data_uri = f"data:video/mp4;base64,{video_b64}"

    final_prompt = prompt or DEFAULT_PROMPT
    if style_preset and style_preset in STYLE_PRESETS:
        final_prompt = f"{STYLE_PRESETS[style_preset]}. {final_prompt}"
        print(f"  Style preset: {style_preset}")

    content = build_content(video_data_uri, final_prompt, reference_images)

    use_model = model
    if fast and not use_model:
        use_model = "doubao-seedance-2-0-fast-260128"

    print(f"  Prompt: {final_prompt[:100]}...")
    result = sc.generate_video(
        content=content,
        output_path=output_path,
        model=use_model,
        duration=duration,
        ratio=ratio,
        resolution=resolution,
    )
    print(f"  Output: {result}")

    if ref_path != reference_video and os.path.exists(ref_path):
        os.unlink(ref_path)

    return result


def main():
    parser = argparse.ArgumentParser(description="Seedance Viral Video Replicator")
    parser.add_argument("reference", help="Path to the reference/viral video")
    parser.add_argument("-o", "--output", help="Output directory", default="video/output")
    parser.add_argument("-n", "--name", help="Output filename (without extension)")
    parser.add_argument("-p", "--prompt", help="Custom text prompt")
    parser.add_argument("-s", "--style", choices=list(STYLE_PRESETS.keys()), help="Style preset")
    parser.add_argument("-i", "--images", nargs="+", help="Reference images (product/character)")
    parser.add_argument("-d", "--duration", type=int, default=8, help="Video duration in seconds (4-15)")
    parser.add_argument("-r", "--ratio", default="adaptive", help="Aspect ratio (16:9, 9:16, 1:1, adaptive)")
    parser.add_argument("--resolution", default="720p", choices=["480p", "720p"])
    parser.add_argument("--fast", action="store_true", help="Use fast model")
    parser.add_argument("--model", help="Override model ID")

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    name = args.name or f"replicate_{Path(args.reference).stem}"
    output_path = os.path.join(args.output, f"{name}.mp4")

    try:
        result = replicate_video(
            reference_video=args.reference,
            output_path=output_path,
            prompt=args.prompt,
            style_preset=args.style,
            reference_images=args.images,
            duration=args.duration,
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

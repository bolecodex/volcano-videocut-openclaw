#!/usr/bin/env python3
"""
Seedance Video Restyler

Edit/restyle existing video clips — change environment, add visual effects,
swap objects, alter weather/lighting using Seedance 2.0 video editing.

Usage:
    python seedance_restyle.py <video> [options]
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seedance_client as sc


RESTYLE_PRESETS = {
    "night_scene": "Transform to a dramatic night scene with moonlight, blue-tinted shadows, and glowing city lights in the background",
    "snow_effect": "Add falling snow effect with winter atmosphere, frost on surfaces, cold blue color grading, visible breath vapor",
    "rain_mood": "Add cinematic rain effect with wet reflections on surfaces, moody dark atmosphere, neon light reflections on puddles",
    "golden_hour": "Transform lighting to golden hour sunset, warm orange tones, long dramatic shadows, lens flare effects",
    "luxury_upgrade": "Upgrade the environment to luxury setting — marble textures, gold accents, premium lighting, high-end aesthetic",
    "cyberpunk": "Restyle into cyberpunk aesthetic — neon lights, holographic elements, futuristic UI overlays, blue and pink color scheme",
    "ancient_chinese": "Transform into ancient Chinese drama style — traditional architecture, silk textures, lantern lighting, ink wash color palette",
    "horror_tint": "Add horror atmosphere — desaturated colors, flickering lights, subtle fog, slightly unstable camera, dark vignette",
}


def restyle_video(
    video_path: str,
    output_path: str,
    edit_prompt: str | None = None,
    restyle_preset: str | None = None,
    reference_image: str | None = None,
    duration: int = 8,
    ratio: str = "adaptive",
    resolution: str = "720p",
    model: str | None = None,
    fast: bool = False,
) -> str:
    """
    Restyle/edit a video clip with Seedance 2.0.
    """
    print("=== Seedance Video Restyler ===")
    print(f"  Source: {video_path}")

    ref_path = sc.prepare_video_for_reference(video_path)
    with open(ref_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode("utf-8")
    video_data_uri = f"data:video/mp4;base64,{video_b64}"

    prompt = edit_prompt or ""
    if restyle_preset and restyle_preset in RESTYLE_PRESETS:
        preset_desc = RESTYLE_PRESETS[restyle_preset]
        prompt = f"{preset_desc}. {prompt}" if prompt else preset_desc
        print(f"  Restyle preset: {restyle_preset}")
    elif not prompt:
        prompt = "Enhance the visual quality and add cinematic color grading"

    content = [
        {"type": "video_url", "video_url": {"url": video_data_uri}},
    ]

    if reference_image:
        img_uri = sc.encode_image_data_uri(reference_image)
        content.append({
            "type": "image_url",
            "image_url": {"url": img_uri},
        })

    content.append({"type": "text", "text": prompt})

    use_model = model
    if fast and not use_model:
        use_model = "doubao-seedance-2-0-fast-260128"

    print(f"  Prompt: {prompt[:100]}...")
    result = sc.generate_video(
        content=content,
        output_path=output_path,
        model=use_model,
        duration=duration,
        ratio=ratio,
        resolution=resolution,
    )
    print(f"  Output: {result}")

    if ref_path != video_path and os.path.exists(ref_path):
        os.unlink(ref_path)

    return result


def main():
    parser = argparse.ArgumentParser(description="Seedance Video Restyler")
    parser.add_argument("video", help="Path to the video clip to restyle")
    parser.add_argument("-o", "--output", help="Output directory", default="video/output")
    parser.add_argument("-n", "--name", help="Output filename (without extension)")
    parser.add_argument("-p", "--prompt", help="Edit/restyle prompt")
    parser.add_argument("-s", "--style", choices=list(RESTYLE_PRESETS.keys()), help="Restyle preset")
    parser.add_argument("-i", "--image", help="Reference image for style transfer")
    parser.add_argument("-d", "--duration", type=int, default=8, help="Duration (4-15)")
    parser.add_argument("-r", "--ratio", default="adaptive", help="Aspect ratio")
    parser.add_argument("--resolution", default="720p", choices=["480p", "720p"])
    parser.add_argument("--fast", action="store_true", help="Use fast model")
    parser.add_argument("--model", help="Override model ID")

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    name = args.name or f"restyled_{Path(args.video).stem}"
    output_path = os.path.join(args.output, f"{name}.mp4")

    try:
        result = restyle_video(
            video_path=args.video,
            output_path=output_path,
            edit_prompt=args.prompt,
            restyle_preset=args.style,
            reference_image=args.image,
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

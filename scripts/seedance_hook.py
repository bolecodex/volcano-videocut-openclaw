#!/usr/bin/env python3
"""
Seedance AI Hook Clip Generator

Generate eye-catching 5-8s AI opening hooks to prepend to drama promo footage.
Uses Seedance 2.0 text-to-video or image-to-video for dramatic attention-grabbing clips.

Usage:
    python seedance_hook.py [options]
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seedance_client as sc


HOOK_STYLES = {
    "suspense_zoom": (
        "Extreme slow-motion dramatic zoom into a mysterious scene, "
        "dark cinematic lighting with volumetric fog, tension-building atmosphere, "
        "shallow depth of field revealing a hidden detail"
    ),
    "explosion_reveal": (
        "Dramatic particle explosion revealing the main subject, "
        "fragments flying in slow motion with golden light rays, "
        "epic cinematic reveal with shockwave effect"
    ),
    "emotional_rain": (
        "Cinematic rain scene with emotional close-up, "
        "water droplets in slow motion, warm backlighting creating silhouette, "
        "intimate dramatic mood with shallow depth of field"
    ),
    "epic_slow_motion": (
        "Ultra slow motion dramatic moment, "
        "high-speed camera effect with crisp detail, "
        "epic scale with dramatic lighting and atmospheric haze"
    ),
    "glitch_rewind": (
        "Digital glitch rewind effect transitioning through time, "
        "VHS distortion with RGB split, fast reverse motion "
        "freezing at a dramatic moment with sharp focus"
    ),
    "luxury_reveal": (
        "Luxurious cinematic reveal with smooth camera orbit, "
        "golden hour lighting on premium surfaces, "
        "reflections and bokeh creating high-end commercial aesthetic"
    ),
    "mystery_approach": (
        "Slow steady approach through a dark corridor, "
        "atmospheric fog with dramatic side lighting, "
        "building tension as something comes into view"
    ),
}


def build_content(
    prompt: str,
    first_frame_path: str | None = None,
) -> list[dict]:
    """Build content for hook generation."""
    content = []

    if first_frame_path:
        data_uri = sc.encode_image_data_uri(first_frame_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": data_uri},
        })

    content.append({"type": "text", "text": prompt})
    return content


def generate_hook(
    output_path: str,
    hook_style: str | None = None,
    custom_prompt: str | None = None,
    first_frame: str | None = None,
    source_video: str | None = None,
    duration: int = 5,
    ratio: str = "9:16",
    resolution: str = "720p",
    model: str | None = None,
    fast: bool = False,
    generate_audio: bool = True,
) -> str:
    """Generate an AI hook clip."""
    print("=== Seedance Hook Generator ===")

    frame_path = first_frame
    if source_video and not frame_path:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", source_video],
            capture_output=True, text=True,
        )
        dur = float(result.stdout.strip()) if result.returncode == 0 else 10
        timestamp = dur * 0.15
        frame_path = output_path.replace(".mp4", "_keyframe.jpg")
        sc.extract_frame(source_video, timestamp, frame_path)
        print(f"  Extracted key frame at {timestamp:.1f}s")

    prompt = custom_prompt or ""
    if hook_style and hook_style in HOOK_STYLES:
        style_desc = HOOK_STYLES[hook_style]
        prompt = f"{style_desc}. {prompt}" if prompt else style_desc
        print(f"  Hook style: {hook_style}")
    elif not prompt:
        prompt = HOOK_STYLES["suspense_zoom"]
        print("  Using default hook style: suspense_zoom")

    content = build_content(prompt, frame_path)

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
        generate_audio=generate_audio,
    )
    print(f"  Output: {result}")

    if frame_path and frame_path != first_frame and os.path.exists(frame_path):
        os.unlink(frame_path)

    return result


def main():
    parser = argparse.ArgumentParser(description="Seedance AI Hook Clip Generator")
    parser.add_argument("-o", "--output", help="Output directory", default="video/output")
    parser.add_argument("-n", "--name", help="Output filename (without extension)")
    parser.add_argument("-s", "--style", choices=list(HOOK_STYLES.keys()), help="Hook style preset")
    parser.add_argument("-p", "--prompt", help="Custom text prompt")
    parser.add_argument("-f", "--first-frame", help="Image to use as first frame")
    parser.add_argument("-v", "--source-video", help="Source video to extract first frame from")
    parser.add_argument("-d", "--duration", type=int, default=5, help="Duration in seconds (4-10)")
    parser.add_argument("-r", "--ratio", default="9:16", help="Aspect ratio")
    parser.add_argument("--resolution", default="720p", choices=["480p", "720p"])
    parser.add_argument("--fast", action="store_true", help="Use fast model")
    parser.add_argument("--no-audio", action="store_true", help="Skip audio generation")
    parser.add_argument("--model", help="Override model ID")

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    name = args.name or f"hook_{args.style or 'custom'}"
    output_path = os.path.join(args.output, f"{name}.mp4")

    try:
        result = generate_hook(
            output_path=output_path,
            hook_style=args.style,
            custom_prompt=args.prompt,
            first_frame=args.first_frame,
            source_video=args.source_video,
            duration=args.duration,
            ratio=args.ratio,
            resolution=args.resolution,
            model=args.model,
            fast=args.fast,
            generate_audio=not args.no_audio,
        )
        print(json.dumps({"success": True, "output": result}))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()

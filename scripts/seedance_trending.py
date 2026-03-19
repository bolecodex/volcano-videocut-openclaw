#!/usr/bin/env python3
"""
Seedance Trending Content Generator

Batch-generate short viral-style video clips from text descriptions,
optionally using web search for real-time trending visual references.

Usage:
    python seedance_trending.py [options]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seedance_client as sc


THEME_TEMPLATES = {
    "drama_highlight": [
        "Dramatic close-up of a person making a shocking revelation, cinematic lighting with shallow depth of field, emotional tension",
        "Intense confrontation scene between two people in a luxury interior, dramatic side lighting, film noir mood",
        "Person walking away in slow motion through rain, backlighting creating silhouette, emotional music video aesthetic",
        "Dramatic plot twist moment — person turns around with surprised expression, camera quick zoom, lens flare",
    ],
    "visual_spectacle": [
        "Breathtaking aerial shot of a vast fantasy landscape with floating islands and waterfalls, golden hour lighting",
        "Impossible architecture defying gravity, MC Escher inspired, photorealistic rendering with dramatic shadows",
        "Time-lapse of a city transforming from day to night, lights turning on like stars, hyperlapse camera movement",
        "Surreal underwater scene with bioluminescent creatures, ethereal light rays, dreamlike slow motion",
    ],
    "product_tease": [
        "Extreme close-up product reveal with particle effects, premium lighting on metallic surface, satisfying ASMR aesthetic",
        "Smooth 360-degree orbit around a floating product, holographic reflections, clean white background",
        "Product emerging from liquid metal in slow motion, chrome reflections, high-end commercial aesthetic",
        "Unboxing reveal with dramatic lighting, camera tracking from dark to light, premium texture details",
    ],
    "emotion_hook": [
        "Child running into parent's arms in slow motion, golden hour field, emotional warmth, shallow depth of field",
        "Tears rolling down a face in extreme slow motion, beautiful macro cinematography, emotional lighting",
        "Couple's hands slowly reaching for each other, dramatic focus pull, warm color grading, intimate moment",
        "Person standing at the edge of a cliff overlooking vast ocean, contemplative mood, epic wide shot",
    ],
    "action_energy": [
        "High-speed chase through neon-lit streets, motion blur, adrenaline-pumping camera shake, cyberpunk city",
        "Martial arts kick in extreme slow motion, impact shockwave visible, dramatic dust particles, stadium lighting",
        "Car drifting around a corner with smoke and sparks, low-angle shot, cinematic color grading",
        "Parkour runner leaping between rooftops at sunset, dynamic camera following the action, epic scale",
    ],
}


def generate_trending_clips(
    theme: str | None = None,
    custom_prompts: list[str] | None = None,
    output_dir: str = "video/output",
    count: int = 4,
    duration: int = 5,
    ratio: str = "9:16",
    resolution: str = "720p",
    model: str | None = None,
    fast: bool = False,
    use_web_search: bool = False,
    search_query: str | None = None,
) -> list[str]:
    """
    Batch-generate trending video clips.
    Returns list of output file paths.
    """
    print("=== Seedance Trending Clip Maker ===")

    prompts = []
    if custom_prompts:
        prompts = custom_prompts[:count]
    elif theme and theme in THEME_TEMPLATES:
        prompts = THEME_TEMPLATES[theme][:count]
        print(f"  Theme: {theme} ({len(prompts)} prompts)")
    else:
        prompts = THEME_TEMPLATES["drama_highlight"][:count]
        print("  Using default theme: drama_highlight")

    while len(prompts) < count:
        prompts.append(prompts[len(prompts) % len(prompts)])

    os.makedirs(output_dir, exist_ok=True)

    use_model = model
    if fast and not use_model:
        use_model = "doubao-seedance-2-0-fast-260128"

    tools = None
    if use_web_search:
        tools = [{"type": "web_search", "web_search": {}}]
        if search_query:
            prompts = [f"[Search context: {search_query}] {p}" for p in prompts]

    outputs = []
    task_ids = []

    print(f"\n  Submitting {len(prompts)} tasks...")
    for i, prompt in enumerate(prompts):
        content = [{"type": "text", "text": prompt}]
        try:
            task_id = sc.create_task(
                content=content,
                model=use_model,
                duration=duration,
                ratio=ratio,
                resolution=resolution,
                tools=tools,
            )
            task_ids.append((i, task_id, prompt))
        except Exception as e:
            print(f"  Task {i+1} creation failed: {e}")
            task_ids.append((i, None, prompt))

    print(f"\n  Polling {len([t for t in task_ids if t[1]])} tasks...")
    for idx, task_id, prompt in task_ids:
        if not task_id:
            continue

        output_path = os.path.join(output_dir, f"trending_{idx:02d}.mp4")
        try:
            result = sc.poll_task(task_id)
            sc.download_video(result, output_path)
            outputs.append(output_path)
            print(f"  [{idx+1}/{len(prompts)}] Done: {output_path}")
        except Exception as e:
            print(f"  [{idx+1}/{len(prompts)}] Failed: {e}")

    print(f"\n  Generated {len(outputs)}/{len(prompts)} clips")
    return outputs


def main():
    parser = argparse.ArgumentParser(description="Seedance Trending Content Generator")
    parser.add_argument("-o", "--output", help="Output directory", default="video/output")
    parser.add_argument("-t", "--theme", choices=list(THEME_TEMPLATES.keys()), help="Content theme")
    parser.add_argument("-p", "--prompts", nargs="+", help="Custom prompts (one per clip)")
    parser.add_argument("-c", "--count", type=int, default=4, help="Number of clips to generate")
    parser.add_argument("-d", "--duration", type=int, default=5, help="Duration per clip (4-15)")
    parser.add_argument("-r", "--ratio", default="9:16", help="Aspect ratio")
    parser.add_argument("--resolution", default="720p", choices=["480p", "720p"])
    parser.add_argument("--fast", action="store_true", help="Use fast model")
    parser.add_argument("--model", help="Override model ID")
    parser.add_argument("--web-search", action="store_true", help="Enable web search for trending references")
    parser.add_argument("--search-query", help="Web search query for context")

    args = parser.parse_args()

    try:
        results = generate_trending_clips(
            theme=args.theme,
            custom_prompts=args.prompts,
            output_dir=args.output,
            count=args.count,
            duration=args.duration,
            ratio=args.ratio,
            resolution=args.resolution,
            model=args.model,
            fast=args.fast,
            use_web_search=args.web_search,
            search_query=args.search_query,
        )
        print(json.dumps({"success": True, "outputs": results, "count": len(results)}))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Seedance 2.0 横竖屏比例转换

将视频在横屏(16:9)与竖屏(9:16)之间转换，保持内容与风格，仅改变画面比例与构图。
使用 Seedance 2.0 视频编辑能力实现智能重构图。

Usage:
    python seedance_reframe.py <video> -r <9:16|16:9> [options]
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seedance_client as sc

REFRAME_PROMPTS = {
    "9:16": "保持原画面内容、人物与风格完全一致，仅将画面比例转换为竖屏 9:16，智能重新构图以适配竖屏展示，不改变剧情与对白。",
    "16:9": "保持原画面内容、人物与风格完全一致，仅将画面比例转换为横屏 16:9，智能重新构图以适配横屏展示，不改变剧情与对白。",
    "1:1": "保持原画面内容与风格一致，仅将画面比例转换为方形 1:1，智能重新构图。",
}


def reframe_video(
    video_path: str,
    output_path: str,
    target_ratio: str = "9:16",
    custom_prompt: str | None = None,
    duration: int = 8,
    resolution: str = "720p",
    model: str | None = None,
    fast: bool = False,
) -> str:
    """
    使用 Seedance 2.0 将视频转换为目标比例（横屏转竖屏或竖屏转横屏）。
    """
    print("=== Seedance 横竖屏比例转换 ===")
    print(f"  源视频: {video_path}")
    print(f"  目标比例: {target_ratio}")

    ref_path = sc.prepare_video_for_reference(video_path)
    with open(ref_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode("utf-8")
    video_data_uri = f"data:video/mp4;base64,{video_b64}"

    prompt = custom_prompt or REFRAME_PROMPTS.get(target_ratio, REFRAME_PROMPTS["9:16"])
    content = [
        {"type": "video_url", "video_url": {"url": video_data_uri}},
        {"type": "text", "text": prompt},
    ]

    use_model = model
    if fast and not use_model:
        use_model = "doubao-seedance-2-0-fast-260128"

    print(f"  提示: {prompt[:60]}...")
    result = sc.generate_video(
        content=content,
        output_path=output_path,
        model=use_model,
        duration=duration,
        ratio=target_ratio,
        resolution=resolution,
    )
    print(f"  输出: {result}")

    if ref_path != video_path and os.path.exists(ref_path):
        os.unlink(ref_path)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Seedance 2.0 横屏转竖屏 / 竖屏转横屏"
    )
    parser.add_argument("video", help="待转换的视频文件路径")
    parser.add_argument("-o", "--output", default="video/output", help="输出目录")
    parser.add_argument("-n", "--name", help="输出文件名（不含扩展名）")
    parser.add_argument(
        "-r", "--ratio",
        choices=["9:16", "16:9", "1:1"],
        default="9:16",
        help="目标比例：9:16 竖屏、16:9 横屏、1:1 方形",
    )
    parser.add_argument("-p", "--prompt", help="自定义转换提示词（可选）")
    parser.add_argument("-d", "--duration", type=int, default=8, help="输出时长秒数 (4-15)")
    parser.add_argument("--resolution", default="720p", choices=["480p", "720p"])
    parser.add_argument("--fast", action="store_true", help="使用快速模型")
    parser.add_argument("--model", help="指定模型 ID")

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    stem = Path(args.video).stem
    suffix = args.ratio.replace(":", "x")
    name = args.name or f"reframe_{stem}_{suffix}"
    output_path = os.path.join(args.output, f"{name}.mp4")

    try:
        result = reframe_video(
            video_path=args.video,
            output_path=output_path,
            target_ratio=args.ratio,
            custom_prompt=args.prompt,
            duration=args.duration,
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

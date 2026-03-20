#!/usr/bin/env python3
"""
开场钩子与解说衔接

在 AI 解说场景下，为开场钩子段生成与正剧解说风格一致、内容衔接的解说词，
并做音频过渡（淡入淡出），使前贴与正剧解说流畅衔接。
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


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


def generate_hook_narration(
    hook_video_path: str,
    main_narration_script: str,
    max_hook_seconds: float = 8.0,
) -> str:
    """
    根据正剧解说文案，为钩子视频生成一段简短解说，使结尾能自然衔接到 main_narration_script 的开头。
    """
    from openai import OpenAI
    import httpx

    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    if not api_key:
        return ""

    duration = get_video_duration_seconds(hook_video_path)
    duration = min(duration, max_hook_seconds)

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=httpx.Timeout(60.0))

    main_preview = (main_narration_script or "")[:400]

    prompt = (
        f"请为一段 {duration:.0f} 秒的「投流开场钩子」视频撰写解说旁白（约 {max(5, int(duration))} 句）。\n\n"
        "要求：\n"
        "1. 风格与下面的正剧解说一致，语气有吸引力。\n"
        "2. 结尾一句要能自然过渡到正剧解说的开头，不要重复正剧第一句。\n"
        "3. 只输出钩子段的纯文本旁白，不要序号、不要时间轴。\n\n"
        f"正剧解说开头预览：\n{main_preview}\n\n"
        "请只输出钩子段的解说文案。"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  Hook narration generation error: {e}", file=sys.stderr)
        return ""


def bridge_narrations(
    hook_audio_path: str,
    main_audio_path: str,
    output_audio_path: str,
    crossfade_seconds: float = 0.5,
) -> bool:
    """将钩子解说与正剧解说音频拼接，衔接处做淡入淡出。"""
    # Concat with crossfade: [hook][crossfade][main]
    # FFmpeg: concat demuxer or filter afade
    with open(output_audio_path + ".list", "w") as f:
        f.write(f"file '{os.path.abspath(hook_audio_path)}'\n")
        f.write(f"file '{os.path.abspath(main_audio_path)}'\n")

    # Simple concat first; then we can add afade at junction
    args = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", output_audio_path + ".list",
        "-c", "copy",
        output_audio_path,
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    try:
        os.unlink(output_audio_path + ".list")
    except OSError:
        pass
    if result.returncode != 0:
        print(f"  FFmpeg bridge error: {result.stderr[-300:]}", file=sys.stderr)
        return False
    return True


def run_hook_bridge(
    hook_video_path: str,
    main_video_path: str,
    main_narration_script: str,
    output_audio_path: str | None = None,
    voice_id: str = "zh_female_huayan",
) -> str | None:
    """
    为钩子生成衔接解说，并可与正剧解说音频桥接。
    返回拼接后的音频路径；若仅生成钩子文案则返回 None（由调用方再合成）。
    """
    hook_script = generate_hook_narration(hook_video_path, main_narration_script)
    if not hook_script:
        return None

    sys.path.insert(0, str(get_project_root() / "scripts"))
    from ai_narration import synthesize_narration

    out_dir = str(Path(main_video_path).parent)
    hook_audio = os.path.join(out_dir, "hook_narration_temp.mp3")
    main_audio = os.path.join(out_dir, "main_narration_temp.mp3")

    if not synthesize_narration(hook_script, hook_audio, voice_id=voice_id):
        return None

    # 若调用方已提供正剧解说音频路径，可在此 bridge；否则只返回 hook 音频路径供后续拼接
    if output_audio_path and os.path.exists(main_audio):
        bridge_narrations(hook_audio, main_audio, output_audio_path)
        return output_audio_path
    return hook_audio


def main():
    parser = argparse.ArgumentParser(description="Generate hook narration that bridges to main narration")
    parser.add_argument("hook_video", help="Hook clip video path")
    parser.add_argument("main_script", help="Main narration script text (or path to .txt file)")
    parser.add_argument("-o", "--output", help="Output bridged audio path")
    parser.add_argument("--voice", default="zh_female_huayan")
    args = parser.parse_args()

    main_script = args.main_script
    if os.path.exists(main_script):
        with open(main_script, "r", encoding="utf-8") as f:
            main_script = f.read()

    out = run_hook_bridge(
        args.hook_video,
        "",
        main_script,
        output_audio_path=args.output,
        voice_id=args.voice,
    )
    sys.exit(0 if out else 1)


if __name__ == "__main__":
    main()

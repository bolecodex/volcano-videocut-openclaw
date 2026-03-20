#!/usr/bin/env python3
"""
BGM 自动匹配：根据视频情绪/风格从音乐库中匹配合适的 BGM 并混音

分析视频情绪（可选 Ark 多模态或启发式），根据 assets/bgm/bgm_index.json 或文件名分类匹配，
调用 bgm_mix 进行混音。
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


BGM_CATEGORIES = {
    "tense": "紧张悬疑",
    "warm": "温馨治愈",
    "epic": "激昂史诗",
    "sad": "悲伤催泪",
    "funny": "搞笑轻松",
    "romantic": "浪漫甜蜜",
    "cool": "酷炫节奏",
}


def load_bgm_index(bgm_dir: str) -> list[dict]:
    """Load BGM index from bgm_index.json; fallback to scanning audio files."""
    index_path = os.path.join(bgm_dir, "bgm_index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data if isinstance(data, list) else data.get("tracks", [])
        for e in entries:
            if "path" in e and not os.path.isabs(e["path"]):
                e["path"] = os.path.join(bgm_dir, e["path"])
        return entries

    entries = []
    for f in sorted(Path(bgm_dir).iterdir()):
        if f.suffix.lower() not in {".mp3", ".wav", ".aac", ".m4a", ".ogg"}:
            continue
        category = "unknown"
        for cat in BGM_CATEGORIES:
            if cat in f.stem.lower():
                category = cat
                break
        entries.append({
            "path": str(f),
            "name": f.stem,
            "emotion": category,
            "style": BGM_CATEGORIES.get(category, "其他"),
        })
    return entries


def analyze_video_mood(video_path: str, use_ai: bool = True) -> str:
    """
    分析视频情绪，返回 BGM 分类 key（如 tense, warm, epic）。
    若 use_ai 且配置了 Ark，可用多模态分析；否则返回默认 'warm'。
    """
    if not use_ai:
        return "warm"

    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        return "warm"

    try:
        import subprocess
        import tempfile
        import base64
        from openai import OpenAI
        import httpx

        # 取一帧做简单分析
        out_img = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        out_img.close()
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-ss", "5", "-i", video_path,
                "-vframes", "1", "-q:v", "2", out_img.name,
            ],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            os.unlink(out_img.name)
            return "warm"

        with open(out_img.name, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        os.unlink(out_img.name)

        base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=httpx.Timeout(60.0))

        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": (
                        "这是短剧视频的一帧。请从以下选择一个最符合画面情绪的词（只答一个英文词）： "
                        "tense, warm, epic, sad, funny, romantic, cool。只返回该词。"
                    )},
                ],
            }],
            max_tokens=16,
            temperature=0.2,
        )
        text = (resp.choices[0].message.content or "").strip().lower()
        for cat in BGM_CATEGORIES:
            if cat in text:
                return cat
    except Exception as e:
        print(f"  Mood analysis fallback: {e}", file=sys.stderr)
    return "warm"


def match_bgm(video_mood: str, bgm_library_dir: str) -> dict | None:
    """Pick best BGM from library by mood; fallback to first available."""
    entries = load_bgm_index(bgm_library_dir)
    if not entries:
        return None

    # 优先同情绪
    for e in entries:
        if e.get("emotion") == video_mood or e.get("style") == BGM_CATEGORIES.get(video_mood):
            if os.path.exists(e.get("path", "")):
                return e

    # 否则第一个
    for e in entries:
        if os.path.exists(e.get("path", "")):
            return e
    return None


def auto_mix_bgm(
    video_path: str,
    output_path: str | None = None,
    bgm_dir: str | None = None,
    use_ai_mood: bool = True,
) -> str | None:
    """Match BGM by video mood and mix; returns output path or None."""
    if bgm_dir is None:
        bgm_dir = str(get_project_root() / "assets" / "bgm")
    if not os.path.isdir(bgm_dir):
        print(f"  BGM directory not found: {bgm_dir}", file=sys.stderr)
        return None

    mood = analyze_video_mood(video_path, use_ai=use_ai_mood)
    print(f"  Video mood: {mood} ({BGM_CATEGORIES.get(mood, mood)})")
    bgm_entry = match_bgm(mood, bgm_dir)
    if not bgm_entry:
        print("  No BGM matched", file=sys.stderr)
        return None

    bgm_path = bgm_entry["path"]
    print(f"  Matched BGM: {bgm_entry.get('name', Path(bgm_path).stem)}")

    sys.path.insert(0, str(get_project_root() / "scripts"))
    from bgm_mix import mix_bgm

    output_path = output_path or video_path.replace(".mp4", "_bgm.mp4")
    ok = mix_bgm(
        video_path, bgm_path, output_path,
        bgm_volume_db=-15,
        duck_volume_db=-25,
        ducking=True,
        fade_in=1.0,
        fade_out=2.0,
    )
    return output_path if ok else None


def main():
    parser = argparse.ArgumentParser(description="Auto-match BGM by video mood and mix")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("-o", "--output", help="Output video path")
    parser.add_argument("--bgm-dir", help="BGM library directory (default: assets/bgm)")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI mood analysis, use default")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    out = auto_mix_bgm(
        args.video,
        output_path=args.output,
        bgm_dir=args.bgm_dir,
        use_ai_mood=not args.no_ai,
    )
    sys.exit(0 if out else 1)


if __name__ == "__main__":
    main()

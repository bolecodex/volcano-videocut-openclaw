#!/usr/bin/env python3
"""
素材质量 AI 评分脚本

使用 doubao-seed-2.0 对最终投流素材进行质量评分。
评分维度：前3秒吸引力 / 节奏流畅度 / 情绪曲线 / 卡点效果 / 台词完整性。
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_video_duration_seconds(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    return float(result.stdout.strip())


def compress_for_scoring(video_path: str, target_mb: float = 8) -> str:
    """Compress video for scoring API upload."""
    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if size_mb <= target_mb:
        return video_path

    duration = get_video_duration_seconds(video_path)
    if duration <= 0:
        duration = 120

    target_bitrate = int((target_mb * 8 * 1024) / duration * 0.85)
    video_bitrate = max(target_bitrate - 48, 200)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()

    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", "scale='min(480,iw)':-2",
            "-c:v", "libx264", "-preset", "fast",
            "-b:v", f"{video_bitrate}k",
            "-c:a", "aac", "-b:a", "48k", "-ac", "1",
            "-movflags", "+faststart",
            tmp.name,
        ],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        os.unlink(tmp.name)
        return video_path

    return tmp.name


def score_quality(
    video_path: str,
    output_dir: str | None = None,
) -> dict:
    """Score video quality using AI."""
    project_root = get_project_root()
    load_dotenv(project_root / ".env")

    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    if not api_key:
        print("ERROR: ARK_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    if output_dir is None:
        output_dir = str(project_root / "video" / "output")
    os.makedirs(output_dir, exist_ok=True)

    stem = Path(video_path).stem
    duration = get_video_duration_seconds(video_path)

    print(f"\n{'='*60}")
    print(f"Quality Scoring: {stem} ({duration:.0f}s)")
    print(f"{'='*60}")

    compressed = compress_for_scoring(video_path)
    is_temp = compressed != video_path

    try:
        with open(compressed, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode("utf-8")

        b64_mb = len(video_b64) / (1024 * 1024)
        print(f"  Video payload: {b64_mb:.1f}MB")

        import httpx
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(300.0, connect=30.0, write=120.0, read=300.0),
            max_retries=2,
        )

        prompt = (
            "你是一位专业的短剧投流素材质检师。请对这段投流广告视频进行全面质量评估。\n\n"
            f"视频时长：{duration:.0f}秒\n\n"
            "请从以下 5 个维度评分（每个维度 0-100 分），并给出综合评分和改进建议。\n\n"
            "## 评分维度\n\n"
            "1. **前3秒吸引力** (hook_score)\n"
            "   - 开头画面是否有冲击力？\n"
            "   - 是否能让用户停住不划走？\n"
            "   - 前5秒是否建立了悬念/冲突/情感？\n\n"
            "2. **节奏流畅度** (rhythm_score)\n"
            "   - 片段之间的衔接是否自然？\n"
            "   - 是否有明显的跳切/卡顿/不连贯？\n"
            "   - 整体节奏是否适合投流（不拖沓、不太快）？\n\n"
            "3. **情绪曲线** (emotion_score)\n"
            "   - 是否有清晰的情绪递进？\n"
            "   - 高潮/爽点是否到位？\n"
            "   - 结尾是否有足够悬念让用户想看完整剧？\n\n"
            "4. **卡点效果** (ending_score)\n"
            "   - 结尾是否在最佳位置？\n"
            "   - 是否卡在悬念/爽点即将爆发的位置？\n"
            "   - 最后画面是否有'落幅'？\n\n"
            "5. **台词完整性** (dialogue_score)\n"
            "   - 是否有台词被切断？\n"
            "   - 切入/切出点是否在台词自然停顿处？\n"
            "   - 对白是否清晰可听？\n\n"
            "## 输出格式\n\n"
            "```json\n"
            "{\n"
            '  "overall_score": 85,\n'
            '  "grade": "A/B/C/D",\n'
            '  "scores": {\n'
            '    "hook_score": 90,\n'
            '    "rhythm_score": 85,\n'
            '    "emotion_score": 80,\n'
            '    "ending_score": 88,\n'
            '    "dialogue_score": 82\n'
            "  },\n"
            '  "strengths": ["优势1", "优势2"],\n'
            '  "weaknesses": ["问题1", "问题2"],\n'
            '  "suggestions": ["改进建议1", "改进建议2"],\n'
            '  "summary": "一句话总结"\n'
            "}\n"
            "```\n\n"
            "评分标准：90+ = S级，80-89 = A级，70-79 = B级，60-69 = C级，<60 = D级\n"
            "只返回 JSON。"
        )

        print(f"  Scoring with {model}...")
        start_time = time.time()

        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{video_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=4096,
            temperature=0.1,
        )

        elapsed = time.time() - start_time
        print(f"  Scoring completed in {elapsed:.1f}s")

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        result = json.loads(content)

    except json.JSONDecodeError:
        result = {"error": "Failed to parse AI response", "raw": content[:500]}
    except Exception as e:
        result = {"error": str(e)}
    finally:
        if is_temp:
            try:
                os.unlink(compressed)
            except OSError:
                pass

    result["video"] = Path(video_path).name
    result["duration"] = duration

    json_path = os.path.join(output_dir, f"score_{stem}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Results saved: {json_path}")

    if "overall_score" in result:
        print(f"\n  Overall: {result['overall_score']}/100 ({result.get('grade', '?')})")
        scores = result.get("scores", {})
        for dim, val in scores.items():
            label = dim.replace("_score", "").replace("_", " ").title()
            print(f"    {label}: {val}")
        if result.get("suggestions"):
            print(f"  Suggestions:")
            for s in result["suggestions"]:
                print(f"    - {s}")

    return result


def main():
    parser = argparse.ArgumentParser(description="AI quality scoring for promotional video material")
    parser.add_argument("video", help="Input video file to score")
    parser.add_argument("-o", "--output-dir", help="Output directory for score JSON")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    score_quality(args.video, args.output_dir)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
封面/首帧生成脚本

从视频中提取高冲击力帧作为封面候选，
可选调用火山引擎 AI 评估最佳封面。
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


def get_video_duration_seconds(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    return float(result.stdout.strip())


def extract_candidate_frames(
    video_path: str,
    output_dir: str,
    num_candidates: int = 12,
    prefer_early: bool = True,
) -> list[dict]:
    """Extract candidate cover frames at high visual-impact moments."""
    duration = get_video_duration_seconds(video_path)
    if duration <= 0:
        return []

    frames_dir = os.path.join(output_dir, "cover_candidates")
    os.makedirs(frames_dir, exist_ok=True)

    if prefer_early:
        timestamps = []
        early_count = num_candidates * 2 // 3
        late_count = num_candidates - early_count
        early_end = min(duration * 0.4, 60)
        for i in range(early_count):
            ts = (i + 1) * early_end / (early_count + 1)
            timestamps.append(ts)
        for i in range(late_count):
            ts = early_end + (i + 1) * (duration - early_end) / (late_count + 1)
            timestamps.append(ts)
    else:
        timestamps = [(i + 1) * duration / (num_candidates + 1) for i in range(num_candidates)]

    candidates = []
    for i, ts in enumerate(timestamps):
        h = int(ts // 3600)
        m = int((ts % 3600) // 60)
        s = int(ts % 60)
        ts_str = f"{h:02d}:{m:02d}:{s:02d}"

        out_path = os.path.join(frames_dir, f"cover_{i:02d}_{ts:.0f}s.jpg")
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(ts),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                out_path,
            ],
            capture_output=True, text=True,
        )

        if result.returncode == 0 and os.path.exists(out_path):
            size_kb = os.path.getsize(out_path) / 1024
            candidates.append({
                "index": i,
                "timestamp": ts_str,
                "seconds": round(ts, 1),
                "path": out_path,
                "size_kb": round(size_kb, 1),
            })

    print(f"  Extracted {len(candidates)} candidate frames")
    return candidates


def score_covers_with_ai(candidates: list[dict]) -> list[dict]:
    """Use Ark API to evaluate which frames make the best cover."""
    from openai import OpenAI
    import httpx

    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    if not api_key:
        print("  WARNING: No API key, skipping AI scoring", file=sys.stderr)
        return candidates

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(120.0),
        max_retries=2,
    )

    content_parts = []
    for c in candidates[:8]:
        with open(c["path"], "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
        })

    prompt = (
        f"以下是 {len(content_parts)} 张视频截图，请评估每张作为投流广告封面的效果。\n\n"
        "评估维度：\n"
        "1. 视觉冲击力（画面是否吸引眼球）\n"
        "2. 情绪张力（是否有强烈情绪表达）\n"
        "3. 信息量（画面是否有趣/有悬念）\n"
        "4. 构图质量（人物是否清晰、画面是否协调）\n\n"
        "请为每张图片打分（0-100），并推荐最佳 Top 3。\n"
        "输出 JSON 数组，每个元素包含 index(0开始)、score、reason 字段。\n"
        "只返回 JSON。"
    )
    content_parts.append({"type": "text", "text": prompt})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=4096,
            temperature=0.1,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        scores = json.loads(content)
        if isinstance(scores, list):
            for s in scores:
                idx = s.get("index", -1)
                if 0 <= idx < len(candidates):
                    candidates[idx]["ai_score"] = s.get("score", 0)
                    candidates[idx]["ai_reason"] = s.get("reason", "")
            candidates.sort(key=lambda x: x.get("ai_score", 0), reverse=True)
            print(f"  AI scoring complete. Top score: {candidates[0].get('ai_score', 'N/A')}")
    except Exception as e:
        print(f"  AI scoring failed: {e}", file=sys.stderr)

    return candidates


def generate_covers(
    video_path: str,
    output_dir: str | None = None,
    num_candidates: int = 12,
    ai_score: bool = True,
) -> dict:
    """Full cover generation pipeline."""
    if output_dir is None:
        output_dir = str(get_project_root() / "video" / "output")
    os.makedirs(output_dir, exist_ok=True)

    stem = Path(video_path).stem
    print(f"\n{'='*60}")
    print(f"Cover Generation: {stem}")
    print(f"{'='*60}")

    candidates = extract_candidate_frames(video_path, output_dir, num_candidates)

    if not candidates:
        print("  ERROR: No frames extracted", file=sys.stderr)
        return {"video": Path(video_path).name, "candidates": []}

    if ai_score:
        candidates = score_covers_with_ai(candidates)

    result = {
        "video": Path(video_path).name,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "recommended": candidates[:3] if len(candidates) >= 3 else candidates,
    }

    json_path = os.path.join(output_dir, f"covers_{stem}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Results saved: {json_path}")

    for i, c in enumerate(result["recommended"]):
        print(f"  Top {i+1}: {c['timestamp']} (score: {c.get('ai_score', 'N/A')})")

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate cover frame candidates from video")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("-o", "--output-dir", help="Output directory")
    parser.add_argument("-n", "--num-candidates", type=int, default=12, help="Number of candidate frames")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI scoring")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    generate_covers(args.video, args.output_dir, args.num_candidates, not args.no_ai)


if __name__ == "__main__":
    main()

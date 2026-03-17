#!/usr/bin/env python3
"""
ASR 语音转文字脚本

使用火山引擎 ASR（大模型语音识别）或兼容 OpenAI Whisper 接口提取视频中的
台词文本和精确时间戳。输出 JSON 和 SRT 两种格式。

支持模式：
- 火山引擎 ASR API（推荐，精度高）
- 本地 FFmpeg 提取音频 + Whisper 风格 API
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
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


def extract_audio(video_path: str, output_path: str, sample_rate: int = 16000) -> bool:
    """Extract audio track from video as WAV/MP3 for ASR processing."""
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
            output_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  Audio extraction failed: {result.stderr[-300:]}", file=sys.stderr)
        return False
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Audio extracted: {size_mb:.1f}MB")
    return True


def extract_audio_mp3(video_path: str, output_path: str) -> bool:
    """Extract audio as MP3 (smaller for upload)."""
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-c:a", "libmp3lame", "-b:a", "64k", "-ar", "16000", "-ac", "1",
            output_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  MP3 extraction failed: {result.stderr[-300:]}", file=sys.stderr)
        return False
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  MP3 extracted: {size_mb:.1f}MB")
    return True


def seconds_to_srt_time(sec: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def seconds_to_hms(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def utterances_to_srt(utterances: list[dict]) -> str:
    """Convert utterance list to SRT subtitle format."""
    lines = []
    for i, u in enumerate(utterances, 1):
        start = seconds_to_srt_time(u["start_time"])
        end = seconds_to_srt_time(u["end_time"])
        text = u["text"].strip()
        if text:
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")
    return "\n".join(lines)


def asr_via_ark_whisper(audio_path: str) -> list[dict]:
    """
    Use Ark API with Whisper-compatible endpoint for ASR.
    Falls back to segment-level timestamps.
    """
    import base64
    from openai import OpenAI
    import httpx

    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    if not api_key:
        print("ERROR: ARK_API_KEY not set", file=sys.stderr)
        return []

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(600.0, connect=60.0, write=120.0, read=600.0),
        max_retries=2,
    )

    model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    print(f"  Sending audio to Ark API for transcription...")
    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": audio_b64,
                            "format": "mp3" if audio_path.endswith(".mp3") else "wav",
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "请将这段音频转录为逐句文本，每句标注精确的起止时间戳。\n"
                            "输出格式为 JSON 数组，每个元素包含：\n"
                            '- "start_time": 开始时间（秒，保留2位小数）\n'
                            '- "end_time": 结束时间（秒，保留2位小数）\n'
                            '- "text": 该句台词文本\n'
                            '- "speaker": 说话者（如果能区分，否则为 "unknown"）\n\n'
                            "只返回 JSON 数组，不要其他内容。"
                        ),
                    },
                ],
            }],
            max_tokens=16384,
            temperature=0.05,
        )
        elapsed = time.time() - start_time
        print(f"  ASR completed in {elapsed:.1f}s")

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        result = json.loads(content)
        if isinstance(result, list):
            return result
        return []
    except Exception as e:
        print(f"  ASR API error: {e}", file=sys.stderr)
        return []


def asr_via_ffmpeg_silence(video_path: str) -> list[dict]:
    """
    Fallback: use FFmpeg silence detection to find speech segments.
    This is less accurate but works without any API.
    """
    print("  Using FFmpeg silence detection (fallback mode)...")
    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-af", "silencedetect=n=-30dB:d=0.5",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    stderr = result.stderr

    silence_starts = []
    silence_ends = []
    for line in stderr.split("\n"):
        if "silence_start" in line:
            try:
                val = float(line.split("silence_start:")[1].strip().split()[0])
                silence_starts.append(val)
            except (ValueError, IndexError):
                pass
        elif "silence_end" in line:
            try:
                val = float(line.split("silence_end:")[1].strip().split()[0])
                silence_ends.append(val)
            except (ValueError, IndexError):
                pass

    duration = get_video_duration_seconds(video_path)
    utterances = []
    speech_id = 1

    if not silence_starts and not silence_ends:
        utterances.append({
            "start_time": 0.0,
            "end_time": duration,
            "text": f"[Speech segment {speech_id}]",
            "speaker": "unknown",
        })
        return utterances

    if silence_ends and (not silence_starts or silence_ends[0] < silence_starts[0]):
        if silence_ends[0] > 0.5:
            utterances.append({
                "start_time": 0.0,
                "end_time": round(silence_ends[0], 2),
                "text": f"[Speech segment {speech_id}]",
                "speaker": "unknown",
            })
            speech_id += 1

    for i in range(min(len(silence_starts), len(silence_ends))):
        if i + 1 < len(silence_ends):
            seg_start = silence_ends[i] if i < len(silence_ends) else silence_starts[i]
            seg_end = silence_starts[i + 1] if i + 1 < len(silence_starts) else duration
        elif i < len(silence_starts):
            seg_start = silence_starts[i]
            seg_end = silence_ends[i] if i < len(silence_ends) else duration
            continue
        else:
            break

        if seg_end - seg_start > 0.3:
            utterances.append({
                "start_time": round(seg_start, 2),
                "end_time": round(seg_end, 2),
                "text": f"[Speech segment {speech_id}]",
                "speaker": "unknown",
            })
            speech_id += 1

    if silence_starts and silence_starts[-1] < duration - 0.5:
        last_end = silence_ends[-1] if silence_ends and silence_ends[-1] > silence_starts[-1] else silence_starts[-1] + 0.5
        if last_end < duration - 0.3:
            utterances.append({
                "start_time": round(last_end, 2),
                "end_time": round(duration, 2),
                "text": f"[Speech segment {speech_id}]",
                "speaker": "unknown",
            })

    return utterances


def process_video(
    video_path: str,
    output_dir: str | None = None,
    method: str = "auto",
) -> dict:
    """Extract ASR from a single video, output JSON + SRT."""
    project_root = get_project_root()
    if output_dir is None:
        output_dir = str(project_root / "video" / "output")
    os.makedirs(output_dir, exist_ok=True)

    stem = Path(video_path).stem
    duration = get_video_duration_seconds(video_path)

    print(f"\n{'='*60}")
    print(f"ASR: {Path(video_path).name} ({duration:.0f}s)")
    print(f"{'='*60}")

    utterances = []

    if method in ("auto", "ark"):
        mp3_path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
        try:
            if extract_audio_mp3(video_path, mp3_path):
                utterances = asr_via_ark_whisper(mp3_path)
        finally:
            try:
                os.unlink(mp3_path)
            except OSError:
                pass

    if not utterances and method in ("auto", "silence"):
        utterances = asr_via_ffmpeg_silence(video_path)

    if not utterances:
        print("  WARNING: No utterances extracted")
        return {"video": Path(video_path).name, "utterances": [], "duration": duration}

    result = {
        "video": Path(video_path).name,
        "duration": duration,
        "utterance_count": len(utterances),
        "utterances": utterances,
    }

    json_path = os.path.join(output_dir, f"asr_{stem}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  JSON saved: {json_path}")

    srt_content = utterances_to_srt(utterances)
    srt_path = os.path.join(output_dir, f"asr_{stem}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    print(f"  SRT saved: {srt_path}")

    word_count = sum(len(u["text"]) for u in utterances)
    print(f"  Utterances: {len(utterances)}, Characters: {word_count}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract ASR transcripts from video files")
    parser.add_argument("input", help="Video file or directory")
    parser.add_argument("-o", "--output-dir", help="Output directory")
    parser.add_argument(
        "--method", choices=["auto", "ark", "silence"], default="auto",
        help="ASR method: auto (try ark then silence), ark (API only), silence (FFmpeg fallback)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)

    if input_path.is_dir():
        video_files = sorted(
            p for p in input_path.iterdir()
            if p.suffix.lower() in {".mp4", ".mov", ".mpeg", ".webm", ".avi"}
        )
        if not video_files:
            print(f"No video files found in {args.input}")
            sys.exit(1)
        print(f"Found {len(video_files)} video(s)")
        for vf in video_files:
            process_video(str(vf), args.output_dir, args.method)
    elif input_path.is_file():
        process_video(str(input_path), args.output_dir, args.method)
    else:
        print(f"ERROR: {args.input} not found", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

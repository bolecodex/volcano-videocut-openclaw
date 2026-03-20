#!/usr/bin/env python3
"""
AI 解说技能：根据视频内容生成匹配画面的解说配音

流程：分析视频 -> 生成解说词 -> Ark TTS 合成 -> 替换原音轨。
要求：声音有吸引力，与画面匹配。
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


def extract_frames_for_analysis(video_path: str, num_frames: int = 8) -> list[str]:
    """Extract evenly spaced frames as JPEG for narration script generation."""
    duration = get_video_duration_seconds(video_path)
    if duration <= 0:
        return []
    tmp_dir = tempfile.mkdtemp(prefix="narration_frames_")
    paths = []
    for i in range(num_frames):
        t = (i + 1) * duration / (num_frames + 1)
        out_path = os.path.join(tmp_dir, f"frame_{i:02d}.jpg")
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(t), "-i", video_path,
                "-vframes", "1", "-q:v", "2", out_path,
            ],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and os.path.exists(out_path):
            paths.append(out_path)
    return paths


def analyze_video_for_narration(video_path: str, output_dir: str | None = None) -> dict:
    """Use Ark multimodal to describe video content for narration."""
    from openai import OpenAI
    import httpx

    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    if not api_key:
        return {"duration": get_video_duration_seconds(video_path), "summary": ""}

    frames = extract_frames_for_analysis(video_path)
    duration = get_video_duration_seconds(video_path)

    content_parts = []
    for p in frames[:6]:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    prompt = (
        f"这是一段短剧/剧情视频的 {len(content_parts)} 张关键帧截图，视频总时长约 {duration:.0f} 秒。\n\n"
        "请用 2-4 句话概括这段视频的剧情和情绪（谁、发生了什么、情绪基调）。\n"
        "输出 JSON：{\"summary\": \"你的概括\"}。只返回 JSON。"
    )
    content_parts.append({"type": "text", "text": prompt})

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(120.0),
        max_retries=2,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=1024,
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[0].strip() or text.split("```")[1].strip()
        data = json.loads(text)
        data["duration"] = duration
        return data
    except Exception as e:
        print(f"  Narration analysis error: {e}", file=sys.stderr)
        return {"duration": duration, "summary": ""}
    finally:
        for p in frames:
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            os.rmdir(os.path.dirname(frames[0]))
        except OSError:
            pass


def generate_narration_script(video_analysis: dict, video_path: str) -> str:
    """Generate full narration script matching the video."""
    from openai import OpenAI
    import httpx

    load_dotenv(get_project_root() / ".env")
    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("ARK_MODEL_NAME", "doubao-seed-2-0-pro-260215")

    duration = video_analysis.get("duration", 60)
    summary = video_analysis.get("summary", "")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(120.0),
        max_retries=2,
    )

    prompt = (
        f"请为一段短剧投流素材撰写「解说旁白」文案。\n\n"
        f"视频概况：{summary or '剧情片段'}\n"
        f"时长约 {duration:.0f} 秒。\n\n"
        "要求：\n"
        "1. 语言有吸引力、有悬念，适合配音朗读。\n"
        "2. 与画面内容匹配，节奏适中，总字数控制在约 1 字/秒。\n"
        "3. 只输出纯文本旁白，不要序号、不要时间轴。\n"
        "4. 适合女声或男声播音腔，情绪与剧情一致。\n"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  Script generation error: {e}", file=sys.stderr)
        return ""


def synthesize_narration(
    text: str,
    output_audio_path: str,
    voice_id: str = "zh_female_huayan",
    speed: float = 1.0,
) -> bool:
    """
    调用 TTS 合成解说音频。
    支持火山引擎语音合成：设置 ARK_TTS_ENDPOINT（接入点 ID）时使用 Ark 同区 TTS。
    若未配置 TTS，则生成静音占位并保存文案到同目录 .txt。
    """
    load_dotenv(get_project_root() / ".env")
    tts_endpoint = os.getenv("ARK_TTS_ENDPOINT") or os.getenv("ARK_TTS_MODEL")
    api_key = os.getenv("ARK_API_KEY")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    if not text.strip():
        return False

    if tts_endpoint and api_key:
        try:
            from openai import OpenAI
            import httpx
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=httpx.Timeout(60.0))
            # 部分 Ark 模型支持 audio 输出，这里按文本补全接口调用；若实际为专用 TTS API 需替换
            resp = client.chat.completions.create(
                model=tts_endpoint,
                messages=[{"role": "user", "content": text}],
                max_tokens=0,
            )
            # 若返回中有 audio 或 attachment，写入文件
            if hasattr(resp, "choices") and resp.choices and hasattr(resp.choices[0], "message"):
                msg = resp.choices[0].message
                if hasattr(msg, "content") and isinstance(msg.content, bytes):
                    with open(output_audio_path, "wb") as f:
                        f.write(msg.content)
                    return True
        except Exception as e:
            print(f"  TTS API fallback: {e}", file=sys.stderr)

    # 未配置或调用失败：保存文案，生成与字数大致时长的静音
    script_path = output_audio_path.replace(".mp3", ".txt").replace(".wav", "_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(text)
    # 约 3 字/秒，生成静音 wav 供后续替换
    duration_sec = max(10, len(text) / 3)
    wav_out = output_audio_path.replace(".mp3", "_silent.wav")
    if not output_audio_path.endswith(".wav"):
        wav_out = output_audio_path + ".wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(duration_sec), "-acodec", "pcm_s16le", wav_out,
        ],
        capture_output=True,
    )
    if output_audio_path.endswith(".mp3"):
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_out, "-acodec", "libmp3lame", "-q:a", "2", output_audio_path],
            capture_output=True,
        )
        try:
            os.unlink(wav_out)
        except OSError:
            pass
    else:
        import shutil
        shutil.move(wav_out, output_audio_path)
    print(f"  TTS not configured or failed; script saved to {script_path}, placeholder audio to {output_audio_path}")
    return True


def replace_audio_track(video_path: str, audio_path: str, output_path: str) -> bool:
    """Replace video audio with narration track (FFmpeg)."""
    args = [
        "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg replace audio error: {result.stderr[-300:]}", file=sys.stderr)
        return False
    return True


def run_ai_narration(
    video_path: str,
    output_path: str | None = None,
    voice_id: str = "zh_female_huayan",
    speed: float = 1.0,
) -> str | None:
    """Full pipeline: analyze -> script -> TTS -> replace audio. Returns output path or None."""
    if not os.path.exists(video_path):
        print(f"  ERROR: Video not found: {video_path}", file=sys.stderr)
        return None

    output_path = output_path or video_path.replace(".mp4", "_narration.mp4")
    out_dir = str(Path(output_path).parent)
    temp_audio = os.path.join(out_dir, "narration_temp.mp3")

    print("  Analyzing video for narration...")
    analysis = analyze_video_for_narration(video_path, out_dir)
    print("  Generating narration script...")
    script = generate_narration_script(analysis, video_path)
    if not script:
        print("  No script generated", file=sys.stderr)
        return None

    print("  Synthesizing narration audio...")
    if not synthesize_narration(script, temp_audio, voice_id=voice_id, speed=speed):
        return None

    print("  Replacing audio track...")
    if not replace_audio_track(video_path, temp_audio, output_path):
        return None

    try:
        os.unlink(temp_audio)
    except OSError:
        pass

    print(f"  Done: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="AI narration for video (script + TTS + replace audio)")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("-o", "--output", help="Output video path")
    parser.add_argument("--voice", default="zh_female_huayan", help="TTS voice id")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()

    out = run_ai_narration(args.video, args.output, voice_id=args.voice, speed=args.speed)
    sys.exit(0 if out else 1)


if __name__ == "__main__":
    main()

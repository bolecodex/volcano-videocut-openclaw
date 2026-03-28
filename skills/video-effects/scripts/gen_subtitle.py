import argparse
import sys
import subprocess
from pathlib import Path
from shutil import which

from faster_whisper import WhisperModel


def _get_skill_temp_dir():
    skill_dir = Path(__file__).resolve().parents[1]
    temp_dir = skill_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _format_timestamp(seconds):
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def extract_audio(video_path, audio_path):
    if which("ffmpeg") is None:
        raise RuntimeError("ffmpeg 不可用")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)


def transcribe_audio(
    audio_path,
    model_size,
    device,
    compute_type,
    beam_size,
    language,
    vad_filter,
):
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    transcribe_options = {
        "beam_size": beam_size,
        "vad_filter": vad_filter,
    }
    if language:
        transcribe_options["language"] = language
    segments, info = model.transcribe(str(audio_path), **transcribe_options)
    return segments, info


def write_srt(segments, srt_path):
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    index = 0
    with srt_path.open("w", encoding="utf-8") as f:
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            index += 1
            start = _format_timestamp(segment.start)
            end = _format_timestamp(segment.end)
            f.write(f"{index}\n{start} --> {end}\n{text}\n\n")


def _parse_args():
    parser = argparse.ArgumentParser(
        description="本地离线提取字幕（MoviePy + faster-whisper）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python src/local_subtitle.py video.mp4
  python src/local_subtitle.py video.mp4 --model-size large-v3 --device cuda
  python src/local_subtitle.py video.mp4 --output out.srt
        """,
    )
    parser.add_argument("video", help="本地视频路径")
    parser.add_argument("--output", default=None, help="输出字幕路径(.srt)")
    parser.add_argument("--audio", default=None, help="输出音频路径(.wav)")
    parser.add_argument("--model-size", default="small", help="模型名称")
    parser.add_argument("--device", default="cpu", help="cpu 或 cuda")
    parser.add_argument("--compute-type", default="int8", help="推理精度")
    parser.add_argument("--beam-size", type=int, default=1, help="beam size")
    parser.add_argument("--language", default=None, help="语言代码，如 zh, en")
    parser.add_argument("--vad-filter", action="store_true", default=True, help="启用 VAD")
    parser.add_argument("--keep-audio", action="store_true", help="保留中间音频")
    return parser.parse_args()


def main():
    args = _parse_args()
    try:
        video_path = Path(args.video).expanduser().resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"视频不存在: {video_path}")

        temp_dir = _get_skill_temp_dir()
        audio_path = (
            Path(args.audio).expanduser().resolve()
            if args.audio
            else temp_dir / f"{video_path.stem}.wav"
        )
        srt_path = (
            Path(args.output).expanduser().resolve()
            if args.output
            else temp_dir / f"{video_path.stem}.srt"
        )

        print("🎧 提取音频中...")
        extract_audio(video_path, audio_path)
        print(f"✅ 音频已保存: {audio_path}")

        print("📝 生成字幕中...")
        segments, info = transcribe_audio(
            audio_path=audio_path,
            model_size=args.model_size,
            device=args.device,
            compute_type=args.compute_type,
            beam_size=args.beam_size,
            language=args.language,
            vad_filter=args.vad_filter,
        )
        print(
            f"✅ 检测语言: {info.language} (置信度 {info.language_probability:.3f})"
        )

        write_srt(segments, srt_path)
        print(f"✅ 字幕已保存: {srt_path}")

        if not args.keep_audio and audio_path.exists():
            audio_path.unlink()
    except Exception as e:
        print(f"❌ 字幕生成失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

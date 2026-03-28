#!/usr/bin/env python3
"""
音视频分离脚本（ffmpeg-python + Demucs）

- 输出目录：<workspace_root>/outputs/<输入文件名(无扩展名)>/，重复则覆盖。
- 静音视频：mute.<原扩展名>
- 人声：voice.mp3
- 背景音：background.mp3
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import scipy.io.wavfile
import ffmpeg


def run_mute_video(input_file: Path, mute_path: Path) -> Path:
    """视频静音：去除音轨和字幕，输出到 mute_path。"""
    (
        ffmpeg.input(str(input_file))
        .output(str(mute_path), vcodec="copy", an=None, sn=None)
        .global_args("-an", "-sn")
        .run(quiet=True, overwrite_output=True)
    )
    return mute_path


def run_voice_background_separation(
    input_file: Path, output_dir: Path, voice_path: Path, background_path: Path
) -> tuple[Path, Path]:
    """
    人声/背景音分离：提取音频 → Demucs 分离 → 输出 voice.mp3、background.mp3。
    返回 (人声路径, 背景音路径)。
    """
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model

    basename = input_file.stem
    audio_wav = output_dir / f".tmp_{basename}_audio.wav"
    (
        ffmpeg.input(str(input_file))
        .output(
            str(audio_wav),
            format="wav",
            acodec="pcm_s16le",
            ar="44100",
            ac="2",
        )
        .run(quiet=True, overwrite_output=True)
    )

    model = get_model("htdemucs")
    model.cpu()
    wav = AudioFile(str(audio_wav)).read(
        streams=0,
        samplerate=model.samplerate,
        channels=model.audio_channels,
    )
    ref = wav.mean(0)
    wav = wav - ref.mean()
    wav = wav / (ref.std() + 1e-8)
    sources = apply_model(
        model,
        wav[None],
        device="cpu",
        shifts=1,
        split=True,
        overlap=0.25,
        progress=True,
    )[0]
    sources = sources * ref.std() + ref.mean()

    demucs_output = output_dir / ".demucs_output" / "htdemucs" / f"{basename}_audio"
    demucs_output.mkdir(parents=True, exist_ok=True)

    def _save_wav(tensor, path: Path, samplerate: int) -> None:
        arr = tensor.cpu().numpy()
        arr = (arr * 32767).clip(-32768, 32767).astype(np.int16)
        scipy.io.wavfile.write(str(path), samplerate, arr.T)

    vocals_wav = demucs_output / "vocals.wav"
    vocals_idx = model.sources.index("vocals")
    _save_wav(sources[vocals_idx], vocals_wav, model.samplerate)

    bgm_wav = demucs_output / "bgm.wav"
    non_vocals_indices = [i for i, n in enumerate(model.sources) if n != "vocals"]
    _save_wav(sources[non_vocals_indices].sum(0), bgm_wav, model.samplerate)

    (
        ffmpeg.input(str(vocals_wav))
        .output(str(voice_path), format="mp3", acodec="libmp3lame", qscale="2")
        .run(quiet=True, overwrite_output=True)
    )
    (
        ffmpeg.input(str(bgm_wav))
        .output(str(background_path), format="mp3", acodec="libmp3lame", qscale="2")
        .run(quiet=True, overwrite_output=True)
    )

    if audio_wav.exists():
        audio_wav.unlink()
    demucs_dir = output_dir / ".demucs_output"
    if demucs_dir.exists():
        shutil.rmtree(demucs_dir)

    return voice_path, background_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="音视频分离：静音视频 mute.<ext>、人声 voice.mp3、背景 background.mp3"
    )
    parser.add_argument("input_file", help="输入视频/音频路径")
    parser.add_argument(
        "--workspace-root",
        default=".",
        help="工作空间根目录，输出为 <workspace_root>/outputs/<文件名>/（默认当前目录）",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "separate", "mute"],
        default="all",
        help="all=静音视频+人声分离；separate=仅人声/背景；mute=仅静音视频",
    )
    args = parser.parse_args()

    input_file = Path(args.input_file).resolve()
    if not input_file.exists():
        print(f"错误: 输入文件未找到: {input_file}")
        return 1

    workspace_root = Path(args.workspace_root).resolve()

    # output_layout 是 CLI 运行时的可选依赖；被其他脚本 import 时不应阻塞。
    try:
        from .output_layout import (
            get_output_dir,
            get_mute_video_path,
            get_voice_path,
            get_background_path,
        )

        output_dir = get_output_dir(input_file, workspace_root)
        ext = input_file.suffix or ".mp4"
        mute_path = get_mute_video_path(output_dir, ext)
        voice_path = get_voice_path(output_dir)
        background_path = get_background_path(output_dir)
    except Exception:
        output_dir = workspace_root / "outputs" / input_file.stem
        output_dir.mkdir(parents=True, exist_ok=True)
        ext = input_file.suffix or ".mp4"
        mute_path = output_dir / f"mute{ext}"
        voice_path = output_dir / "voice.mp3"
        background_path = output_dir / "background.mp3"

    print("================================================")
    print(f"输入: {input_file}")
    print(f"输出目录: {output_dir}")
    print(f"模式: {args.mode}")
    print("================================================")

    try:
        if args.mode in ("all", "mute"):
            print("\n[视频静音] 去除音轨与字幕...")
            run_mute_video(input_file, mute_path)
            print(f"  -> {mute_path}")

        if args.mode in ("all", "separate"):
            print("\n[人声/背景音分离] Demucs...")
            run_voice_background_separation(
                input_file, output_dir, voice_path, background_path
            )
            print(f"  -> {voice_path}")
            print(f"  -> {background_path}")

        print("\n================================================\n")
        return 0
    except ffmpeg.Error as e:
        err = e.stderr.decode("utf-8") if e.stderr else str(e)
        print(f"错误: FFmpeg 执行失败: {err}")
        return 1
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

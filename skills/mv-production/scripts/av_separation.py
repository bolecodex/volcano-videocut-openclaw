#!/usr/bin/env python3
"""
M0_AV_SEPARATION：人声 / 背景音分离（Demucs + ffmpeg）

约定（与 mv-production/SKILL.md 一致）：
- 输入：song.mp3（或任意音频文件）
- 输出到 --output-dir：
  - voice.mp3
  - background.mp3
  - （可选）.demucs_output/ 临时目录会自动清理
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import scipy.io.wavfile
import subprocess

from ffmpeg_exe import get_ffmpeg_exe

FFMPEG_EXE = get_ffmpeg_exe()


def separate_voice_background(input_audio: Path, output_dir: Path) -> tuple[Path, Path]:
    """
    提取音频为 wav → Demucs 分离 → 转 mp3 输出 voice/background。
    返回 (voice_path, background_path)。
    """
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model

    output_dir.mkdir(parents=True, exist_ok=True)

    basename = input_audio.stem
    audio_wav = output_dir / f".tmp_{basename}_audio.wav"

    # 提取/转码为标准 wav，保证 demucs 输入稳定（使用 imageio-ffmpeg 内置 ffmpeg 可执行文件）
    subprocess.run(
        [
            FFMPEG_EXE,
            "-i",
            str(input_audio),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(audio_wav),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
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

    voice_mp3 = output_dir / "voice.mp3"
    background_mp3 = output_dir / "background.mp3"

    subprocess.run(
        [
            FFMPEG_EXE,
            "-i",
            str(vocals_wav),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(voice_mp3),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    subprocess.run(
        [
            FFMPEG_EXE,
            "-i",
            str(bgm_wav),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(background_mp3),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )

    # 清理临时文件
    if audio_wav.exists():
        audio_wav.unlink()
    demucs_dir = output_dir / ".demucs_output"
    if demucs_dir.exists():
        shutil.rmtree(demucs_dir)

    return voice_mp3, background_mp3


def main() -> int:
    parser = argparse.ArgumentParser(description="人声/背景音分离（Demucs）")
    parser.add_argument("input_audio", help="输入音频文件路径（如 output_dir/song.mp3）")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="输出目录（将写入 voice.mp3/background.mp3）",
    )
    args = parser.parse_args()

    input_audio = Path(args.input_audio).expanduser().resolve()
    if not input_audio.exists():
        print(f"错误：输入文件不存在: {input_audio}")
        return 1

    output_dir = Path(args.output_dir).expanduser().resolve()
    try:
        voice, bg = separate_voice_background(input_audio, output_dir)
        print(f"分离完成：\n- 人声: {voice}\n- 背景音: {bg}")
        return 0
    except Exception as e:
        print(f"错误：{e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

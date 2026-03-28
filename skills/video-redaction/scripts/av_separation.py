#!/usr/bin/env python3
"""
音视频分离脚本（使用 ffmpeg-python 和 Demucs）

支持能力：
1. 人声背景音分离：使用 Demucs 将音频分离为人声与背景音，输出 MP3
2. 视频静音处理：去除视频音轨与字幕，输出无音频视频
3. 完整流程：上述两者均执行（默认）
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import scipy.io.wavfile
import ffmpeg


def run_mute_video(input_file: Path, output_dir: Path, basename: str) -> Path:
    """视频静音处理：去除音轨和字幕，输出无音频视频。"""
    video_only = output_dir / f"{basename}_muted.mp4"
    (
        ffmpeg.input(str(input_file))
        .output(str(video_only), vcodec="copy", an=None, sn=None)
        .global_args("-an", "-sn")
        .run(quiet=True, overwrite_output=True)
    )
    return video_only


def run_voice_background_separation(
    input_file: Path, output_dir: Path, basename: str
) -> tuple[Path, Path]:
    """
    人声背景音分离：提取音频后用 Demucs 分离人声与背景音，输出 MP3。
    返回 (人声路径, 背景音路径)。
    """
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model

    # 1. 提取音频为 WAV
    audio_wav = output_dir / f"{basename}_audio.wav"
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

    # 2. Demucs 分离（使用 apply_model，与官方 separate 一致）
    model = get_model("htdemucs")
    model.cpu()
    wav = AudioFile(str(audio_wav)).read(
        streams=0,
        samplerate=model.samplerate,
        channels=model.audio_channels,
    )
    # 归一化，与 demucs.separate 一致，提升分离效果
    ref = wav.mean(0)
    wav = wav - ref.mean()
    wav = wav / (ref.std() + 1e-8)
    # apply_model 返回 (batch, sources, channels, length)，取 [0] 得到 (sources, channels, length)
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

    demucs_output = (
        output_dir / "demucs_output" / "htdemucs" / f"{basename}_audio"
    )
    demucs_output.mkdir(parents=True, exist_ok=True)

    def _save_wav(tensor, path: Path, samplerate: int) -> None:
        """用 scipy 写 WAV，避免 torchaudio.save 触发的 torchcodec/FFmpeg 依赖。"""
        arr = tensor.cpu().numpy()
        arr = (arr * 32767).clip(-32768, 32767).astype(np.int16)
        scipy.io.wavfile.write(str(path), samplerate, arr.T)

    vocals_wav = demucs_output / "vocals.wav"
    vocals_idx = model.sources.index("vocals")
    vocals = sources[vocals_idx]
    _save_wav(vocals, vocals_wav, model.samplerate)

    # Demucs 默认是多轨（如 drums/bass/other/vocals），这里将除人声外的所有轨道相加作为背景音
    bgm_wav = demucs_output / "bgm.wav"
    non_vocals_indices = [i for i, name in enumerate(model.sources) if name != "vocals"]
    bgm = sources[non_vocals_indices].sum(0)
    _save_wav(bgm, bgm_wav, model.samplerate)

    # 3. 转 MP3
    vocals_mp3 = output_dir / f"{basename}_vocals.mp3"
    (
        ffmpeg.input(str(vocals_wav))
        .output(str(vocals_mp3), format="mp3", acodec="libmp3lame", qscale="2")
        .run(quiet=True, overwrite_output=True)
    )
    bgm_mp3 = output_dir / f"{basename}_bgm.mp3"
    (
        ffmpeg.input(str(bgm_wav))
        .output(str(bgm_mp3), format="mp3", acodec="libmp3lame", qscale="2")
        .run(quiet=True, overwrite_output=True)
    )

    # 清理临时文件
    if audio_wav.exists():
        audio_wav.unlink()
    demucs_dir = output_dir / "demucs_output"
    if demucs_dir.exists():
        shutil.rmtree(demucs_dir)

    return vocals_mp3, bgm_mp3


def main():
    parser = argparse.ArgumentParser(
        description="音视频分离脚本：人声背景音分离、视频静音处理（ffmpeg + Demucs）"
    )
    parser.add_argument("input_file", help="输入视频/音频文件路径")
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="./output",
        help="输出目录（默认：./output）",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "separate", "mute"],
        default="all",
        help="运行模式：all=人声分离+静音视频；separate=仅人声背景音分离；mute=仅视频静音",
    )
    args = parser.parse_args()

    input_file = Path(args.input_file).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not input_file.exists():
        print(f"错误: 输入文件未找到: {input_file}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    basename = input_file.stem

    print("================================================")
    print(f"输入: {input_file}")
    print(f"输出目录: {output_dir}")
    print(f"模式: {args.mode}")
    print("================================================")

    try:
        outputs = []

        if args.mode in ("all", "mute"):
            print("\n[视频静音处理] 去除音轨与字幕...")
            muted_path = run_mute_video(input_file, output_dir, basename)
            outputs.append(("静音视频", muted_path))

        if args.mode in ("all", "separate"):
            print("\n[人声背景音分离] 使用 Demucs 分离...")
            vocals_mp3, bgm_mp3 = run_voice_background_separation(
                input_file, output_dir, basename
            )
            outputs.append(("人声", vocals_mp3))
            outputs.append(("背景音", bgm_mp3))

        print("\n================================================")
        print("处理完成，输出文件:")
        print("================================================")
        for name, path in outputs:
            print(f"  - {name}: {path}")
        print("================================================\n")
        return 0

    except ffmpeg.Error as e:
        err = e.stderr.decode("utf-8") if e.stderr else str(e)
        print(f"错误: FFmpeg 执行失败: {err}")
        return 1
    except FileNotFoundError as e:
        print(f"错误: 文件未找到: {e}")
        return 1
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
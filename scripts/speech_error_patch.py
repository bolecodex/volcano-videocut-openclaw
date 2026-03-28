#!/usr/bin/env python3
"""
在视频的指定时间窗内，用 TTS 合成的「正确读音」替换原音轨片段（口误 / 错字纠正）。

适用：Seedance 2.0 等生成的口播视频仅个别字读错；保留画面与其它时段音频，只替换一小段。

依赖：FFmpeg、ffprobe；TTS 与 scripts/ai_narration.py 的 synthesize_narration 相同（ARK_TTS_* + ARK_API_KEY）。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

# 复用项目内 TTS
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_narration import get_video_duration_seconds, synthesize_narration  # noqa: E402


def get_audio_duration(path: str) -> float:
    r = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return 0.0
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def run_ffmpeg(args: list[str]) -> None:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "")[-800:]
        raise RuntimeError(f"FFmpeg failed: {tail}")


def extract_full_audio_wav(video: str, out_wav: str, sample_rate: int = 48000) -> None:
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-i", video,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "2",
            out_wav,
        ]
    )


def normalize_patch_to_slot(patch_in: str, patch_out: str, slot_sec: float) -> None:
    """将补丁音频变为与 slot 等长的 48k stereo wav（不足补静音，过长截断）。"""
    dur = get_audio_duration(patch_in)
    if dur <= 0:
        raise RuntimeError("补丁音频时长为 0，请检查 TTS 是否成功")

    if dur > slot_sec + 0.02:
        # 略长于窗口：截到窗口长度（极端情况可能切到半个音节）
        run_ffmpeg(
            [
                "ffmpeg", "-y", "-i", patch_in,
                "-af", f"atrim=0:{slot_sec:.6f},asetpts=PTS-STARTPTS",
                "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2",
                patch_out,
            ]
        )
        return

    pad = max(0.0, slot_sec - dur)
    if pad < 0.001:
        run_ffmpeg(
            [
                "ffmpeg", "-y", "-i", patch_in,
                "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2",
                patch_out,
            ]
        )
        return

    run_ffmpeg(
        [
            "ffmpeg", "-y", "-i", patch_in,
            "-af", f"apad=pad_dur={pad:.6f},atrim=0:{slot_sec:.6f},asetpts=PTS-STARTPTS",
            "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2",
            patch_out,
        ]
    )


def splice_audio(full_wav: str, patch_wav: str, start: float, end: float, out_wav: str) -> None:
    """full_wav 与 patch_wav 均为 48k stereo pcm；用 patch 替换 [start, end)。"""
    # atrim: end = 该时刻起丢弃之后；start = 从该时刻起输出
    fc = (
        f"[0:a]atrim=start=0:end={start:.6f},asetpts=PTS-STARTPTS[a0];"
        f"[0:a]atrim=start={end:.6f},asetpts=PTS-STARTPTS[a2];"
        f"[1:a]asetpts=PTS-STARTPTS[p];"
        f"[a0][p][a2]concat=n=3:v=0:a=1[aout]"
    )
    run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-i", full_wav,
            "-i", patch_wav,
            "-filter_complex", fc,
            "-map", "[aout]",
            "-acodec", "pcm_s16le",
            out_wav,
        ]
    )


def mux_video_audio(video: str, audio_wav: str, output: str) -> None:
    run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-i", video,
            "-i", audio_wav,
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            output,
        ]
    )


def patch_speech_segment(
    video_path: str,
    start_sec: float,
    end_sec: float,
    correct_text: str,
    output_path: str | None,
    voice_id: str,
    speed: float,
) -> str:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    if end_sec <= start_sec:
        raise ValueError("end 必须大于 start")
    slot = end_sec - start_sec
    if slot < 0.05:
        raise ValueError("替换窗口过短（<0.05s），请适当放宽 end-start")

    vdur = get_video_duration_seconds(video_path)
    if vdur > 0 and end_sec > vdur + 0.05:
        raise ValueError(f"end 超过视频时长（约 {vdur:.2f}s）")

    out = output_path or (
        str(Path(video_path).with_name(Path(video_path).stem + "_speechfix.mp4"))
    )

    with tempfile.TemporaryDirectory(prefix="speech_patch_") as tmp:
        full_wav = os.path.join(tmp, "full.wav")
        patch_raw = os.path.join(tmp, "patch_raw.mp3")
        patch_fit = os.path.join(tmp, "patch_fit.wav")
        merged = os.path.join(tmp, "merged.wav")

        print("  提取原音轨…")
        extract_full_audio_wav(video_path, full_wav)

        print(f"  TTS 合成纠正文案（{len(correct_text)} 字）…")
        if not synthesize_narration(correct_text.strip(), patch_raw, voice_id=voice_id, speed=speed):
            raise RuntimeError("TTS 合成失败（检查 ARK_API_KEY、ARK_TTS_ENDPOINT / ARK_TTS_MODEL）")

        print(f"  对齐补丁时长到窗口 {slot:.3f}s…")
        normalize_patch_to_slot(patch_raw, patch_fit, slot)

        print("  拼接音轨…")
        splice_audio(full_wav, patch_fit, start_sec, end_sec, merged)

        print(f"  写入成片: {out}")
        mux_video_audio(video_path, merged, out)

    return out


def main() -> None:
    p = argparse.ArgumentParser(
        description="替换视频中指定时间窗内的语音（TTS 纠正错读/口误）",
    )
    p.add_argument("video", help="输入视频路径")
    p.add_argument("--start", type=float, required=True, help="替换起点（秒，含）")
    p.add_argument("--end", type=float, required=True, help="替换终点（秒，不含）")
    p.add_argument("--text", required=True, help="该窗口内应读出的正确文本（通常很短，如单个词）")
    p.add_argument("-o", "--output", help="输出 mp4，默认与输入同目录 *_speechfix.mp4")
    p.add_argument("--voice", default="zh_female_huayan", help="TTS 音色 id")
    p.add_argument("--speed", type=float, default=1.0, help="TTS 语速")
    args = p.parse_args()

    if not os.path.isfile(args.video):
        print(f"ERROR: 文件不存在: {args.video}", file=sys.stderr)
        sys.exit(1)

    try:
        out = patch_speech_segment(
            args.video,
            args.start,
            args.end,
            args.text,
            args.output,
            args.voice,
            args.speed,
        )
        print(out)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

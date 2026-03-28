#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import ffmpeg


def log(msg: str) -> None:
    print(f"[merge_av] {msg}", flush=True)


def normalize_output_audio_path(path: Path) -> Path:
    # Some shells/editors may pass backup-like names such as *.wav~.
    name = path.name
    if name.endswith("~"):
        while name.endswith("~"):
            name = name[:-1]
        fixed = path.with_name(name)
        log(f"normalize output audio path: {path} -> {fixed}")
        path = fixed
    return path


def audio_mux_format(path: Path) -> str:
    ext = path.suffix.lower()
    mapping = {
        ".wav": "wav",
        ".mp3": "mp3",
        ".m4a": "ipod",
        ".aac": "adts",
        ".flac": "flac",
    }
    if ext not in mapping:
        raise ValueError(
            f"不支持的输出音频后缀: {path.name}。请使用 .wav/.mp3/.m4a/.aac/.flac"
        )
    return mapping[ext]


def load_asr_segments(asr_split_json: Path) -> list[dict[str, Any]]:
    with open(asr_split_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    segments = data.get("segments") or []
    if not isinstance(segments, list):
        raise ValueError(f"Invalid asr_split format: {asr_split_json}")
    cleaned: list[dict[str, Any]] = []
    for i, seg in enumerate(segments, start=1):
        if "start" not in seg or "end" not in seg:
            continue
        start = float(seg["start"])
        end = float(seg["end"])
        if end <= start:
            continue
        seg_id = int(seg.get("id", i))
        cleaned.append({"id": seg_id, "start": start, "end": end})
    cleaned.sort(key=lambda x: (x["start"], x["id"]))
    return cleaned


def ffprobe_duration(path: Path) -> float:
    meta = ffmpeg.probe(str(path))
    return float(meta["format"]["duration"])


def run_ffmpeg_with_retry(builder, retries: int, stage: str) -> None:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            builder()
            return
        except ffmpeg.Error as e:
            last_err = e
            msg = e.stderr.decode() if e.stderr else str(e)
            log(f"{stage} failed at attempt {attempt}/{retries}: {msg}")
        except Exception as exc:
            last_err = exc
            log(f"{stage} failed at attempt {attempt}/{retries}: {exc}")
    raise RuntimeError(f"{stage} failed after {retries} attempts: {last_err}")


def find_tts_file(tts_dir: Path, seg_id: int) -> Path | None:
    candidates = [
        tts_dir / f"segment_tts_{seg_id:04d}.wav",
        tts_dir / f"segment_tts_{seg_id:04d}.mp3",
        tts_dir / f"segment_tts_{seg_id:03d}.wav",
        tts_dir / f"segment_tts_{seg_id:03d}.mp3",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def process_segment_audio(
    src: Path,
    slot_duration: float,
    max_speed: float,
    work_dir: Path,
    retries: int,
) -> tuple[Path, dict[str, int]]:
    duration = ffprobe_duration(src)
    stats = {"silence_trimmed": 0, "sped_up": 0}

    # 1) Remove head/tail silence first to reduce perceived clipping.
    cleaned_path = work_dir / f"{src.stem}.clean.wav"

    def _trim_silence():
        stream = ffmpeg.input(str(src)).audio
        stream = stream.filter(
            "silenceremove",
            start_periods=1,
            start_duration=0.05,
            start_threshold="-40dB",
        )
        stream = stream.filter("areverse")
        stream = stream.filter(
            "silenceremove",
            start_periods=1,
            start_duration=0.05,
            start_threshold="-40dB",
        )
        stream = stream.filter("areverse")
        (
            ffmpeg.output(stream, str(cleaned_path), ac=2, ar=48000, acodec="pcm_s16le")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

    run_ffmpeg_with_retry(_trim_silence, retries, f"trim silence segment {src.name}")
    cleaned_duration = ffprobe_duration(cleaned_path)
    # Keep source if silence trim is too aggressive.
    if cleaned_duration > 0.05 and cleaned_duration < duration:
        src = cleaned_path
        duration = cleaned_duration
        stats["silence_trimmed"] = 1

    # Micro speed tuning: only when segment still longer than adjusted slot.
    if slot_duration > 0 and duration > slot_duration:
        required_speed = duration / slot_duration
        applied_speed = min(max_speed, required_speed)
        # only apply when meaningful
        if applied_speed > 1.01:
            sped_path = work_dir / f"{src.stem}.spd.wav"

            def _speedup():
                stream = ffmpeg.input(str(src)).audio
                stream = stream.filter("atempo", max(1.0, min(2.0, applied_speed)))
                (
                    ffmpeg.output(stream, str(sped_path), ac=2, ar=48000, acodec="pcm_s16le")
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )

            run_ffmpeg_with_retry(_speedup, retries, f"micro speedup segment {src.name}")
            src = sped_path
            stats["sped_up"] = 1

    return src, stats


def build_dubbed_audio(
    segments: list[dict[str, Any]],
    tts_dir: Path,
    out_audio: Path,
    total_duration: float,
    max_speed: float,
    retries: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="merge_av_") as td:
        work_dir = Path(td)
        delayed_streams = []
        used = 0
        missing = 0
        silence_trimmed = 0
        gap_extended = 0
        sped_up = 0

        for idx, seg in enumerate(segments):
            seg_id = seg["id"]
            tts_file = find_tts_file(tts_dir, seg_id)
            if not tts_file:
                missing += 1
                log(f"skip segment {seg_id}: tts file not found")
                continue

            start = float(seg["start"])
            end = float(seg["end"])
            slot = max(0.0, end - start)
            prev_end = float(segments[idx - 1]["end"]) if idx > 0 else 0.0
            next_start = float(segments[idx + 1]["start"]) if idx + 1 < len(segments) else total_duration
            pre_gap = max(0.0, start - prev_end)
            post_gap = max(0.0, next_start - end)

            processed, seg_stats = process_segment_audio(
                tts_file,
                slot + pre_gap + post_gap,
                max_speed,
                work_dir,
                retries,
            )
            silence_trimmed += seg_stats["silence_trimmed"]
            sped_up += seg_stats["sped_up"]
            duration_after_clean = ffprobe_duration(processed)
            overflow = max(0.0, duration_after_clean - slot)
            pre_borrow = min(pre_gap, overflow * 0.5)
            post_borrow = min(post_gap, max(0.0, overflow - pre_borrow))
            placement_start = max(0.0, start - pre_borrow)
            if pre_borrow > 1e-3 or post_borrow > 1e-3:
                gap_extended += 1

            delay_ms = int(placement_start * 1000)
            stream = ffmpeg.input(str(processed)).audio
            stream = stream.filter("aformat", sample_fmts="s16", sample_rates=48000, channel_layouts="stereo")
            stream = stream.filter("adelay", f"{delay_ms}|{delay_ms}")
            delayed_streams.append(stream)
            used += 1

        if not delayed_streams:
            # No usable TTS segments: generate silence track.
            (
                ffmpeg.input("anullsrc=r=48000:cl=stereo", f="lavfi", t=total_duration)
                .output(str(out_audio), acodec="pcm_s16le")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return {
                "used_segments": 0,
                "missing_segments": missing,
                "silence_trimmed_segments": 0,
                "gap_extended_segments": 0,
                "sped_up_segments": 0,
            }

        mixed = ffmpeg.filter(delayed_streams, "amix", inputs=len(delayed_streams), dropout_transition=0, normalize=0)
        # Force exact total duration to avoid drift.
        mixed = mixed.filter("atrim", duration=total_duration).filter("asetpts", "N/SR/TB")
        (
            ffmpeg.output(mixed, str(out_audio), ac=2, ar=48000, acodec="pcm_s16le")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return {
            "used_segments": used,
            "missing_segments": missing,
            "silence_trimmed_segments": silence_trimmed,
            "gap_extended_segments": gap_extended,
            "sped_up_segments": sped_up,
        }


def mix_with_background(
    dubbed_audio: Path,
    background_audio: Path,
    out_audio: Path,
    total_duration: float,
    dubbed_volume: float,
    bg_volume: float,
    retries: int,
) -> None:
    out_fmt = audio_mux_format(out_audio)

    def _mix():
        dubbed = ffmpeg.input(str(dubbed_audio)).audio
        bg = ffmpeg.input(str(background_audio)).audio

        dubbed = (
            dubbed.filter("aformat", sample_fmts="s16", sample_rates=48000, channel_layouts="stereo")
            .filter("volume", dubbed_volume)
            .filter("atrim", duration=total_duration)
            .filter("asetpts", "N/SR/TB")
        )
        bg = (
            bg.filter("aformat", sample_fmts="s16", sample_rates=48000, channel_layouts="stereo")
            .filter("volume", bg_volume)
            .filter("apad")
            .filter("atrim", duration=total_duration)
            .filter("asetpts", "N/SR/TB")
        )
        mixed = ffmpeg.filter([dubbed, bg], "amix", inputs=2, dropout_transition=0, normalize=0)
        (
            ffmpeg.output(mixed, str(out_audio), f=out_fmt, ac=2, ar=48000, acodec="pcm_s16le")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

    run_ffmpeg_with_retry(_mix, retries, "mix dubbed with background")


def mux_video_audio(muted_video: Path, dubbed_audio: Path, output_video: Path, retries: int) -> None:
    def _mux():
        v = ffmpeg.input(str(muted_video)).video
        a = ffmpeg.input(str(dubbed_audio)).audio
        (
            ffmpeg.output(v, a, str(output_video), vcodec="copy", acodec="aac", shortest=None)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

    run_ffmpeg_with_retry(_mux, retries, "mux final video")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="按 asr_split 时间轴合并 TTS 片段并与静音视频合成最终视频（去静音→借间隔软对齐）"
    )
    parser.add_argument("--muted-video", required=True, help="静音视频路径（如 muted_video.mp4）")
    parser.add_argument("--asr-split-json", required=True, help="asr_split.json 路径")
    parser.add_argument("--tts-dir", required=True, help="TTS 片段目录（如 tts/en）")
    parser.add_argument("--background-audio", required=True, help="背景音路径（如 background.mp3）")
    parser.add_argument("--output-video", required=True, help="输出视频路径（如 xxx_translate_video.mp4）")
    parser.add_argument(
        "--output-audio",
        default=None,
        help="可选，输出最终混合音轨路径（默认与 output-video 同目录，文件名 dubbed_track.wav）",
    )
    parser.add_argument("--dubbed-volume", type=float, default=1.0, help="配音轨音量（默认 1.0）")
    parser.add_argument("--background-volume", type=float, default=0.35, help="背景音音量（默认 0.35）")
    parser.add_argument(
        "--max-speed",
        type=float,
        default=1.2,
        help="超长片段倍速微调上限（默认 1.2，仅在片段超出可用时长时启用）",
    )
    parser.add_argument("--retry-times", type=int, default=3, help="ffmpeg 阶段失败重试次数（默认 3）")
    args = parser.parse_args()

    muted_video = Path(args.muted_video).resolve()
    asr_split_json = Path(args.asr_split_json).resolve()
    tts_dir = Path(args.tts_dir).resolve()
    background_audio = Path(args.background_audio).resolve()
    output_video = Path(args.output_video).resolve()
    output_video.parent.mkdir(parents=True, exist_ok=True)
    output_audio = (
        Path(args.output_audio).resolve()
        if args.output_audio
        else output_video.parent / "dubbed_track.wav"
    )
    output_audio = normalize_output_audio_path(output_audio)
    output_audio.parent.mkdir(parents=True, exist_ok=True)

    if not muted_video.exists():
        print(f"错误: muted video 不存在: {muted_video}")
        return 1
    if not asr_split_json.exists():
        print(f"错误: asr_split.json 不存在: {asr_split_json}")
        return 1
    if not tts_dir.exists():
        print(f"错误: tts 目录不存在: {tts_dir}")
        return 1
    if not background_audio.exists():
        print(f"错误: background audio 不存在: {background_audio}")
        return 1
    try:
        audio_mux_format(output_audio)
    except ValueError as exc:
        print(f"错误: {exc}")
        return 1

    retries = max(1, int(args.retry_times))
    max_speed = max(1.0, min(1.2, float(args.max_speed)))
    dubbed_volume = max(0.0, float(args.dubbed_volume))
    background_volume = max(0.0, float(args.background_volume))

    try:
        segments = load_asr_segments(asr_split_json)
        if not segments:
            print(f"错误: asr_split 无有效 segments: {asr_split_json}")
            return 1

        total_duration = ffprobe_duration(muted_video)
        log(
            f"segments={len(segments)} total_duration={total_duration:.3f}s "
            f"max_speed={max_speed} dubbed_volume={dubbed_volume} background_volume={background_volume}"
        )
        with tempfile.TemporaryDirectory(prefix="merge_av_main_") as td:
            tmp_dubbed_audio = Path(td) / "dubbed_only.wav"
            stats = build_dubbed_audio(
                segments=segments,
                tts_dir=tts_dir,
                out_audio=tmp_dubbed_audio,
                total_duration=total_duration,
                max_speed=max_speed,
                retries=retries,
            )
            log(f"dubbed-only track generated: {tmp_dubbed_audio}")
            log(f"Output audio path: {output_audio}")
            mix_with_background(
                dubbed_audio=tmp_dubbed_audio,
                background_audio=background_audio,
                out_audio=output_audio,
                total_duration=total_duration,
                dubbed_volume=dubbed_volume,
                bg_volume=background_volume,
                retries=retries,
            )
        log(f"final mixed track generated: {output_audio}")
        log(
            "stats "
            + json.dumps(
                {
                    "used_segments": stats["used_segments"],
                    "missing_segments": stats["missing_segments"],
                    "silence_trimmed_segments": stats["silence_trimmed_segments"],
                    "gap_extended_segments": stats["gap_extended_segments"],
                    "sped_up_segments": stats["sped_up_segments"],
                },
                ensure_ascii=False,
            )
        )

        mux_video_audio(muted_video, output_audio, output_video, retries)
        log(f"final video generated: {output_video}")
        return 0
    except Exception as exc:
        print(f"错误: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

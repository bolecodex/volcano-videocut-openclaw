#!/usr/bin/env python3
"""
FFmpeg 视频切片合并脚本 (S-Level Enhanced)

支持跨集剪辑：从多个源视频文件中切取段落，合并成一个素材视频。
每个 segment 通过 source_file 指定来自哪个源视频。

增强功能：
- 帧级精确切割（重编码模式，默认开启）
- 片段间智能转场（crossfade / dip-to-black）
- 音频归一化（loudnorm 滤镜）
- 多版本批量输出
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def time_to_seconds(t: str) -> float:
    parts = t.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def run_ffmpeg(args: list[str], desc: str = "") -> bool:
    cmd = ["ffmpeg", "-y"] + args
    if desc:
        print(f"  {desc}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[-500:]}", file=sys.stderr)
        return False
    return True


def cut_segment_precise(
    source_video: str,
    start_time: str,
    end_time: str,
    output_path: str,
    reencode: bool = True,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
) -> bool:
    """Cut a segment with frame-level precision using re-encoding."""
    start_sec = time_to_seconds(start_time)
    end_sec = time_to_seconds(end_time)
    duration = end_sec - start_sec

    if duration <= 0:
        print(f"  WARNING: Invalid segment {start_time}-{end_time}, skipping", file=sys.stderr)
        return False

    if reencode:
        vf_parts = []
        af_parts = []

        if fade_in > 0:
            vf_parts.append(f"fade=t=in:st=0:d={fade_in}")
            af_parts.append(f"afade=t=in:st=0:d={fade_in}")
        if fade_out > 0:
            fade_start = max(0, duration - fade_out)
            vf_parts.append(f"fade=t=out:st={fade_start}:d={fade_out}")
            af_parts.append(f"afade=t=out:st={fade_start}:d={fade_out}")

        vf = ",".join(vf_parts) if vf_parts else None
        af = ",".join(af_parts) if af_parts else None

        args = [
            "-ss", str(start_sec),
            "-i", source_video,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
        ]
        if vf:
            args.extend(["-vf", vf])
        if af:
            args.extend(["-af", af])
        args.extend(["-avoid_negative_ts", "make_zero", output_path])
    else:
        args = [
            "-ss", str(start_sec),
            "-i", source_video,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]

    return run_ffmpeg(args, f"Cut {Path(source_video).name} {start_time}->{end_time} ({duration:.1f}s)")


def concat_with_crossfade(
    segment_files: list[str],
    output_path: str,
    crossfade_duration: float = 0.0,
    normalize_audio: bool = True,
) -> bool:
    """Concatenate segments with optional crossfade transitions and audio normalization."""
    if not segment_files:
        print("  No segments to concatenate", file=sys.stderr)
        return False

    if len(segment_files) == 1:
        if normalize_audio:
            args = [
                "-i", segment_files[0],
                "-c:v", "copy",
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ]
            return run_ffmpeg(args, f"Normalizing audio -> {Path(output_path).name}")
        else:
            shutil.copy2(segment_files[0], output_path)
            print(f"  Single segment, copied to {Path(output_path).name}")
            return True

    if crossfade_duration > 0 and len(segment_files) >= 2:
        return _concat_crossfade(segment_files, output_path, crossfade_duration, normalize_audio)

    return _concat_standard(segment_files, output_path, normalize_audio)


def _concat_standard(segment_files: list[str], output_path: str, normalize_audio: bool) -> bool:
    """Standard concat with re-encoding."""
    filter_parts = []
    inputs = []
    for i, seg in enumerate(segment_files):
        inputs.extend(["-i", seg])
        filter_parts.append(f"[{i}:v:0][{i}:a:0]")

    af_chain = ""
    if normalize_audio:
        af_chain = ",loudnorm=I=-16:TP=-1.5:LRA=11"

    filter_str = (
        "".join(filter_parts)
        + f"concat=n={len(segment_files)}:v=1:a=1[outv][outa_raw];"
        + f"[outa_raw]aresample=async=1{af_chain}[outa]"
    )

    args = inputs + [
        "-filter_complex", filter_str,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    return run_ffmpeg(args, f"Merging {len(segment_files)} segments -> {Path(output_path).name}")


def _concat_crossfade(
    segment_files: list[str],
    output_path: str,
    xfade_dur: float,
    normalize_audio: bool,
) -> bool:
    """Concat with crossfade transitions between segments."""
    n = len(segment_files)
    if n < 2:
        return _concat_standard(segment_files, output_path, normalize_audio)

    inputs = []
    for seg in segment_files:
        inputs.extend(["-i", seg])

    durations = []
    for seg in segment_files:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", seg],
            capture_output=True, text=True,
        )
        durations.append(float(result.stdout.strip()) if result.returncode == 0 else 5.0)

    filter_lines = []
    offsets = []
    cumulative = 0.0
    for i in range(n - 1):
        cumulative += durations[i] - xfade_dur
        offsets.append(cumulative)

    if n == 2:
        filter_lines.append(
            f"[0:v][1:v]xfade=transition=fade:duration={xfade_dur}:offset={offsets[0]:.3f}[outv];"
            f"[0:a][1:a]acrossfade=d={xfade_dur}[outa_raw]"
        )
    else:
        prev_v = "[0:v]"
        prev_a = "[0:a]"
        for i in range(1, n):
            out_v = "[outv]" if i == n - 1 else f"[v{i}]"
            out_a = "[outa_raw]" if i == n - 1 else f"[a{i}]"
            offset = offsets[i - 1] if i - 1 < len(offsets) else 0
            filter_lines.append(
                f"{prev_v}[{i}:v]xfade=transition=fade:duration={xfade_dur}:offset={offset:.3f}{out_v};"
                f"{prev_a}[{i}:a]acrossfade=d={xfade_dur}{out_a}"
            )
            prev_v = out_v
            prev_a = out_a

    filter_str = ";".join(filter_lines)
    if normalize_audio:
        filter_str += ";[outa_raw]loudnorm=I=-16:TP=-1.5:LRA=11[outa]"
        audio_map = "[outa]"
    else:
        filter_str = filter_str.replace("[outa_raw]", "[outa]")
        audio_map = "[outa]"

    args = inputs + [
        "-filter_complex", filter_str,
        "-map", "[outv]", "-map", audio_map,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    return run_ffmpeg(args, f"Crossfade merging {n} segments ({xfade_dur}s transitions)")


def resolve_source_path(source_file: str, video_dir: str) -> str:
    """Resolve source_file to an absolute path, searching in video_dir."""
    if os.path.isabs(source_file) and os.path.exists(source_file):
        return source_file
    candidate = os.path.join(video_dir, source_file)
    if os.path.exists(candidate):
        return candidate
    candidate = os.path.join(video_dir, os.path.basename(source_file))
    if os.path.exists(candidate):
        return candidate
    return source_file


def _process_segment_order(
    data: dict,
    video_dir: str,
    temp_dir: str,
    reencode: bool = True,
    version_suffix: str = "",
) -> tuple[list[str], float]:
    """Process segments from analysis data and return cut files + total duration."""
    segments = data.get("segments_to_keep", [])
    hook = data.get("hook", {})
    hook_enabled = hook.get("enabled", False)
    final_structure = data.get("final_structure", {})

    segment_order = final_structure.get("segment_order", [])
    if not segment_order:
        if hook_enabled:
            segment_order = [{"type": "hook"}] + [{"type": "keep", "id": s["id"]} for s in segments]
        else:
            segment_order = [{"type": "keep", "id": s["id"]} for s in segments]

    segments_by_id = {s["id"]: s for s in segments}
    cut_files = []
    total_dur = 0.0

    for idx, entry in enumerate(segment_order):
        seg_type = entry.get("type")
        suffix = f"_{version_suffix}" if version_suffix else ""

        if seg_type == "hook" and hook_enabled:
            src = resolve_source_path(hook["source_file"], video_dir)
            seg_path = os.path.join(temp_dir, f"seg{suffix}_hook.mp4")
            ok = cut_segment_precise(src, hook["source_start"], hook["source_end"], seg_path, reencode)
            if ok:
                cut_files.append(seg_path)
                total_dur += time_to_seconds(hook["source_end"]) - time_to_seconds(hook["source_start"])

        elif seg_type == "keep":
            sid = entry.get("id")
            seg = segments_by_id.get(sid)
            if seg is None:
                print(f"  WARNING: Segment ID {sid} not found, skipping")
                continue
            src = resolve_source_path(seg["source_file"], video_dir)
            seg_path = os.path.join(temp_dir, f"seg{suffix}_{sid:03d}.mp4")
            ok = cut_segment_precise(src, seg["start_time"], seg["end_time"], seg_path, reencode)
            if ok:
                cut_files.append(seg_path)
                total_dur += time_to_seconds(seg["end_time"]) - time_to_seconds(seg["start_time"])
            else:
                print(f"  WARNING: Failed to cut segment {sid}")

    return cut_files, total_dur


def process_combined(
    analysis_json: str,
    video_dir: str,
    output_dir: str | None = None,
    output_name: str | None = None,
    reencode: bool = True,
    crossfade: float = 0.0,
    normalize_audio: bool = True,
    process_versions: bool = False,
) -> str | None:
    """
    Process a cross-episode analysis JSON with S-level quality.
    Supports frame-level cutting, transitions, audio normalization, and multi-version.
    """
    project_root = get_project_root()
    if output_dir is None:
        output_dir = str(project_root / "video" / "output")
    os.makedirs(output_dir, exist_ok=True)

    with open(analysis_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments_to_keep", [])
    if not segments:
        print("ERROR: No segments_to_keep found", file=sys.stderr)
        return None

    drama_name = data.get("drama_name", "combined")
    hook_enabled = data.get("hook", {}).get("enabled", False)

    print(f"\n{'='*60}")
    print(f"Cross-episode cut (S-Level): {drama_name}")
    print(f"  Segments: {len(segments)}, Hook: {hook_enabled}")
    print(f"  Re-encode: {reencode}, Crossfade: {crossfade}s, Normalize: {normalize_audio}")
    print(f"{'='*60}")

    temp_dir = os.path.join(output_dir, "_temp_segments")
    os.makedirs(temp_dir, exist_ok=True)

    safe_name = output_name or drama_name.replace(" ", "_").replace("/", "_")

    output_files = []

    cut_files, total_dur = _process_segment_order(data, video_dir, temp_dir, reencode)

    if not cut_files:
        print("ERROR: All cuts failed", file=sys.stderr)
        _cleanup_temp(temp_dir)
        return None

    print(f"\n  Total: {len(cut_files)} segments, {total_dur:.0f}s ({total_dur/60:.1f}min)")

    output_path = os.path.join(output_dir, f"promo_{safe_name}.mp4")
    ok = concat_with_crossfade(cut_files, output_path, crossfade, normalize_audio)

    _cleanup_files(cut_files)

    if ok:
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n  Output: {output_path} ({size_mb:.1f} MB)")
        output_files.append(output_path)
    else:
        print("ERROR: Concat failed", file=sys.stderr)

    if process_versions and "versions" in data:
        for ver in data["versions"]:
            ver_name = ver.get("name", ver.get("type", "version"))
            print(f"\n  --- Processing version: {ver_name} ---")
            ver_data = {
                "segments_to_keep": ver.get("segments_to_keep", []),
                "hook": ver.get("hook", data.get("hook", {})),
                "final_structure": ver.get("final_structure", {}),
            }
            if not ver_data["segments_to_keep"]:
                print(f"  Skipping {ver_name}: no segments")
                continue

            ver_suffix = ver_name.replace(" ", "_")
            vf, vd = _process_segment_order(ver_data, video_dir, temp_dir, reencode, ver_suffix)
            if vf:
                ver_output = os.path.join(output_dir, f"promo_{safe_name}_{ver_suffix}.mp4")
                ok = concat_with_crossfade(vf, ver_output, crossfade, normalize_audio)
                _cleanup_files(vf)
                if ok:
                    vsz = os.path.getsize(ver_output) / (1024 * 1024)
                    print(f"  Version output: {ver_output} ({vsz:.1f} MB)")
                    output_files.append(ver_output)

    _cleanup_temp(temp_dir)

    if output_files:
        return output_files[0]
    return None


def _cleanup_files(files: list[str]):
    for f in files:
        try:
            os.unlink(f)
        except OSError:
            pass


def _cleanup_temp(temp_dir: str):
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="S-Level video cut & merge with transitions and audio normalization"
    )
    parser.add_argument(
        "analysis_json",
        help="Path to the analysis JSON file",
    )
    parser.add_argument(
        "video_dir",
        help="Directory containing the source video files",
    )
    parser.add_argument(
        "-o", "--output-dir",
        help="Output directory (default: video/output/)",
    )
    parser.add_argument(
        "-n", "--name",
        help="Output file name (without extension)",
    )
    parser.add_argument(
        "--no-reencode",
        action="store_true",
        help="Use stream copy instead of re-encoding (faster but less precise)",
    )
    parser.add_argument(
        "--crossfade",
        type=float, default=0.0,
        help="Crossfade duration between segments in seconds (0 = no crossfade, recommended: 0.3-0.5)",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Skip audio loudness normalization",
    )
    parser.add_argument(
        "--versions",
        action="store_true",
        help="Process all versions from the analysis JSON",
    )
    args = parser.parse_args()

    process_combined(
        args.analysis_json,
        args.video_dir,
        args.output_dir,
        args.name,
        reencode=not args.no_reencode,
        crossfade=args.crossfade,
        normalize_audio=not args.no_normalize,
        process_versions=args.versions,
    )


if __name__ == "__main__":
    main()

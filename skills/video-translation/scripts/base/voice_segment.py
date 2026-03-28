#!/usr/bin/env python3
"""
按 ASR 切分结果（asr_split.json）将人声音频切分为片段，写入 segments/ 并生成角色/片段映射。

- 输入：人声音频（如 voice.mp3）、ASR 切分结果（如 asr_split.json）
- 输出目录：<output_dir>/segments/
  - segment_001.mp3, segment_002.mp3, ...
  - mapping.json：片段 id、起止时间、文本、文件名、角色（若 ASR 有 speaker 则填入）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ffmpeg

SEGMENTS_DIRNAME = "segments"


def run(
    voice_audio: Path,
    asr_split_path: Path,
    output_dir: Path,
    *,
    segments_dirname: str = SEGMENTS_DIRNAME,
    format: str = "wav",
    pad_start: float = 0.0,
    pad_end: float = 0.0,
    min_duration: float = 0.0,
) -> list[dict]:
    """
    根据 asr_split.json 的 segments 对人声做切片，写入 output_dir/segments/。
    返回 mapping 列表（与写入的 mapping.json 一致）。
    """
    output_dir = Path(output_dir).resolve()
    with open(asr_split_path, "r", encoding="utf-8") as f:
        asr_data = json.load(f)

    segments = asr_data.get("segments") or []
    if not segments:
        return []

    segments_dir = output_dir / segments_dirname
    segments_dir.mkdir(parents=True, exist_ok=True)
    mapping: list[dict] = []

    for idx, seg in enumerate(segments, start=1):
        source_id = seg.get("id", idx)
        if "start" not in seg or "end" not in seg:
            print(f"警告: 跳过片段 {source_id}，缺少 start/end", file=sys.stderr)
            continue
        start = float(seg["start"])
        end = float(seg["end"])
        start = max(0.0, start - max(0.0, pad_start))
        end = max(start, end + max(0.0, pad_end))
        duration = end - start
        if duration <= 0:
            print(f"警告: 跳过片段 {source_id}，时长<=0 (start={start}, end={end})", file=sys.stderr)
            continue
        if duration < max(0.0, min_duration):
            print(f"警告: 跳过片段 {source_id}，时长<{min_duration}s", file=sys.stderr)
            continue
        text = seg.get("text", "").strip()
        speaker = seg.get("speaker")  # 若 ASR 后续支持角色/说话人则使用

        filename = f"segment_{len(mapping) + 1:04d}.{format}"
        out_path = segments_dir / filename

        try:
            kwargs = {}
            if format == "wav":
                kwargs["acodec"] = "pcm_s16le"
            else:
                kwargs["acodec"] = "libmp3lame"
                kwargs["audio_bitrate"] = "192k"
            (
                ffmpeg.input(str(voice_audio), ss=start, t=end - start)
                .output(str(out_path), **kwargs)
                .run(quiet=True, overwrite_output=True)
            )
        except ffmpeg.Error as e:
            err = e.stderr.decode("utf-8") if e.stderr else str(e)
            print(f"警告: 切片 segment {source_id} 失败: {err}", file=sys.stderr)
            continue

        entry = {
            "id": len(mapping) + 1,
            "source_id": source_id,
            "start": start,
            "end": end,
            "duration": duration,
            "text": text,
            "file": filename,
        }
        if speaker is not None:
            entry["speaker"] = speaker
        mapping.append(entry)

    mapping_path = segments_dir / "mapping.json"
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(
        description="按 ASR 切分结果（asr_split.json）切分人声到 segments/ 并生成 mapping.json"
    )
    parser.add_argument("voice_audio", help="人声音频路径（如 voice.mp3）")
    parser.add_argument("asr_split_json", help="ASR 切分结果 JSON 路径（如 asr_split.json）")
    parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="输出目录（例如 output/<剧名>/<视频名>/）",
    )
    parser.add_argument(
        "--format",
        choices=["wav", "mp3"],
        default="wav",
        help="片段音频格式（默认 wav）",
    )
    parser.add_argument("--segments-dirname", default=SEGMENTS_DIRNAME, help="片段目录名（默认 segments）")
    parser.add_argument("--pad-start", type=float, default=0.0, help="片段开始前置补偿秒数（默认 0）")
    parser.add_argument("--pad-end", type=float, default=0.0, help="片段结束后置补偿秒数（默认 0）")
    parser.add_argument("--min-duration", type=float, default=0.0, help="最小时长阈值，低于阈值的片段将跳过（默认 0）")
    args = parser.parse_args()

    voice_path = Path(args.voice_audio).resolve()
    asr_path = Path(args.asr_split_json).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not voice_path.exists():
        print(f"错误: 人声音频未找到: {voice_path}")
        return 1
    if not asr_path.exists():
        print(f"错误: ASR 切分文件未找到: {asr_path}")
        return 1

    try:
        mapping = run(
            voice_path,
            asr_path,
            output_dir,
            segments_dirname=args.segments_dirname,
            format=args.format,
            pad_start=args.pad_start,
            pad_end=args.pad_end,
            min_duration=args.min_duration,
        )
        target_dir = output_dir / args.segments_dirname
        print(f"已切分 {len(mapping)} 个片段到 {target_dir}/")
        print(f"映射已写入 {target_dir / 'mapping.json'}")
        return 0
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

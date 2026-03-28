#!/usr/bin/env python3
"""
敏感词音频处理：按 sensitivity.json 中的时间区间，将人声音频中的敏感片段替换为等长屏蔽音效。

流程（对应 reference/敏感词音频处理.md 第 1–4 步）：
1. 读取敏感词列表中的时间间隔 sensitivity.json
2. 使用 ffmpeg-python，将指定区间替换为 asserts/dd6a0e.mp3 屏蔽音
3. 屏蔽音时长为 1017ms：区间超过 1017ms 则循环后截断，少于则截取对应长度后替换
4. 核心逻辑：将敏感词对应时间区间（startTime 至 endTime）的原始音频，替换为等时长的屏蔽音效

用法:
  python sensitive_audio_replace.py --sensitivity sensitivity.json --vocals xxx_vocals.mp3 -o vocals_censored.mp3
  python sensitive_audio_replace.py --sensitivity ./audit_output/sensitivity.json --vocals ./audit_output/xxx_vocals.mp3 -o ./audit_output/xxx_vocals_censored.mp3 --beep ../asserts/dd6a0e.mp3
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import subprocess
from pathlib import Path

import ffmpeg

# 屏蔽音效标准时长（毫秒），与 asserts/dd6a0e.mp3 一致
BEEP_DURATION_MS = 1017


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def load_intervals(sensitivity_path: Path) -> list[tuple[int, int]]:
    """从 sensitivity.json 读取 (start_time_ms, end_time_ms) 列表，并按 start 排序、合并重叠。"""
    raw = json.loads(sensitivity_path.read_text(encoding="utf-8"))
    intervals: list[tuple[int, int]] = []
    for item in raw:
        s = int(item["start_time"])
        e = int(item["end_time"])
        if e > s:
            intervals.append((s, e))
    intervals.sort(key=lambda x: x[0])
    # 合并重叠区间
    merged: list[tuple[int, int]] = []
    for s, e in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def build_ffmpeg_args(
    vocals_path: Path,
    beep_path: Path,
    intervals: list[tuple[int, int]],
    output_path: Path,
    beep_offset_sec: float = 0.0,
):
    """
    构建 ffmpeg 命令：按时间轴切段后拼接（不再混音）。
    输出效果示意：
      原声 [0, s1) | 哔声 [s1, e1) | 原声 [e1, s2) | 哔声 [s2, e2) | ... | 原声 [e_last, end]

    敏感区间内完全清除原声，仅保留等长屏蔽音效。
    """
    if not intervals:
        (
            ffmpeg
            .input(str(vocals_path))
            .output(str(output_path), acodec="copy")
            .run(quiet=True, overwrite_output=True)
        )
        return

    # 构建交替片段：
    #  - 原声段：从原始人声截取 [start, end)
    #  - 哔声段：生成等长哔声 [0, duration)
    segments: list[tuple[float, float | None, str]] = []
    t_s = 0.0
    for s_ms, e_ms in intervals:
        s_s = s_ms / 1000.0
        e_s = e_ms / 1000.0
        if t_s < s_s - 1e-6:
            # 前一段原声
            segments.append((t_s, s_s, "orig"))
        # 敏感区间对应的哔声段（从 0 开始、长度 = e_s - s_s）
        segments.append((0.0, e_s - s_s, "beep"))
        t_s = e_s

    # 末尾剩余原声（直到文件结尾），end=None 表示一直到结尾
    segments.append((t_s, None, "orig_tail"))

    # 使用 subprocess 直接调用 ffmpeg，避免 ffmpeg-python 对 complex_filter 的封装问题
    cmd = ["ffmpeg", "-y"]
    
    # Input 0: vocals
    cmd.extend(["-i", str(vocals_path)])
    
    filter_parts: list[str] = []
    next_input_idx = 1
    concat_inputs: list[str] = []

    for i, (start_s, end_or_none, seg_type) in enumerate(segments):
        label = f"s{i}"
        if seg_type in ("orig", "orig_tail"):
            # 从原始人声截取原声片段
            if end_or_none is None:
                # 到文件结尾
                filter_parts.append(
                    f"[0:a]atrim=start={start_s:.3f},asetpts=PTS-STARTPTS[{label}]"
                )
            else:
                end_s = float(end_or_none)
                filter_parts.append(
                    f"[0:a]atrim=start={start_s:.3f}:end={end_s:.3f},asetpts=PTS-STARTPTS[{label}]"
                )
            concat_inputs.append(f"[{label}]")
        else:  # beep 段
            seg_duration = float(end_or_none)
            # 哔声段：从 beep 文件的 beep_offset_sec 处开始截取 seg_duration，避免文件头静音造成听感滞后
            duration_ms = int(round(seg_duration * 1000))
            n_loop = max(0, math.ceil(duration_ms / BEEP_DURATION_MS) - 1)
            
            # Add input for this beep
            # 注意：-stream_loop 必须在 -i 之前
            cmd.extend(["-stream_loop", str(n_loop), "-i", str(beep_path)])
            
            start_s_beep = beep_offset_sec
            end_s_beep = beep_offset_sec + seg_duration
            filter_parts.append(
                f"[{next_input_idx}:a]atrim=start={start_s_beep:.3f}:end={end_s_beep:.3f},asetpts=PTS-STARTPTS[{label}]"
            )
            concat_inputs.append(f"[{label}]")
            next_input_idx += 1

    # 按顺序 concat 所有片段
    n_seg = len(segments)
    filter_parts.append("".join(concat_inputs) + f"concat=n={n_seg}:v=0:a=1[aout]")
    complex_filter = ";".join(filter_parts)
    
    cmd.extend(["-filter_complex", complex_filter])
    cmd.extend(["-map", "[aout]"])
    cmd.extend(["-acodec", "libmp3lame"])
    cmd.append(str(output_path))
    
    # 打印命令以便调试
    # print(f"Running ffmpeg: {' '.join(cmd)}", file=sys.stderr)
    
    subprocess.run(cmd, check=True, stderr=subprocess.PIPE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="按 sensitivity.json 将人声中的敏感词区间替换为等长屏蔽音效",
    )
    parser.add_argument(
        "--sensitivity", "-s",
        required=True,
        type=Path,
        help="sensitivity.json 路径（含 start_time/end_time 毫秒）",
    )
    parser.add_argument(
        "--vocals", "-v",
        required=True,
        type=Path,
        help="人声音频路径（如 xxx_vocals.mp3）",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="输出音频路径（替换后的新音频）",
    )
    parser.add_argument(
        "--beep", "-b",
        default=None,
        type=Path,
        help="屏蔽音效文件路径，默认使用 审核/asserts/dd6a0e.mp3",
    )
    parser.add_argument(
        "--beep-offset-ms",
        default=0,
        type=int,
        metavar="MS",
        help="哔声文件开头跳过的毫秒数（若听感滞后可设 50–150，跳过文件头静音/淡入）",
    )
    args = parser.parse_args()

    sensitivity_path = args.sensitivity.resolve()
    vocals_path = args.vocals.resolve()
    output_path = args.output.resolve()
    beep_path = args.beep.resolve() if args.beep else (get_script_dir().parent / "asserts" / "dd6a0e.mp3").resolve()

    if not sensitivity_path.is_file():
        print(f"❌ 找不到 sensitivity 文件: {sensitivity_path}", file=sys.stderr)
        return 1
    if not vocals_path.is_file():
        print(f"❌ 找不到人声音频: {vocals_path}", file=sys.stderr)
        return 1
    if not beep_path.is_file():
        print(f"❌ 找不到屏蔽音效: {beep_path}", file=sys.stderr)
        return 1

    intervals = load_intervals(sensitivity_path)
    print(f"📋 已读取 {len(intervals)} 个敏感词时间区间", file=sys.stderr)
    if intervals:
        for i, (s, e) in enumerate(intervals):
            print(f"   区间 {i + 1}: {s}–{e} ms ({e - s} ms)", file=sys.stderr)

    beep_offset_sec = args.beep_offset_ms / 1000.0
    try:
        build_ffmpeg_args(vocals_path, beep_path, intervals, output_path, beep_offset_sec)
        print(f"✅ 已输出: {output_path}", file=sys.stderr)
        return 0
    except ffmpeg.Error as e:
        err = e.stderr.decode("utf-8") if e.stderr else str(e)
        print(f"❌ ffmpeg 执行失败: {err}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ 执行失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
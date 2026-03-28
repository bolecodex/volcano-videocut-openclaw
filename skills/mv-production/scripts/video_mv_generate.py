#!/usr/bin/env python3
"""
基于分镜 JSON 与歌曲音频合成 MV：
- 先静音拼接所有镜头；
- 再合并歌曲音轨；
- 可选：在本地直接基于 SRT 硬编码字幕（简单场景下可替代 VOD 字幕烧录）。

ffmpeg 通过 Python 包 imageio-ffmpeg 提供，不依赖用户本机安装。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from dotenv import load_dotenv

from ffmpeg_exe import get_ffmpeg_exe
from output_dir_utils import resolve_output_dir

load_dotenv(_SCRIPT_DIR / ".env")


def build_shots_file(storyboard_path: Path, work_dir: Path) -> Path:
    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("storyboard JSON 必须是数组，每个元素至少包含 video_path。")

    lines = []
    for shot in data:
        video_path = shot.get("video_path")
        if not video_path:
            raise ValueError("每个分镜对象必须包含 video_path 字段。")
        vp = Path(video_path)
        if not vp.is_absolute():
            vp = storyboard_path.parent / vp
        if not vp.exists():
            raise FileNotFoundError(f"分镜视频不存在: {vp}")
        lines.append(f"file '{vp.as_posix()}'")

    shots_file = work_dir / "shots.txt"
    shots_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return shots_file


def run_ffmpeg_concat(shots_file: Path, temp_video: Path) -> None:
    exe = get_ffmpeg_exe()
    subprocess.run(
        [exe, "-y", "-f", "concat", "-safe", "0", "-i", str(shots_file), "-an", "-c:v", "libx264", str(temp_video)],
        check=True,
    )


def get_audio_duration_seconds(audio_path: Path, ffmpeg_exe: str) -> float:
    """用 ffmpeg 探测音频时长（秒），用于合成时以音频时长为准。"""
    result = subprocess.run(
        [ffmpeg_exe, "-i", str(audio_path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # 从 stderr 解析 "Duration: 00:01:30.50, ..."
    import re  # 延迟导入以避免顶层不必要依赖

    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)[.,](\d*)", result.stderr or "")
    if not match:
        return 0.0
    h, m, s, frac = match.groups()
    frac = (frac + "000000")[:6].ljust(6, "0")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(frac) / 1_000_000.0


def run_ffmpeg_merge_audio(
    temp_video: Path,
    song_audio: Path,
    output: Path,
    duration_seconds: Optional[float] = None,
    subtitle: Optional[Path] = None,
) -> None:
    """
    合并静音视频与歌曲音频；若提供 duration_seconds（通常为音频时长），则输出时长以该值为准。
    若提供 subtitle（SRT 路径），则在本地通过 ffmpeg 的 subtitles 滤镜进行**硬编码字幕**。
    """
    exe = get_ffmpeg_exe()
    if duration_seconds is None or duration_seconds <= 0:
        duration_seconds = get_audio_duration_seconds(song_audio, exe)
    args = [
        exe,
        "-y",
        "-i",
        str(temp_video),
        "-i",
        str(song_audio),
    ]

    if subtitle is not None:
        # 使用 subtitles 滤镜进行硬编码字幕，需保证 SRT 为 UTF-8 编码
        args += [
            "-vf",
            f"subtitles={subtitle.as_posix()}",
            "-c:v",
            "libx264",
        ]
    else:
        # 不处理字幕时，直接 copy 视频编码
        args += [
            "-c:v",
            "copy",
        ]

    args += [
        "-c:a",
        "aac",
        "-t",
        str(duration_seconds),
        str(output),
    ]
    subprocess.run(args, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="基于分镜 JSON 与歌曲音频合成 MV，可选本地硬编码 SRT 字幕。"
    )
    parser.add_argument("--storyboard", required=True, help="分镜 JSON，每项含 video_path。")
    parser.add_argument("--song-audio", required=True, help="歌曲音频路径。")
    parser.add_argument("--output", required=True, help="最终 MV 输出路径。")
    parser.add_argument(
        "--subtitle",
        default=None,
        help="可选：SRT 字幕文件路径，若提供则在本地通过 ffmpeg 进行硬编码字幕。",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="中间文件与工作目录；未指定时由 --song-name 或随机 6 位数决定，见 music_output/<歌曲名|随机数>。",
    )
    parser.add_argument(
        "--song-name",
        default=None,
        help="歌曲名称，用于生成任务子目录 music_output/<歌曲名>；未提供则使用 6 位随机数。",
    )
    args = parser.parse_args()

    storyboard_path = Path(args.storyboard)
    song_audio = Path(args.song_audio)
    output = Path(args.output)
    work_dir = resolve_output_dir(output_dir=args.work_dir, song_name=args.song_name)

    if not storyboard_path.exists():
        raise FileNotFoundError(f"找不到分镜文件: {storyboard_path}")
    if not song_audio.exists():
        raise FileNotFoundError(f"找不到歌曲音频: {song_audio}")
    work_dir.mkdir(parents=True, exist_ok=True)

    subtitle_path: Optional[Path] = None
    if args.subtitle:
        subtitle_path = Path(args.subtitle)
        if not subtitle_path.exists():
            raise FileNotFoundError(f"找不到字幕文件: {subtitle_path}")

    shots_file = build_shots_file(storyboard_path, work_dir)
    temp_video = work_dir / "temp_video_silent.mp4"

    print("静音拼接分镜...")
    run_ffmpeg_concat(shots_file, temp_video)
    exe = get_ffmpeg_exe()
    audio_duration = get_audio_duration_seconds(song_audio, exe)
    if audio_duration <= 0:
        raise ValueError(f"无法获取音频时长: {song_audio}")
    print(f"音频时长: {audio_duration:.1f}s（后续以此为准）")

    # 直接将静音视频与歌曲音频合成，生成不含任何字幕的 MV
    print("合并歌曲音频（最后一步）...")
    run_ffmpeg_merge_audio(
        temp_video,
        song_audio,
        output,
        duration_seconds=audio_duration,
        subtitle=subtitle_path,
    )
    print(f"完成: {output}")


if __name__ == "__main__":
    main()

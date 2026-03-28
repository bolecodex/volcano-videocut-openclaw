#!/usr/bin/env python3
"""
合并音频和视频，使用 imageio-ffmpeg 提供的 ffmpeg。
"""
import argparse
import subprocess
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
import sys
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ffmpeg_exe import get_ffmpeg_exe


def merge_audio_video(video_path: Path, audio_path: Path, output_path: Path):
    exe = get_ffmpeg_exe()
    cmd = [
        exe, "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output_path)
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="合并视频和音频")
    parser.add_argument("--video", required=True, help="视频路径")
    parser.add_argument("--audio", required=True, help="音频路径")
    parser.add_argument("--output", required=True, help="输出路径")
    args = parser.parse_args()
    
    print(f"合并视频和音频: {args.video} + {args.audio} -> {args.output}")
    merge_audio_video(Path(args.video), Path(args.audio), Path(args.output))
    print(f"完成: {args.output}")

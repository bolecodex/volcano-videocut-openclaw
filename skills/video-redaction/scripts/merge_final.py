#!/usr/bin/env python3
"""
Final Merge Script using ffmpeg-python
Merges muted video, censored vocals, background music, and subtitles.
"""

import argparse
import sys
from pathlib import Path
import ffmpeg

def merge(muted_video, vocals, bgm, subtitles, output_path):
    muted_video = Path(muted_video).resolve()
    vocals = Path(vocals).resolve()
    bgm = Path(bgm).resolve()
    subtitles = Path(subtitles).resolve()
    output_path = Path(output_path).resolve()

    if not all(p.exists() for p in [muted_video, vocals, bgm, subtitles]):
        print("Error: One or more input files not found.")
        return

    # 1. Mix Audio
    # amix: inputs=2, duration=first
    print("Mixing audio...")
    input_vocals = ffmpeg.input(str(vocals))
    input_bgm = ffmpeg.input(str(bgm))
    
    mixed_audio = ffmpeg.filter([input_vocals, input_bgm], 'amix', inputs=2, duration='first', dropout_transition=2)
    
    # 2. Burn Subtitles and Merge with Audio
    # We apply the ASS filter to the video stream
    # And we take the mixed audio stream
    
    print("Burning subtitles and merging...")
    
    input_video = ffmpeg.input(str(muted_video))
    
    # Apply subtitles filter. Note: filename must be properly escaped if needed, 
    # but ffmpeg-python handles basic string paths.
    video_with_subs = input_video.filter('ass', str(subtitles))
    
    # Combine processed video and mixed audio
    output = ffmpeg.output(
        video_with_subs,
        mixed_audio,
        str(output_path),
        vcodec='libx264',
        acodec='aac',
        **{'c:a': 'aac'} # Explicitly set audio codec
    )
    
    # Run
    try:
        output.run(overwrite_output=True)
        print(f"Successfully created: {output_path}")
    except ffmpeg.Error as e:
        print(f"FFmpeg Error: {e.stderr.decode() if e.stderr else str(e)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Merge video, audio and subtitles")
    parser.add_argument("--video", required=True, help="Muted video path")
    parser.add_argument("--vocals", required=True, help="Censored vocals path")
    parser.add_argument("--bgm", required=True, help="Background music path")
    parser.add_argument("--subtitles", required=True, help="Subtitles (.ass) path")
    parser.add_argument("-o", "--output", required=True, help="Final output video path")
    
    args = parser.parse_args()
    
    merge(args.video, args.vocals, args.bgm, args.subtitles, args.output)

if __name__ == "__main__":
    main()

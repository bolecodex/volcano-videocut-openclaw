#!/usr/bin/env python3
import json
import argparse


def ms_to_timecode(ms):
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def generate_srt(asr_corrected_path, output_path):
    with open(asr_corrected_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    lines = []
    for idx, line in enumerate(data['lines']):
        start_time = ms_to_timecode(line['start_time_ms'])
        end_time = ms_to_timecode(line['end_time_ms'])
        lines.append(f"{idx + 1}")
        lines.append(f"{start_time} --> {end_time}")
        lines.append(line['lyric'])
        lines.append("")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"已生成 SRT 字幕文件: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 asr_corrected.json 生成 SRT 字幕")
    parser.add_argument("--asr", required=True, help="asr_corrected.json 路径")
    parser.add_argument("--output", required=True, help="输出 SRT 文件路径")
    
    args = parser.parse_args()
    generate_srt(args.asr, args.output)

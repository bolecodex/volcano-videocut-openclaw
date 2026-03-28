#!/usr/bin/env python3
"""
Interview video processor - Main script
Adds fancy text and term definition cards to interview videos
"""
import json
import sys
import os
import argparse
import subprocess
from pathlib import Path
from shutil import which


def process_video(video_path, config_path, effects_dir, output_path):
    print(f"🎬 正在处理视频: {video_path}")

    if not os.path.exists(video_path):
        print(f"❌ 错误: 视频文件不存在: {video_path}")
        sys.exit(1)

    if not os.path.exists(config_path):
        print(f"❌ 错误: 配置文件不存在: {config_path}")
        sys.exit(1)

    if not os.path.exists(effects_dir):
        print(f"❌ 错误: 动效视频目录不存在: {effects_dir}")
        sys.exit(1)

    if which('ffmpeg') is None:
        print("❌ 错误: ffmpeg 不可用")
        sys.exit(1)

    print("📋 加载配置文件...")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    effects = _collect_effects(config, effects_dir)
    if not effects:
        print("⚠️ 未发现可叠加的动效视频，直接复制原视频")
        _copy_video(video_path, output_path)
        return

    print(f"🎞️ 合成动效视频 ({len(effects)} 个)...")
    _render_overlay(video_path, effects, output_path)
    print("✅ 处理完成！")
    print(f"📁 输出文件: {output_path}")


def _copy_video(video_path, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(video_path, 'rb') as src, open(output_path, 'wb') as dst:
        dst.write(src.read())


def _collect_effects(config, effects_dir):
    effects = []

    def add_effect(path, start_ms, duration_ms):
        if path and os.path.exists(path) and duration_ms and duration_ms > 0:
            effects.append({
                'path': path,
                'start': start_ms / 1000.0,
                'end': (start_ms + duration_ms) / 1000.0
            })

    chapter_titles = config.get('chapterTitles', [])
    for i, ch in enumerate(chapter_titles):
        add_effect(
            os.path.join(effects_dir, f'chapterTitles-{i}.mov'),
            ch.get('startMs', 0),
            ch.get('durationMs', 4000)
        )

    key_phrases = config.get('keyPhrases', [])
    for i, phrase in enumerate(key_phrases):
        duration_ms = phrase.get('durationMs')
        if duration_ms is None:
            start_ms = phrase.get('startMs', 0)
            end_ms = phrase.get('endMs')
            duration_ms = max((end_ms or start_ms) - start_ms, 0)
        add_effect(
            os.path.join(effects_dir, f'keyPhrases-{i}.mov'),
            phrase.get('startMs', 0),
            duration_ms
        )

    term_defs = config.get('termDefinitions', [])
    for i, term in enumerate(term_defs):
        duration_ms = term.get('durationMs')
        if duration_ms is None:
            duration_ms = int(term.get('displayDurationSeconds', 6) * 1000)
        add_effect(
            os.path.join(effects_dir, f'termDefinitions-{i}.mov'),
            term.get('firstAppearanceMs', 0),
            duration_ms
        )

    quotes = config.get('quotes', [])
    for i, quote in enumerate(quotes):
        add_effect(
            os.path.join(effects_dir, f'quotes-{i}.mov'),
            quote.get('startMs', 0),
            quote.get('durationMs', 5000)
        )

    stats = config.get('stats', [])
    for i, stat in enumerate(stats):
        add_effect(
            os.path.join(effects_dir, f'stats-{i}.mov'),
            stat.get('startMs', 0),
            stat.get('durationMs', 4000)
        )

    bullet_points = config.get('bulletPoints', [])
    for i, bp in enumerate(bullet_points):
        add_effect(
            os.path.join(effects_dir, f'bulletPoints-{i}.mov'),
            bp.get('startMs', 0),
            bp.get('durationMs', 6000)
        )

    social_bars = config.get('socialBars', [])
    for i, sb in enumerate(social_bars):
        add_effect(
            os.path.join(effects_dir, f'socialBars-{i}.mov'),
            sb.get('startMs', 0),
            sb.get('durationMs', 8000)
        )

    lower_thirds = config.get('lowerThirds', [])
    for i, lt in enumerate(lower_thirds):
        add_effect(
            os.path.join(effects_dir, f'lowerThirds-{i}.mov'),
            lt.get('startMs', 0),
            lt.get('durationMs', 5000)
        )

    return effects


def _build_filter_complex(effect_count, effects):
    filters = ['[0:v]format=rgba[base]']
    last_label = 'base'
    for idx in range(effect_count):
        effect = effects[idx]
        start = effect['start']
        end = effect['end']
        ov_label = f'ov{idx}'
        out_label = f'v{idx + 1}'
        filters.append(
            f'[{idx + 1}:v]setpts=PTS-STARTPTS+{start}/TB,format=rgba[{ov_label}]'
        )
        filters.append(
            f'[{last_label}][{ov_label}]overlay=enable=\'between(t,{start},{end})\':format=auto[{out_label}]'
        )
        last_label = out_label
    return ';'.join(filters), last_label


def _render_overlay(video_path, effects, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    inputs = [video_path] + [e['path'] for e in effects]
    filter_complex, last_label = _build_filter_complex(len(effects), effects)
    filter_complex = f'{filter_complex};[{last_label}]format=yuv420p[outv]'

    cmd = [
        'ffmpeg', '-y',
        '-i', inputs[0]
    ]
    for path in inputs[1:]:
        cmd.extend(['-i', path])
    cmd.extend([
        '-filter_complex', filter_complex,
        '-map', '[outv]',
        '-map', '0:a?',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-crf', '18',
        '-c:a', 'aac',
        '-movflags', 'faststart',
        output_path
    ])

    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(
        description='为访谈视频添加花字和名词解释卡片',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python video_processor.py video.mp4 config.json temp output.mp4
        """
    )

    parser.add_argument('video', help='输入视频文件路径')
    parser.add_argument('config', help='配置文件路径 (.json)')
    parser.add_argument('effects_dir', help='动效视频目录路径')
    parser.add_argument('output', nargs='?', default=None, help='输出视频路径 (默认: output.mp4)')
    args = parser.parse_args()

    original_cwd = os.environ.get('ORIGINAL_CWD', os.getcwd())

    if args.output:
        output_path = args.output
        if not os.path.isabs(output_path):
            output_path = os.path.join(original_cwd, output_path)
    else:
        output_path = os.path.join(original_cwd, 'output.mp4')
    if output_path.endswith('~'):
        output_path = output_path[:-1]

    try:
        process_video(
            args.video,
            args.config,
            args.effects_dir,
            output_path
        )
    except Exception as e:
        print(f"❌ 处理失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

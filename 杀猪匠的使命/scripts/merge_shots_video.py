#!/usr/bin/env python3
"""
分镜头视频合成工具（AI视频版）
将 shots/*.yaml 中的 AI 视频片段和 TTS 配音合并成完整视频。

核心逻辑：
1. 下载每个镜头的 AI 视频片段 (video_url)
2. 下载并合并该镜头所有台词音频 (lines[].audio_url)
3. 处理视频时长与音频时长不匹配：
   - 音频更长 → 提取视频末帧，冻结延展至音频结束
   - 视频更长 → 以音频时长为准裁剪
4. 替换音轨，输出最终镜头视频
5. 按场景拼接所有镜头，再合并为完整视频
"""

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml


# ─────────────────────────── 工具函数 ───────────────────────────

def log(msg: str, level: str = "INFO"):
    """打印日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def check_ffmpeg():
    """检查 FFmpeg 是否安装"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def download_file(url: str, output_path: Path, retries: int = 3) -> bool:
    """下载文件，支持重试"""
    if output_path.exists() and output_path.stat().st_size > 0:
        log(f"  已存在，跳过下载: {output_path.name}")
        return True
    for attempt in range(retries):
        try:
            log(f"  下载: {url[:100]}...")
            urllib.request.urlretrieve(url, output_path)
            if output_path.exists() and output_path.stat().st_size > 0:
                return True
        except Exception as e:
            log(f"  下载失败 (尝试 {attempt + 1}/{retries}): {e}", "WARN")
    return False


def get_media_duration(media_path: Path) -> float:
    """获取音频或视频时长（秒）"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(media_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        log(f"  无法获取时长: {media_path.name}", "ERROR")
        return 0.0


def load_scene_yaml(yaml_path: Path) -> dict:
    """加载场景 YAML 文件"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─────────────────────────── 音频处理 ───────────────────────────

def merge_audio_files(audio_files: list, output_path: Path) -> bool:
    """合并多个音频文件为一个"""
    if len(audio_files) == 0:
        return False

    if len(audio_files) == 1:
        shutil.copy(audio_files[0], output_path)
        return True

    # 构建 FFmpeg concat 命令
    inputs = []
    for f in audio_files:
        inputs.extend(["-i", str(f)])

    n = len(audio_files)
    filter_parts = "".join([f"[{i}:a]" for i in range(n)])
    filter_complex = f"{filter_parts}concat=n={n}:v=0:a=1[out]"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  音频合并失败: {result.stderr[-200:]}", "ERROR")
    return result.returncode == 0


# ─────────────────────── 视频+音频合成 ──────────────────────────

def extract_last_frame(video_path: Path, output_path: Path) -> bool:
    """提取视频最后一帧为图片"""
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.1",
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and output_path.exists()


def get_video_resolution(video_path: Path) -> tuple:
    """获取视频分辨率 (width, height)"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        parts = result.stdout.strip().split("x")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 1280, 720  # 默认值


def create_shot_video_from_clip(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    temp_dir: Path,
    tolerance: float = 0.5
) -> bool:
    """
    从 AI 视频片段 + 配音音频创建最终视频。
    处理视频时长与音频时长不匹配的问题。
    """
    video_dur = get_media_duration(video_path)
    audio_dur = get_media_duration(audio_path)

    if video_dur <= 0 or audio_dur <= 0:
        log(f"  时长异常: video={video_dur:.1f}s, audio={audio_dur:.1f}s", "ERROR")
        return False

    diff = audio_dur - video_dur
    log(f"  时长对比: video={video_dur:.1f}s, audio={audio_dur:.1f}s, diff={diff:+.1f}s")

    w, h = get_video_resolution(video_path)

    if diff > tolerance:
        # ── 音频比视频长：提取末帧冻结延展 ──
        remaining = diff + 0.2  # 多加 0.2s 缓冲
        last_frame = temp_dir / f"{output_path.stem}_lastframe.png"

        if not extract_last_frame(video_path, last_frame):
            log("  提取末帧失败，回退到直接叠加", "WARN")
            return _simple_overlay(video_path, audio_path, output_path)

        # 用 filter_complex 拼接原视频 + 冻结帧，然后叠加音频
        # 统一分辨率和像素格式
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-loop", "1", "-t", f"{remaining:.2f}", "-i", str(last_frame),
            "-i", str(audio_path),
            "-filter_complex",
            (
                f"[0:v]scale={w}:{h},setsar=1,fps=24,format=yuv420p[v0];"
                f"[1:v]scale={w}:{h},setsar=1,fps=24,format=yuv420p[v1];"
                f"[v0][v1]concat=n=2:v=1:a=0[vout]"
            ),
            "-map", "[vout]",
            "-map", "2:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", f"{audio_dur:.2f}",
            "-movflags", "+faststart",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"  冻结延展失败: {result.stderr[-300:]}", "WARN")
            log("  回退到直接叠加模式", "WARN")
            return _simple_overlay(video_path, audio_path, output_path)
        return True

    elif diff < -tolerance:
        # ── 视频比音频长：以音频时长为准裁剪 ──
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"  裁剪叠加失败: {result.stderr[-300:]}", "ERROR")
            return False
        return True

    else:
        # ── 时长相近：直接替换音轨 ──
        return _simple_overlay(video_path, audio_path, output_path)


def _simple_overlay(video_path: Path, audio_path: Path, output_path: Path) -> bool:
    """直接替换视频的音轨"""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  音轨替换失败: {result.stderr[-300:]}", "ERROR")
    return result.returncode == 0


# ─────────────────────────── 拼接视频 ───────────────────────────

def concat_videos(video_files: list, output_path: Path) -> bool:
    """拼接多个视频片段为一个完整视频"""
    if len(video_files) == 0:
        return False

    if len(video_files) == 1:
        shutil.copy(video_files[0], output_path)
        return True

    # 需要统一编码参数后再拼接，使用 filter_complex concat
    # 先获取第一个视频的分辨率作为基准
    w, h = get_video_resolution(video_files[0])

    inputs = []
    filter_parts = []
    for i, vf in enumerate(video_files):
        inputs.extend(["-i", str(vf)])
        filter_parts.append(f"[{i}:v]scale={w}:{h},setsar=1,fps=24,format=yuv420p[v{i}];")
        filter_parts.append(f"[{i}:a]aresample=44100[a{i}];")

    n = len(video_files)
    # concat 滤镜要求输入按 [v0][a0][v1][a1]... 交替排列
    interleaved = "".join([f"[v{i}][a{i}]" for i in range(n)])
    filter_parts.append(f"{interleaved}concat=n={n}:v=1:a=1[vout][aout]")

    filter_str = "".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_str,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  拼接失败: {result.stderr[-300:]}", "ERROR")
        # 回退到简单 concat 模式
        return _simple_concat(video_files, output_path)
    return True


def _simple_concat(video_files: list, output_path: Path) -> bool:
    """使用 concat demuxer 简单拼接（要求编码一致）"""
    list_file = output_path.parent / "concat_list.txt"
    with open(list_file, "w") as f:
        for vf in video_files:
            f.write(f"file '{Path(vf).absolute()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if list_file.exists():
        list_file.unlink()
    if result.returncode != 0:
        log(f"  简单拼接也失败: {result.stderr[-200:]}", "ERROR")
    return result.returncode == 0


# ─────────────────────────── 字幕处理 ───────────────────────────

def format_srt_time(seconds: float) -> str:
    """格式化 SRT 时间码"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_from_audio_durations(
    shots_data: list,
    audio_dir: Path,
    output_path: Path
) -> float:
    """
    根据实际音频时长生成精确的 SRT 字幕。
    返回总时长。
    """
    srt_content = []
    current_time = 0.0
    index = 1

    for shot in shots_data:
        shot_id = shot.get("id", "unknown")
        lines = shot.get("lines", [])

        for i, line in enumerate(lines):
            text = line.get("text", "")
            if not text:
                continue

            # 尝试获取实际音频时长
            audio_file = audio_dir / f"{shot_id}_line_{i:02d}.mp3"
            if audio_file.exists():
                duration = get_media_duration(audio_file)
            else:
                # 回退：估算时长（中文约 4 字/秒）
                duration = max(len(text) / 4, 1.5)

            start = format_srt_time(current_time)
            end = format_srt_time(current_time + duration)

            srt_content.append(f"{index}")
            srt_content.append(f"{start} --> {end}")
            srt_content.append(text)
            srt_content.append("")

            current_time += duration
            index += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_content))

    return current_time


def burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> bool:
    """将字幕烧录到视频"""
    # 使用 FFmpeg subtitles 滤镜
    # 需要转义路径中的特殊字符
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"subtitles='{srt_escaped}':force_style='FontSize=20,FontName=PingFang SC,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2,MarginV=25'",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  字幕烧录失败: {result.stderr[-300:]}", "WARN")
    return result.returncode == 0


# ─────────────────────── 资源检查 ──────────────────────────

def check_scene_resources(scene_data: dict) -> dict:
    """检查场景资源完整性（含 video_url）"""
    shots = scene_data.get("shots", [])

    total_shots = len(shots)
    videos_ready = 0
    images_ready = 0
    audio_ready = 0
    total_audio = 0

    for shot in shots:
        # 检查视频
        if shot.get("video_url") and shot.get("video_status") == "completed":
            videos_ready += 1
        # 检查图片（备用）
        if shot.get("image_url") and shot.get("image_status") == "completed":
            images_ready += 1
        # 检查音频
        lines = shot.get("lines", [])
        for line in lines:
            total_audio += 1
            if line.get("audio_url") and line.get("audio_status") == "completed":
                audio_ready += 1

    return {
        "total_shots": total_shots,
        "videos_ready": videos_ready,
        "videos_complete": videos_ready == total_shots,
        "images_ready": images_ready,
        "images_complete": images_ready == total_shots,
        "audio_ready": audio_ready,
        "total_audio": total_audio,
        "audio_complete": audio_ready == total_audio,
        "ready": videos_ready == total_shots and audio_ready == total_audio,
    }


# ─────────────────────── 场景处理 ──────────────────────────

def process_scene(scene_path: Path, output_dir: Path, subtitle: bool = False) -> dict:
    """处理单个场景：下载视频+音频 → 合成 → 拼接"""
    scene_data = load_scene_yaml(scene_path)
    scene_id = scene_data.get("scene_id", "unknown")
    scene_name = scene_data.get("scene_name", "未命名")

    log(f"========== 处理场景: {scene_id} - {scene_name} ==========")

    # 检查资源
    status = check_scene_resources(scene_data)
    if not status["ready"]:
        log(
            f"场景资源不完整: 视频 {status['videos_ready']}/{status['total_shots']}, "
            f"音频 {status['audio_ready']}/{status['total_audio']}",
            "ERROR"
        )
        # 如果视频不全但图片全，可以回退使用图片模式
        if not status["videos_complete"] and status["images_complete"] and status["audio_complete"]:
            log("视频不全但图片齐全，将对缺少视频的镜头使用静态图片模式", "WARN")
        elif not status["audio_complete"]:
            return {"success": False, "error": "音频资源不完整"}

    # 创建临时目录
    temp_dir = output_dir / "temp" / scene_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "video").mkdir(exist_ok=True)
    (temp_dir / "audio").mkdir(exist_ok=True)
    (temp_dir / "clips").mkdir(exist_ok=True)

    shot_videos = []
    total_duration = 0.0

    for shot in scene_data.get("shots", []):
        shot_id = shot.get("id", "unknown")
        log(f"\n  ── 镜头: {shot_id} ({shot.get('title', '')}) ──")

        # 1. 下载并合并音频
        lines = shot.get("lines", [])
        audio_files = []
        for i, line in enumerate(lines):
            audio_url = line.get("audio_url")
            if audio_url:
                audio_path = temp_dir / "audio" / f"{shot_id}_line_{i:02d}.mp3"
                if download_file(audio_url, audio_path):
                    audio_files.append(audio_path)

        if not audio_files:
            log(f"  无音频文件，跳过镜头 {shot_id}", "ERROR")
            continue

        # 合并音频
        merged_audio = temp_dir / "audio" / f"{shot_id}_merged.mp3"
        if not merged_audio.exists() or merged_audio.stat().st_size == 0:
            if not merge_audio_files(audio_files, merged_audio):
                log(f"  音频合并失败，跳过镜头 {shot_id}", "ERROR")
                continue
        audio_dur = get_media_duration(merged_audio)
        log(f"  合并音频时长: {audio_dur:.1f}s ({len(audio_files)} 条台词)")

        # 2. 下载视频片段
        clip_path = temp_dir / "clips" / f"{shot_id}.mp4"

        video_url = shot.get("video_url")
        has_video = video_url and shot.get("video_status") == "completed"

        if has_video:
            video_path = temp_dir / "video" / f"{shot_id}.mp4"
            if not download_file(video_url, video_path):
                log(f"  视频下载失败，尝试使用静态图片模式", "WARN")
                has_video = False

        if has_video:
            # 3a. AI 视频 + 音频合成
            if not create_shot_video_from_clip(
                video_path, merged_audio, clip_path, temp_dir
            ):
                log(f"  视频合成失败，跳过镜头 {shot_id}", "ERROR")
                continue
        else:
            # 3b. 回退：静态图片 + 音频
            image_url = shot.get("image_url")
            if not image_url:
                log(f"  无视频也无图片，跳过镜头 {shot_id}", "ERROR")
                continue
            image_path = temp_dir / "video" / f"{shot_id}.png"
            if not download_file(image_url, image_path):
                log(f"  图片下载也失败，跳过镜头 {shot_id}", "ERROR")
                continue
            if not _create_from_image(image_path, merged_audio, clip_path):
                log(f"  图片视频合成失败，跳过镜头 {shot_id}", "ERROR")
                continue

        final_dur = get_media_duration(clip_path)
        shot_videos.append(clip_path)
        total_duration += final_dur
        log(f"  => 镜头 {shot_id} 完成 (最终时长: {final_dur:.1f}s)")

    if not shot_videos:
        return {"success": False, "error": "无有效镜头"}

    # 4. 拼接所有镜头为场景视频
    log(f"\n  拼接 {len(shot_videos)} 个镜头...")
    scene_video = output_dir / f"{scene_id}_{scene_name}.mp4"
    if not concat_videos(shot_videos, scene_video):
        return {"success": False, "error": "视频拼接失败"}

    # 5. 添加字幕（可选）
    if subtitle:
        log("  生成字幕...")
        srt_path = temp_dir / f"{scene_id}.srt"
        generate_srt_from_audio_durations(
            scene_data.get("shots", []),
            temp_dir / "audio",
            srt_path
        )

        sub_video = output_dir / f"{scene_id}_{scene_name}_sub.mp4"
        if burn_subtitles(scene_video, srt_path, sub_video):
            scene_video.unlink()
            scene_video = sub_video
            log("  字幕添加成功")
        else:
            log("  字幕添加失败，保留无字幕版本", "WARN")

    log(f"\n=> 场景 {scene_id} 完成: {scene_video} ({total_duration:.1f}s)")

    return {
        "success": True,
        "video_path": str(scene_video),
        "duration": total_duration,
        "shots_count": len(shot_videos)
    }


def _create_from_image(image_path: Path, audio_path: Path, output_path: Path) -> bool:
    """从静态图片 + 音频创建视频（回退模式）"""
    duration = get_media_duration(audio_path)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


# ─────────────────────────── 主函数 ───────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="分镜头视频合成工具（AI视频版）- 合并 AI 视频片段与 TTS 配音"
    )
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--scene", default="all", help="场景ID或'all'")
    parser.add_argument("--output", help="输出目录（默认: 项目目录/output/videos）")
    parser.add_argument("--subtitle", action="store_true", help="烧录字幕")
    parser.add_argument("--check-only", action="store_true", help="仅检查资源")
    parser.add_argument("--merge-only", action="store_true", help="仅合并已有场景视频")

    args = parser.parse_args()

    # 检查 FFmpeg
    if not check_ffmpeg():
        log("FFmpeg 未安装！请运行: brew install ffmpeg", "ERROR")
        sys.exit(1)

    project_dir = Path(args.project).resolve()
    shots_dir = project_dir / "shots"
    output_dir = Path(args.output) if args.output else project_dir / "output" / "videos"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 读取 manifest
    manifest_path = shots_dir / "_manifest.yaml"
    if not manifest_path.exists():
        log(f"找不到 manifest: {manifest_path}", "ERROR")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    script_name = manifest.get("script_name", project_dir.name)
    scene_files = manifest.get("files", [])
    if not scene_files:
        log("manifest 中没有场景文件", "ERROR")
        sys.exit(1)

    # ── 仅检查模式 ──
    if args.check_only:
        log("=" * 50)
        log("资源完整性检查")
        log("=" * 50)
        all_ready = True
        for sf in scene_files:
            scene_path = shots_dir / sf["file"]
            if not scene_path.exists():
                print(f"\n❌ {sf.get('scene_id')} - 文件不存在: {sf['file']}")
                all_ready = False
                continue
            scene_data = load_scene_yaml(scene_path)
            status = check_scene_resources(scene_data)
            sid = sf.get("scene_id", "unknown")
            sname = sf.get("scene_name", "未命名")

            vid_icon = "OK" if status["videos_complete"] else "MISS"
            aud_icon = "OK" if status["audio_complete"] else "MISS"
            ready_text = "=> 可生成" if status["ready"] else "=> 资源不完整"
            if not status["ready"]:
                all_ready = False

            print(f"\n{sid} - {sname}")
            print(f"  镜头数: {status['total_shots']}")
            print(f"  视频: {status['videos_ready']}/{status['total_shots']} [{vid_icon}]")
            print(f"  图片: {status['images_ready']}/{status['total_shots']}")
            print(f"  音频: {status['audio_ready']}/{status['total_audio']} [{aud_icon}]")
            print(f"  {ready_text}")

        print("\n" + "=" * 50)
        if all_ready:
            print("所有场景资源完整，可以生成视频！")
        else:
            print("部分场景资源不完整，请先补充缺失资源。")
        print("=" * 50)
        return

    # ── 仅合并模式 ──
    if args.merge_only:
        log("合并已有场景视频...")
        scene_videos = sorted(output_dir.glob("SC_*.mp4"))
        if not scene_videos:
            log("没有找到场景视频文件", "ERROR")
            sys.exit(1)

        log(f"找到 {len(scene_videos)} 个场景视频")
        for sv in scene_videos:
            dur = get_media_duration(sv)
            log(f"  {sv.name} ({dur:.1f}s)")

        final_path = output_dir / f"{script_name}_完整版.mp4"
        if concat_videos(scene_videos, final_path):
            final_dur = get_media_duration(final_path)
            log(f"完整视频已生成: {final_path}")
            log(f"总时长: {final_dur:.1f}秒 ({final_dur/60:.1f}分钟)")
        else:
            log("合并失败", "ERROR")
        return

    # ── 正常处理模式 ──
    scenes_to_process = []
    if args.scene == "all":
        scenes_to_process = scene_files
    else:
        for sf in scene_files:
            if sf.get("scene_id") == args.scene:
                scenes_to_process.append(sf)
                break

    if not scenes_to_process:
        log(f"未找到场景: {args.scene}", "ERROR")
        sys.exit(1)

    log(f"准备处理 {len(scenes_to_process)} 个场景")

    # 处理每个场景
    results = []
    for sf in scenes_to_process:
        scene_path = shots_dir / sf["file"]
        if not scene_path.exists():
            results.append({
                "success": False,
                "error": "文件不存在",
                "scene_id": sf.get("scene_id"),
                "scene_name": sf.get("scene_name")
            })
            continue

        result = process_scene(scene_path, output_dir, subtitle=args.subtitle)
        result["scene_id"] = sf.get("scene_id")
        result["scene_name"] = sf.get("scene_name")
        results.append(result)

    # 汇总结果
    successful = [r for r in results if r["success"]]

    print("\n" + "=" * 60)
    print("视频合成结果")
    print("=" * 60)

    total_duration = 0
    for r in results:
        icon = "[OK]" if r["success"] else "[FAIL]"
        if r["success"]:
            dur = r["duration"]
            total_duration += dur
            m, s = divmod(dur, 60)
            print(f"{icon} {r['scene_id']} - {r['scene_name']}: {int(m)}分{s:.0f}秒, {r['shots_count']}镜头")
            print(f"       输出: {r['video_path']}")
        else:
            print(f"{icon} {r['scene_id']} - {r['scene_name']}: {r.get('error', '未知错误')}")

    # 合并所有成功的场景
    if len(successful) > 1:
        print(f"\n合并 {len(successful)} 个场景...")
        scene_videos = [Path(r["video_path"]) for r in successful]
        final_path = output_dir / f"{script_name}_完整版.mp4"
        if concat_videos(scene_videos, final_path):
            final_dur = get_media_duration(final_path)
            m, s = divmod(final_dur, 60)
            print(f"\n[OK] 完整视频: {final_path}")
            print(f"     总时长: {int(m)}分{s:.0f}秒")
        else:
            print("\n[FAIL] 完整视频合并失败")
    elif len(successful) == 1:
        print(f"\n单场景视频已生成: {successful[0]['video_path']}")

    print("\n" + "=" * 60)
    print(f"成功: {len(successful)}/{len(results)} 场景")
    m, s = divmod(total_duration, 60)
    print(f"总时长: {int(m)}分{s:.0f}秒")
    print("=" * 60)


if __name__ == "__main__":
    main()

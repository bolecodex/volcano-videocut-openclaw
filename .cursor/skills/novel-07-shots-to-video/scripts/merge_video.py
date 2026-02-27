#!/usr/bin/env python3
"""
分镜头视频合成工具
将 shots/*.yaml 中的图片和音频合并成视频
"""

import argparse
import os
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml


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
    for attempt in range(retries):
        try:
            log(f"下载: {url[:80]}...")
            urllib.request.urlretrieve(url, output_path)
            return True
        except Exception as e:
            log(f"下载失败 (尝试 {attempt + 1}/{retries}): {e}", "WARN")
    return False


def get_audio_duration(audio_path: Path) -> float:
    """获取音频时长（秒）"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(audio_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def merge_audio_files(audio_files: list[Path], output_path: Path) -> bool:
    """合并多个音频文件"""
    if len(audio_files) == 0:
        return False
    
    if len(audio_files) == 1:
        # 单个文件直接复制
        import shutil
        shutil.copy(audio_files[0], output_path)
        return True
    
    # 构建 FFmpeg 命令
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
    
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def create_shot_video(image_path: Path, audio_path: Path, output_path: Path, 
                      kenburns: bool = False) -> bool:
    """从图片和音频创建视频片段"""
    duration = get_audio_duration(audio_path)
    
    if kenburns:
        # Ken Burns 效果：微缩放
        vf = f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,zoompan=z='min(zoom+0.0015,1.2)':d={int(duration*24)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-vf", vf,
            "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-shortest",
            str(output_path)
        ]
    else:
        # 静态图片
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-shortest",
            str(output_path)
        ]
    
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def generate_srt(lines: list[dict], output_path: Path, start_time: float = 0) -> float:
    """生成 SRT 字幕文件，返回结束时间"""
    current_time = start_time
    srt_content = []
    
    for i, line in enumerate(lines, 1):
        text = line.get("text", "")
        # 估算时长：中文约 4 字/秒，英文约 2 词/秒
        char_count = len(text)
        duration = max(char_count / 4, 1.5)  # 最少 1.5 秒
        
        start = format_srt_time(current_time)
        end = format_srt_time(current_time + duration)
        
        srt_content.append(f"{i}")
        srt_content.append(f"{start} --> {end}")
        srt_content.append(text)
        srt_content.append("")
        
        current_time += duration
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_content))
    
    return current_time


def format_srt_time(seconds: float) -> str:
    """格式化 SRT 时间码"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> bool:
    """将字幕烧录到视频"""
    # 使用 FFmpeg 的 subtitles 滤镜
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"subtitles={srt_path}:force_style='FontSize=24,FontName=Noto Sans CJK SC,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1,Alignment=2,MarginV=30'",
        "-c:a", "copy",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def concat_videos(video_files: list[Path], output_path: Path, 
                  transition: float = 0) -> bool:
    """拼接多个视频"""
    if len(video_files) == 0:
        return False
    
    if len(video_files) == 1:
        import shutil
        shutil.copy(video_files[0], output_path)
        return True
    
    # 创建文件列表
    list_file = output_path.parent / "concat_list.txt"
    with open(list_file, "w") as f:
        for vf in video_files:
            f.write(f"file '{vf.absolute()}'\n")
    
    if transition > 0:
        # 带转场效果的拼接（更复杂，需要重新编码）
        # 简化处理：使用 xfade 滤镜
        log("转场效果暂未实现，使用无缝拼接", "WARN")
    
    # 无缝拼接
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True)
    list_file.unlink()  # 删除临时文件
    return result.returncode == 0


def load_scene_yaml(yaml_path: Path) -> dict:
    """加载场景 YAML 文件"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_scene_resources(scene_data: dict) -> dict:
    """检查场景资源完整性"""
    shots = scene_data.get("shots", [])
    
    total_shots = len(shots)
    images_ready = 0
    audio_ready = 0
    total_audio = 0
    
    for shot in shots:
        # 检查图片
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
        "images_ready": images_ready,
        "images_complete": images_ready == total_shots,
        "audio_ready": audio_ready,
        "total_audio": total_audio,
        "audio_complete": audio_ready == total_audio,
        "ready": images_ready == total_shots and audio_ready == total_audio
    }


def process_scene(scene_path: Path, output_dir: Path, 
                  subtitle: bool = False, kenburns: bool = False) -> dict:
    """处理单个场景，生成视频"""
    scene_data = load_scene_yaml(scene_path)
    scene_id = scene_data.get("scene_id", "unknown")
    scene_name = scene_data.get("scene_name", "未命名")
    
    log(f"处理场景: {scene_id} - {scene_name}")
    
    # 检查资源
    status = check_scene_resources(scene_data)
    if not status["ready"]:
        log(f"场景资源不完整: 图片 {status['images_ready']}/{status['total_shots']}, "
            f"音频 {status['audio_ready']}/{status['total_audio']}", "ERROR")
        return {"success": False, "error": "资源不完整"}
    
    # 创建临时目录
    temp_dir = output_dir / "temp" / scene_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "images").mkdir(exist_ok=True)
    (temp_dir / "audio").mkdir(exist_ok=True)
    (temp_dir / "clips").mkdir(exist_ok=True)
    
    shot_videos = []
    total_duration = 0
    
    for shot in scene_data.get("shots", []):
        shot_id = shot.get("id", "unknown")
        log(f"  处理镜头: {shot_id}")
        
        # 1. 下载图片
        image_url = shot.get("image_url")
        image_path = temp_dir / "images" / f"{shot_id}.png"
        if not download_file(image_url, image_path):
            log(f"  图片下载失败，跳过镜头 {shot_id}", "ERROR")
            continue
        
        # 2. 下载并合并音频
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
        if not merge_audio_files(audio_files, merged_audio):
            log(f"  音频合并失败，跳过镜头 {shot_id}", "ERROR")
            continue
        
        # 3. 生成视频片段
        clip_path = temp_dir / "clips" / f"{shot_id}.mp4"
        if not create_shot_video(image_path, merged_audio, clip_path, kenburns):
            log(f"  视频生成失败，跳过镜头 {shot_id}", "ERROR")
            continue
        
        shot_videos.append(clip_path)
        duration = get_audio_duration(merged_audio)
        total_duration += duration
        log(f"  ✓ 镜头 {shot_id} 完成 ({duration:.1f}秒)")
    
    if not shot_videos:
        return {"success": False, "error": "无有效镜头"}
    
    # 4. 拼接所有镜头
    scene_video = output_dir / f"{scene_id}_{scene_name}.mp4"
    if not concat_videos(shot_videos, scene_video):
        return {"success": False, "error": "视频拼接失败"}
    
    # 5. 添加字幕（可选）
    if subtitle:
        log("  生成字幕...")
        srt_path = temp_dir / f"{scene_id}.srt"
        all_lines = []
        for shot in scene_data.get("shots", []):
            all_lines.extend(shot.get("lines", []))
        generate_srt(all_lines, srt_path)
        
        final_video = output_dir / f"{scene_id}_{scene_name}_sub.mp4"
        if burn_subtitles(scene_video, srt_path, final_video):
            scene_video.unlink()  # 删除无字幕版本
            scene_video = final_video
    
    log(f"✓ 场景 {scene_id} 完成: {scene_video}")
    
    return {
        "success": True,
        "video_path": scene_video,
        "duration": total_duration,
        "shots_count": len(shot_videos)
    }


def main():
    parser = argparse.ArgumentParser(description="分镜头视频合成工具")
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--scene", default="all", help="场景ID或'all'")
    parser.add_argument("--output", help="输出目录（默认: 项目目录/output/videos）")
    parser.add_argument("--fps", type=int, default=24, help="视频帧率")
    parser.add_argument("--subtitle", action="store_true", help="生成字幕")
    parser.add_argument("--transition", type=float, default=0, help="转场时长(秒)")
    parser.add_argument("--kenburns", action="store_true", help="Ken Burns 缩放效果")
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
    
    # 获取场景列表
    scene_files = manifest.get("files", [])
    if not scene_files:
        log("manifest 中没有场景文件", "ERROR")
        sys.exit(1)
    
    # 仅检查模式
    if args.check_only:
        log("资源检查模式")
        for sf in scene_files:
            scene_path = shots_dir / sf["file"]
            if scene_path.exists():
                scene_data = load_scene_yaml(scene_path)
                status = check_scene_resources(scene_data)
                scene_id = sf.get("scene_id", "unknown")
                scene_name = sf.get("scene_name", "未命名")
                
                img_status = "✅" if status["images_complete"] else "❌"
                aud_status = "✅" if status["audio_complete"] else "❌"
                ready_status = "✅ 可生成" if status["ready"] else "❌ 资源不完整"
                
                print(f"\n{scene_id} - {scene_name}")
                print(f"  镜头数: {status['total_shots']}")
                print(f"  图片: {status['images_ready']}/{status['total_shots']} {img_status}")
                print(f"  音频: {status['audio_ready']}/{status['total_audio']} {aud_status}")
                print(f"  状态: {ready_status}")
        return
    
    # 仅合并模式
    if args.merge_only:
        log("合并已有场景视频")
        scene_videos = sorted(output_dir.glob("SC_*.mp4"))
        if not scene_videos:
            log("没有找到场景视频文件", "ERROR")
            sys.exit(1)
        
        final_path = output_dir / f"{project_dir.name}_完整版.mp4"
        if concat_videos(scene_videos, final_path):
            log(f"✓ 完整视频已生成: {final_path}")
        else:
            log("合并失败", "ERROR")
        return
    
    # 正常处理模式
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
    
    # 处理每个场景
    results = []
    for sf in scenes_to_process:
        scene_path = shots_dir / sf["file"]
        if scene_path.exists():
            result = process_scene(
                scene_path, output_dir,
                subtitle=args.subtitle,
                kenburns=args.kenburns
            )
            result["scene_id"] = sf.get("scene_id")
            result["scene_name"] = sf.get("scene_name")
            results.append(result)
    
    # 汇总
    successful = [r for r in results if r["success"]]
    
    print("\n" + "=" * 50)
    print("视频合成结果")
    print("=" * 50)
    
    total_duration = 0
    for r in results:
        status = "✅" if r["success"] else "❌"
        if r["success"]:
            duration_str = f"{r['duration']:.1f}秒"
            total_duration += r["duration"]
            print(f"{status} {r['scene_id']} - {r['scene_name']}: {duration_str}, {r['shots_count']}镜头")
            print(f"   输出: {r['video_path']}")
        else:
            print(f"{status} {r['scene_id']} - {r['scene_name']}: {r.get('error', '未知错误')}")
    
    # 合并所有场景
    if len(successful) > 1:
        log("\n合并所有场景...")
        scene_videos = [Path(r["video_path"]) for r in successful]
        final_path = output_dir / f"{project_dir.name}_完整版.mp4"
        if concat_videos(scene_videos, final_path):
            print(f"\n✅ 完整视频: {final_path}")
            print(f"   总时长: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()

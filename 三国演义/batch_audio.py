#!/usr/bin/env python3
"""批量生成分镜配音脚本"""
import os
import sys
import json
import yaml
import subprocess
import time
from pathlib import Path

# 配置
PROJECT_DIR = Path("/Users/bytedance/Documents/实验/long_video_skills/三国演义")
SHOTS_DIR = PROJECT_DIR / "shots"
AUDIO_DIR = PROJECT_DIR / "assets" / "audio"
XSKILL_API = Path("/Users/bytedance/Documents/实验/long_video_skills/skills-openclaw/mcp-proxy/xskill_api.py")

AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# 读取音色映射
with open(SHOTS_DIR / "_manifest.yaml", "r", encoding="utf-8") as f:
    manifest = yaml.safe_load(f)
    voice_mapping = manifest.get("voice_mapping", {})

def get_voice_id(speaker):
    """获取说话人对应的音色ID"""
    if speaker in voice_mapping:
        return voice_mapping[speaker]["voice_id"]
    return voice_mapping.get("_default_male", {}).get("voice_id")

def synthesize_audio(text, voice_id):
    """调用TTS API生成音频"""
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(XSKILL_API),
                "speak",
                "--action", "synthesize",
                "--text", text,
                "--voice_id", voice_id
            ],
            capture_output=True,
            text=True,
            check=True
        )
        response = json.loads(result.stdout)
        if response.get("success"):
            return response["audio_url"]
        else:
            print(f"❌ TTS失败: {response}")
            return None
    except Exception as e:
        print(f"❌ TTS异常: {e}")
        return None

def download_audio(audio_url, output_path):
    """下载音频文件到本地"""
    try:
        subprocess.run(
            ["curl", "-L", "-o", str(output_path), audio_url],
            check=True,
            capture_output=True
        )
        return True
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return False

def process_scene(scene_file):
    """处理单个场景文件"""
    scene_path = SHOTS_DIR / scene_file
    if not scene_path.exists():
        print(f"❌ 文件不存在: {scene_file}")
        return False, 0, 0
    
    print(f"\n📖 处理场景: {scene_file}")
    
    with open(scene_path, "r", encoding="utf-8") as f:
        scene_data = yaml.safe_load(f)
    
    success_count = 0
    total_count = 0
    
    for shot in scene_data.get("shots", []):
        shot_id = shot["shot_id"]
        print(f"  🎬 镜头: {shot_id}")
        
        for idx, line in enumerate(shot.get("dialogue", [])):
            total_count += 1
            
            # 跳过已完成的
            if line.get("audio_status") == "completed":
                print(f"    ✓ 跳过已完成: {idx}")
                success_count += 1
                continue
            
            speaker = line.get("speaker", "旁白")
            text = line.get("text", "")
            print(f"    🎤 [{idx}] {speaker}: {text}")
            
            voice_id = get_voice_id(speaker)
            if not voice_id:
                print(f"    ❌ 无法获取音色ID: {speaker}")
                continue
            
            # 生成音频
            audio_url = synthesize_audio(text, voice_id)
            if not audio_url:
                continue
            
            # 下载音频
            audio_filename = f"{shot_id}_line_{idx}.mp3"
            audio_path = AUDIO_DIR / audio_filename
            if not download_audio(audio_url, audio_path):
                continue
            
            # 更新分镜数据
            line["audio_url"] = audio_url
            line["audio_path"] = f"assets/audio/{audio_filename}"
            line["audio_status"] = "completed"
            success_count += 1
            print(f"    ✓ 成功: {audio_filename}")
            
            # 避免API限流
            time.sleep(1)
    
    # 保存更新后的分镜文件
    with open(scene_path, "w", encoding="utf-8") as f:
        yaml.dump(scene_data, f, allow_unicode=True, sort_keys=False)
    
    print(f"  📝 保存: {scene_file}")
    return True, success_count, total_count

def main():
    print("🚀 开始批量生成配音")
    print(f"📂 项目目录: {PROJECT_DIR}")
    
    # 处理场景2-12（场景1已完成）
    scene_files = [f"SC_{i:02d}_*.yaml" for i in range(2, 13)]
    
    total_success = 0
    total_total = 0
    
    # 查找所有场景文件
    from glob import glob
    all_scenes = []
    for pattern in scene_files:
        matches = glob(str(SHOTS_DIR / pattern))
        all_scenes.extend([Path(p).name for p in matches])
    
    # 去重并排序
    all_scenes = sorted(list(set(all_scenes)))
    
    print(f"📋 待处理场景: {len(all_scenes)} 个")
    
    for scene_file in all_scenes:
        success, s_count, t_count = process_scene(scene_file)
        total_success += s_count
        total_total += t_count
        print(f"  📊 进度: {s_count}/{t_count}")
    
    print(f"\n✅ 批量处理完成!")
    print(f"   总成功: {total_success}/{total_total}")

if __name__ == "__main__":
    main()

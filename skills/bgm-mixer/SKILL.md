---
name: bgm-mixer
description: >
  为视频素材智能叠加 BGM 背景音乐，支持自动降低对白段 BGM 音量（ducking）、多种情绪预设。
  在以下场景使用：(1) 给投流素材添加背景音乐，(2) BGM 与对白混音，(3) 音频后期处理。
  触发关键词："BGM"、"背景音乐"、"混音"、"配乐"、"音乐叠加"。
---

# BGM 智能匹配与混音

为投流素材叠加 BGM，自动处理对白段音量。投流素材加 BGM 后完播率提升 20-40%。

## 前置条件

- FFmpeg 已安装
- BGM 音频文件（MP3/WAV/AAC）

## 工作流程

### 第一步：准备 BGM 素材

将 BGM 文件放入 `assets/bgm/` 目录，按情绪分类命名：

```
assets/bgm/
├── tense_suspense_01.mp3      # 紧张悬疑
├── warm_family_01.mp3         # 温馨治愈
├── epic_battle_01.mp3         # 激昂史诗
├── sad_farewell_01.mp3        # 悲伤催泪
├── romantic_love_01.mp3       # 浪漫甜蜜
└── cool_rhythm_01.mp3         # 酷炫节奏
```

### 第二步：混音

```bash
# 基本混音（自动 ducking）
python3 scripts/bgm_mix.py video/output/promo.mp4 assets/bgm/tense_01.mp3

# 自定义输出路径
python3 scripts/bgm_mix.py video.mp4 bgm.mp3 -o output_with_bgm.mp4

# 调整 BGM 音量
python3 scripts/bgm_mix.py video.mp4 bgm.mp3 --bgm-volume -12

# 禁用自动 ducking
python3 scripts/bgm_mix.py video.mp4 bgm.mp3 --no-ducking

# 查看 BGM 库
python3 scripts/bgm_mix.py --list-bgm
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--bgm-volume` | -15dB | BGM 基础音量 |
| `--duck-volume` | -25dB | 对白段 BGM 音量 |
| `--fade-in` | 1.0s | BGM 淡入时长 |
| `--fade-out` | 2.0s | BGM 淡出时长 |
| `--no-ducking` | false | 禁用自动 ducking |

### Ducking 原理

脚本会自动检测视频中的对白段落（通过静音检测），在对白出现时降低 BGM 音量，
对白结束后恢复。这样既有背景氛围感，又不会掩盖台词。

## 情绪分类

| 类别 | 适用场景 |
|------|---------|
| 紧张悬疑 (tense) | 冲突、打斗、追逐、权谋 |
| 温馨治愈 (warm) | 家庭、亲子、和好 |
| 激昂史诗 (epic) | 逆袭、反转、高潮 |
| 悲伤催泪 (sad) | 离别、牺牲、回忆 |
| 浪漫甜蜜 (romantic) | 恋爱、表白、CP互动 |
| 酷炫节奏 (cool) | 现代都市、炫酷展示 |

---
name: 字幕硬烧录
description: >
  将 SRT 字幕文件硬烧入视频，支持多种字幕样式（居中大字幕/底部标准/顶部提示/戏剧化）。
  在以下场景使用：(1) 给视频添加字幕，(2) 硬烧字幕到投流素材，(3) 自定义字幕样式。
  触发关键词："字幕烧录"、"添加字幕"、"硬字幕"、"burn subtitle"、"字幕样式"。
---

# 字幕烧录

将 SRT 字幕硬烧入视频。S 级投流素材必须有字幕（大量用户静音浏览）。

## 前置条件

- FFmpeg 已安装（需支持 ASS/subtitles 滤镜）
- SRT 字幕文件（可由 `asr-subtitle` 技能生成）

## 工作流程

### 第一步：准备字幕文件

如果还没有字幕文件，先用 ASR 技能提取：
```bash
python3 scripts/asr_extract.py "video/原始短剧/05.mp4" -o video/output/
```

### 第二步：烧录字幕

```bash
# 使用默认居中大字幕样式（投流推荐）
python3 scripts/burn_subtitle.py video/output/promo_combined.mp4 video/output/asr_combined.srt

# 指定输出路径
python3 scripts/burn_subtitle.py video.mp4 sub.srt -o video_with_sub.mp4

# 使用不同样式
python3 scripts/burn_subtitle.py video.mp4 sub.srt -s bottom_standard
python3 scripts/burn_subtitle.py video.mp4 sub.srt -s dramatic

# 查看所有可用样式
python3 scripts/burn_subtitle.py --list-styles
```

### 可用样式

| 样式 | 说明 | 适用场景 |
|------|------|---------|
| `center_large` | 居中大字幕，白字黑边 | 投流素材（默认） |
| `bottom_standard` | 底部标准字幕 | 常规视频 |
| `top_hint` | 顶部提示字幕（黄色） | 提示/注释 |
| `dramatic` | 戏剧化大字幕 | 强调冲突/高潮 |

### 完整流水线

```bash
# 1. 提取台词
python3 scripts/asr_extract.py video/ -o output/
# 2. 分析视频
python3 scripts/analyze_video.py video/ -o output/
# 3. 剪辑
python3 scripts/ffmpeg_cut.py output/highlights_combined.json video/
# 4. 烧录字幕
python3 scripts/burn_subtitle.py output/promo_combined.mp4 output/asr_combined.srt
```

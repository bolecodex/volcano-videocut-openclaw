---
name: asr-subtitle
description: >
  使用火山引擎 ASR 或多模态模型提取视频台词文本和精确时间戳，生成 JSON + SRT 字幕文件。
  在以下场景使用：(1) 提取视频中的对白台词，(2) 生成字幕文件 SRT，(3) 为视频分析提供台词辅助，
  (4) 精确定位台词时间戳用于切点校验。
  触发关键词："ASR"、"语音识别"、"台词提取"、"字幕生成"、"转文字"、"语音转文"。
---

# ASR 语音转文字

提取视频中的台词对白，生成带时间戳的文本和 SRT 字幕文件。

## 前置条件

- Python 3.10+，已安装 `openai` 和 `python-dotenv` 包
- `.env` 文件中配置了 `ARK_API_KEY`（用于 Ark API ASR）
- FFmpeg 已安装（用于音频提取和备用静音检测模式）

## 工作流程

### 第一步：提取台词

```bash
# 处理单个视频
python3 scripts/asr_extract.py "video/原始短剧/05.mp4" -o video/output/

# 处理整个目录
python3 scripts/asr_extract.py "video/原始短剧/" -o video/output/

# 仅使用 FFmpeg 静音检测（无需 API，精度较低）
python3 scripts/asr_extract.py "video/原始短剧/05.mp4" --method silence
```

### 第二步：查看输出

脚本会在输出目录生成两个文件：

- `asr_{视频名}.json` -- 结构化台词数据（含时间戳、说话者）
- `asr_{视频名}.srt` -- 标准 SRT 字幕文件

JSON 格式：
```json
{
  "video": "05.mp4",
  "duration": 300.5,
  "utterance_count": 45,
  "utterances": [
    {
      "start_time": 1.20,
      "end_time": 3.85,
      "text": "你怎么又来了？",
      "speaker": "女主"
    }
  ]
}
```

### 第三步：与视频分析联动

ASR 文件生成后，`analyze_video.py` 会自动检测并加载这些台词数据，辅助切点精确化。
建议先运行 ASR 提取，再运行视频分析：

```bash
# 先提取台词
python3 scripts/asr_extract.py "video/原始短剧/" -o video/output/
# 再分析视频（会自动加载 ASR 数据）
python3 scripts/analyze_video.py "video/原始短剧/" -o video/output/
```

## ASR 方法说明

| 方法 | 说明 | 精度 | 需要 API |
|------|------|------|---------|
| `auto` | 先尝试 Ark API，失败后回退 silence | 高→中 | 可选 |
| `ark` | 通过 Ark 多模态模型转录 | 高 | 是 |
| `silence` | FFmpeg 静音检测标记语音段 | 低 | 否 |

## 常见问题

- 长视频（>10分钟）建议分段处理以避免超时
- SRT 文件可直接用于 `subtitle-burner` 技能烧录字幕
- silence 模式只能标记语音段落，无法识别具体文字内容

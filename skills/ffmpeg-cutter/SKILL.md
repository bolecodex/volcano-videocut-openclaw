---
name: 高光切片与成片合成
description: >
  使用 FFmpeg 根据结构化高光 JSON 文件切割和合并视频片段，生成投流广告视频。
  在以下场景使用：(1) 按时间范围从视频中切割片段，(2) 将多个视频片段合并为一个，
  (3) 将 video-analyzer 输出的高光片段加工为投流视频，(4) 按时间戳提取并组合视频片段。
  触发关键词："剪辑"、"切片"、"合并"、"FFmpeg"、"投流视频"、"剪视频"、"合成视频"。
---

# FFmpeg 视频剪辑

使用 FFmpeg 将高光片段切割并合并为投流广告视频。

## 前置条件

- 已安装 FFmpeg（macOS: `brew install ffmpeg`，Linux: `apt install ffmpeg`）
- 一个高光 JSON 文件（由 video-analyzer 技能生成，或手动创建）
- 对应的原始视频文件

## 工作流程

### 第一步：确认输入

确认用户已准备好：
1. 高光 JSON 文件（来自 `video/output/highlights_*.json`）
2. 对应的原始视频文件
3. FFmpeg 已安装（运行 `which ffmpeg` 验证）

### 第二步：选择处理模式

脚本支持三种模式：

**模式 A — 使用推荐组合：**
```bash
python3 scripts/ffmpeg_cut.py video/output/highlights_05.json "video/原始短剧/05.mp4" -v 1
```

**模式 B — 指定片段 ID：**
```bash
python3 scripts/ffmpeg_cut.py video/output/highlights_05.json "video/原始短剧/05.mp4" -s 3 1 5 7
```

**模式 C — 生成所有推荐版本：**
```bash
python3 scripts/ffmpeg_cut.py video/output/highlights_05.json "video/原始短剧/05.mp4" --all-versions
```

### 第三步：输出选项

```bash
# 自定义输出目录
python3 scripts/ffmpeg_cut.py highlights.json source.mp4 -o /path/to/output/

# 重新编码（较慢，但能处理不同编码格式的片段）
python3 scripts/ffmpeg_cut.py highlights.json source.mp4 --reencode
```

### 处理细节

1. **切割**：使用 `-ss`（输入定位）快速精确切割，配合 `-c copy`（流拷贝，不重新编码）
2. **合并**：使用 FFmpeg 的 concat 分离器拼接片段
3. **重新编码模式**：开启 `--reencode` 后使用 libx264/aac 统一编码输出（源片段编码不一致时需要）

### 输出

- 视频默认保存到 `video/output/`，文件名格式为 `promo_{集数}_{版本名}.mp4`
- 临时切片文件在合并后自动清理

### 高光 JSON 格式要求

输入的 JSON 必须包含 `highlights` 数组，每个对象至少包含：
- `id`：整数标识符
- `start_time`：开始时间戳（HH:MM:SS）
- `end_time`：结束时间戳（HH:MM:SS）

可选的 `recommended_combinations` 数组：
- `version`：版本号（整数）
- `segments`：按播放顺序排列的高光 ID 数组
- `name`：版本名称

## 常见问题

- 合并后出现画面卡顿，使用 `--reencode` 重新编码所有片段为统一格式
- 切割不够精确是因为 `-c copy` 基于关键帧对齐，使用 `--reencode` 可实现逐帧精确切割
- 确保源视频路径与 video-analyzer 分析的视频一致

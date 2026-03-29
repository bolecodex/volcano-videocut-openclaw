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

### 多集一条成片（与投流高光分析配套）

本仓库的 `ffmpeg_cut.py` 读取的是 **跨集分析 JSON**（含 `segments_to_keep`、`hook`、`final_structure.segment_order`），**不是**旧版 `highlights` 数组。

- **必须**使用 **一次** `analyze_video.py` 对**整夹**分析得到的 **一个** `highlights_*.json`（勿对每集单独分析再拼多条成片）。
- 第二个参数传 **原片所在文件夹**（与 JSON 里 `source_file` 一致），不是单个 mp4：
  ```bash
  python3 scripts/ffmpeg_cut.py "video/output/highlights_某剧.json" "video/某剧/" -o video/output -n 某剧_投流
  ```
- 默认会 **重编码** 以保证切点精确与音画同步；输出日志含 `Output: ...promo_*.mp4`。

**Agent 收尾**：在回复里写出 **`promo_*.mp4` 与输入 JSON 的完整路径**，便于用户在对话面板看到产出文件位置。

### 第一步：确认输入

确认用户已准备好：
1. **一个** 跨集高光 JSON（`video/output/highlights_*.json`）
2. **原片目录**（内含 JSON 中引用的各集 mp4）
3. FFmpeg 已安装（`which ffmpeg`）

### 第二步：执行合成（本仓库常用命令）

```bash
python3 scripts/ffmpeg_cut.py "video/output/highlights_原始短剧2.json" "video/原始短剧2/" -o video/output -n 原始短剧2_投流
```

可选：`--no-reencode` 加快但切点可能不精确；`--no-normalize` 跳过响度归一。

### 第三步：输出选项

```bash
python3 scripts/ffmpeg_cut.py highlights.json "video/原片目录/" -o /path/to/output/ -n 成片名称
```

### 处理细节

1. 按 `segment_order` 切割各段（含可选全局 **hook**），再 concat；**整条成片只有开头一个 hook**（前提是 JSON 来自跨集单次分析）。
2. 合并后做响度归一等后处理（见脚本默认行为）。

### 输出

- 默认 `video/output/promo_{名称}.mp4`（名称由 `-n` 决定，脚本会自动加 `promo_` 前缀）
- 日志中的 `Output:` 行即为最终成片路径

### JSON 格式要求（本仓库）

输入 JSON 须包含：`segments_to_keep`（含 `id`、`source_file`、`start_time`、`end_time`）、可选 `hook`、`final_structure.segment_order`。结构见 `skills/video-analyzer/references/output_schema.md` 或与 `analyze_video.py` 实际输出一致。

## 常见问题

- 合并后出现画面卡顿，使用 `--reencode` 重新编码所有片段为统一格式
- 切割不够精确是因为 `-c copy` 基于关键帧对齐，使用 `--reencode` 可实现逐帧精确切割
- 确保源视频路径与 video-analyzer 分析的视频一致

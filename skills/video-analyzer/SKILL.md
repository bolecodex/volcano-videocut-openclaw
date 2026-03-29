---
name: 投流高光片段分析
description: >
  使用豆包 Seed 2.0（火山引擎 Ark API）或其他多模态大模型分析短剧视频，提取适合投流广告的高光片段。
  在以下场景使用：(1) 从短剧视频中找出适合做广告素材的高光/卡点片段，(2) 分析视频提取投流剪辑点，
  (3) 识别短剧中吸引人的开头、悬念结尾、冲突场景，(4) 生成带时间戳和理由的结构化高光列表 (JSON)。
  触发关键词："投流"、"高光"、"视频分析"、"卡点"、"广告素材"、"分析视频"、"找高光"。
---

# 视频高光分析

分析短剧视频，提取适合制作投流广告素材的高光片段。

## 前置条件

- Python 3.10+，已安装 `openai` 和 `python-dotenv` 包
- `.env` 文件中配置了 `ARK_API_KEY`、`ARK_MODEL_NAME`、`ARK_BASE_URL`
- 视频文件格式为 mp4/mov/webm

## 工作流程

### 多集短剧 → 一条成片（必读，避免「每集一个钩子」）

**错误做法**：对用户给出的多集 mp4 **逐个**运行 `analyze_video.py 某集.mp4`，或对同一目录使用 **`--single`**，再分别 `ffmpeg_cut` 得到多条成片后手动拼接。这样每集 JSON 都会带各自的 **hook**，合并后会在**每集前重复高光**，剧情不连贯。

**正确做法（跨集一次分析）**：

1. 输入路径选 **整夹目录**（内含多集 `Episode*.mp4` 等），**只跑一条命令**，**不要**加 `--single`：
   ```bash
   python3 scripts/analyze_video.py "video/原始短剧2/" -o video/output --name highlights_原始短剧2
   ```
2. 得到 **一个** 合并结果 `highlights_*.json`（集数多时会先写 `*_batch*.json` 再合并为一个顶层 JSON），其中 **全局仅一个** `hook`，`segments_to_keep` 按故事顺序跨集排列。
3. 再 **只跑一次** `ffmpeg_cut.py`，第二个参数填**同一原片目录**：
   ```bash
   python3 scripts/ffmpeg_cut.py "video/output/highlights_原始短剧2.json" "video/原始短剧2/" -o video/output -n 原始短剧2_投流
   ```

**Agent 收尾**：在回复正文里**明确写出**生成的 `highlights_*.json` 与 `promo_*.mp4` 的完整路径（或相对项目根路径），便于用户在对话里直接看到产出位置。

### 第一步：确认项目环境

找到包含 `scripts/analyze_video.py` 脚本和 `video/` 目录的工作区，确认 `.env` 中已配置 `ARK_API_KEY`。

### 第二步：执行视频分析

运行分析脚本，支持单个视频或批量分析。脚本会自动将大于 20MB 的视频压缩后通过 base64 编码发送给 API。

```bash
# 分析单个视频（大于 20MB 自动压缩）
python3 scripts/analyze_video.py "video/原始短剧/05.mp4" -o video/output/

# 跨集一次分析（多集投流素材，推荐：整夹、勿用 --single）
python3 scripts/analyze_video.py "video/原始短剧/" -o video/output/ --name highlights_原始短剧

# 使用自定义提示词
python3 scripts/analyze_video.py "video/原始短剧/05.mp4" --prompt scripts/prompts/custom_prompt.txt

# 使用公开视频 URL（无需压缩）
python3 scripts/analyze_video.py "video/原始短剧/05.mp4" --method url --video-url "https://example.com/video.mp4"

# 调整压缩目标大小
python3 scripts/analyze_video.py "video/原始短剧/05.mp4" --max-size-mb 30
```

### 第三步：展示结果供人工审核

分析完成后，读取 `video/output/highlights_*.json` 中的结果，以可读格式展示给用户：

- 列出每个高光片段的时间范围、类型、理由和优先级
- 展示推荐的组合版本
- 请用户确认、修改或删除片段，确认后再进行剪辑

### 输出格式

脚本输出的 JSON 文件结构详见 `references/output_schema.md`。

每个高光片段的关键字段：
- `start_time` / `end_time`：精确时间戳（HH:MM:SS）
- `type`：opening（开头）| hook（钩子）| conflict（冲突）| climax（高潮）| emotional（情感）| suspense（悬念）
- `priority`：1-5（5 为最高优先级）
- `suggested_position`：opening（开头）| middle（中间）| ending（结尾）
- `tags`：描述标签
- `reason`：该片段适合投流的具体理由
- `contains_transition`：是否含"未完待续"等转场画面（含则需排除）

### 重要剪辑原则

- **前置爽点**：推荐组合中，应将最刺激的反转/爽点放在开头，再倒叙铺垫
- **片段长度**：每段建议 30-60 秒连续剧情，避免 10 秒碎片拼接
- **总时长**：推荐组合总时长 2-5 分钟
- **必须排除**："未完待续"、片尾字幕、黑屏转场等非剧情画面
- **黄金结构**：开头钩子 20% → 中间铺垫 60% → 结尾卡点 20%

### 剪辑标准参考

分析提示词（位于 `scripts/prompts/highlight_prompt.txt`）已内置专业剪辑标准。完整标准详见 `references/editing_criteria.md`。

## 常见问题

- 视频自动压缩至约 20MB 后进行 base64 编码，可通过 `--max-size-mb` 调整
- 压缩使用 FFmpeg 缩放至 720p 并降低码率，保留音频
- 如果模型返回非 JSON 格式，脚本会将原始响应保存为 `raw_response` 供人工查看
- 如有公开视频 URL，可用 `--method url` 跳过压缩
- 确保 `.env` 中有有效的 `ARK_API_KEY`，可在火山引擎控制台获取

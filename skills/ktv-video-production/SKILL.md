---
name: KTV 歌词特效视频
description: >
  用 Remotion 在视频或音频上叠加 KTV 风格歌词：asr-to-lrc.py 调火山 openspeech 生成 LRC（可选逐词时间戳），再渲染歌词动画。
  视频模式底部双行，音频模式全屏滚动高亮。需 DOUBAO_SPEECH_API_KEY 等，详见正文。
trigger: KTV 歌词、LRC、歌词特效、Remotion 歌词、卡拉OK 字幕、视频加歌词
---

# ktv-video-production

## Description
使用 Remotion 在源视频/音频上叠加 KTV 歌词效果。通过独立的 asr-to-lrc.py 脚本调用火山引擎 openspeech 自动识别语音并生成 LRC 歌词（可选逐词时间戳），再由 Remotion 项目渲染歌词动画。视频模式下歌词叠加在视频底部（当前行+下一行），音频模式下歌词全屏滚动高亮显示。

## Trigger
当用户提到以下关键词时触发此 Skill：
- KTV 歌词视频
- remotion 歌词
- 歌词特效视频
- 制作歌词 MV
- LRC 歌词动画
- 视频加歌词
- 视频字幕特效
- 音频加歌词

## Instructions

### 概述

本 Skill 分为两个独立阶段：

**阶段 A — 语音识别（asr-to-lrc.py）**
- 独立 Python 脚本，输入音频/视频文件，输出 LRC 歌词
- 默认使用**火山引擎 openspeech**（需要 `DOUBAO_SPEECH_API_KEY`）
- 支持尽量输出逐词时间戳（若接口返回 `words` 字段），否则输出普通 LRC

**阶段 B — 歌词视频渲染（Remotion 项目）**
- scaffold.sh 生成 Remotion 项目骨架
- 导入增强 LRC → 解析为逐字时间轴 JSON → 渲染歌词动画
- 输出视频时长与原始媒体完全对齐

### 完整执行步骤

**Step 1：确认用户输入**

向用户确认：
- **媒体文件**：视频（mp4/webm/mov）或 音频（mp3/wav/m4a/flac）（必需）
- **视频分辨率**：默认 1920×1080
- **帧率**：默认 30fps
- **高亮颜色**：默认 `#00ff88`（亮绿色）

判断文件类型：
- 扩展名为 mp4/webm/mov/avi/mkv → 视频模式 (`MODE = "video"`)
- 扩展名为 mp3/wav/m4a/flac/ogg/aac → 音频模式 (`MODE = "audio"`)

**Step 2：阶段 A — 生成增强 LRC 歌词**

前置条件（仅首次）：
- 本机可用 `ffmpeg`
- 项目根目录存在 `.env`，包含 `DOUBAO_SPEECH_API_KEY=...`

使用独立脚本生成增强 LRC：
```bash
python scripts/asr-to-lrc.py <媒体文件路径> -o lyrics.lrc
```

asr-to-lrc.py 参数：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `media` | (必填) | 音频/视频文件路径 |
| `-o/--output` | lyrics.lrc | 输出 LRC 文件路径 |
| `--result-json` | (自动) | 保存火山 ASR 完整结果 JSON（默认与输出同名，后缀改为 `.asr.json`） |
| `--no-enhanced` | 关 | 输出普通 LRC（默认尽量输出逐词时间戳，若返回含 words 字段） |
| `--poll-interval` | 5 | 轮询间隔（秒） |
| `--timeout-sec` | 600 | 超时（秒） |
| `--keep-temp` | 关 | 保留临时 mp3 |

输出格式为增强 LRC（逐字时间戳）：
```
[00:05.20] <00:05.20>我<00:05.60>在<00:05.90>人<00:06.30>民<00:06.70>广<00:07.10>场<00:07.50>吃<00:07.90>炸<00:08.30>鸡<00:08.80>
```

如果用户自己有 LRC 歌词文件，可跳过此步骤。

**Step 3：获取媒体时长**

⚠️ 关键步骤：获取原始媒体的精确时长，用于保证输出视频时长对齐。

```bash
# 获取时长（秒，带小数）
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 <媒体文件路径>)
echo "媒体时长: ${DURATION}s"
```

**Step 4：阶段 B — 初始化 Remotion 项目**

```bash
bash ktv-video-production/scripts/scaffold.sh
```

**Step 5：导入文件并更新配置**

1. 将用户上传的媒体文件下载到 `ktv-video-production-project/public/` 目录，重命名为 `media.mp4` 或 `media.mp3`

2. 将增强 LRC 转为 JSON 并放入项目：
```bash
cd ktv-video-production-project
node scripts/parse-lrc.mjs ../lyrics.lrc 30 > src/data/lyrics-data.json
```

3. 修改 `src/config.ts`：
```typescript
export const MODE: "video" | "audio" = "video";  // 根据文件类型
export const MEDIA_SRC = "media.mp4";             // 媒体文件名
export const TOTAL_DURATION_SEC = 245.32;         // ⚠️ 填入 Step 3 获取的精确时长
export const VIDEO_WIDTH = 1920;
export const VIDEO_HEIGHT = 1080;
export const FPS = 30;
```

**Step 6：打包项目给用户**

```bash
cd ktv-video-production-project && zip -r ../ktv-video-production-project.zip . -x "node_modules/*"
```

**Step 7：告知用户使用方式**

```bash
cd ktv-video-production-project
npm install
npm start          # Remotion Studio 预览
npm run preview    # Vite + Player 预览
npm run render     # CLI 导出 MP4（推荐）
```

### 两种展示模式

#### 视频模式（用户上传视频时）
```
┌──────────────────────────────────┐
│                                  │
│         源视频画面（全屏）          │
│                                  │
│                                  │
├──────────────────────────────────┤ ← 渐变半透明蒙层
│  ▶ 当前行：我在人民广场吃炸鸡      │ ← 64px 亮色逐字填充
│    下一行：而此时此刻你在哪里       │ ← 48px 半透明预览
│▁▁▁▁▁▁▁▁▁▁ 进度条 ▁▁▁▁▁▁▁▁▁▁▁▁│
└──────────────────────────────────┘
```

#### 音频模式（用户上传音频时）
```
┌──────────────────────────────────┐
│        (已唱) 第一行歌词           │ ← 暗色，缩小
│        (已唱) 第二行歌词           │ ← 暗色，缩小
│                                  │
│   ★ 当前行：我在人民广场吃炸鸡 ★   │ ← 居中，最大，逐字填充
│                                  │
│        (下一行) 第四行歌词         │ ← 半透明
│        (下一行) 第五行歌词         │ ← 更半透明
│▁▁▁▁▁▁▁▁▁▁ 进度条 ▁▁▁▁▁▁▁▁▁▁▁▁│
└──────────────────────────────────┘
```

### 时长对齐机制

`src/config.ts` 中的 `TOTAL_DURATION_SEC` 控制输出视频的总帧数：
- **设置了 > 0**：`totalFrames = Math.round(TOTAL_DURATION_SEC * FPS)`，输出视频时长精确等于原始媒体
- **未设置 (= 0)**：fallback 到歌词最后一行结束 + 3 秒

务必通过 ffprobe 获取原始媒体精确时长并填入此字段。

### 注意事项
- asr-to-lrc.py 是独立脚本，不依赖 Remotion 项目
- asr-to-lrc.py 默认使用火山引擎转录；请确保 `.env` 中有 `DOUBAO_SPEECH_API_KEY`
- 视频文件会自动通过 ffmpeg 提取音频并转码为 mp3 再转录
- 如果用户已有 LRC 歌词文件，可跳过 ASR 步骤

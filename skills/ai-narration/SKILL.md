---
name: AI解说
description: 根据视频内容生成与画面匹配的解说旁白，使用 Ark TTS 合成有吸引力的配音并替换原音轨
trigger: AI解说、配音、旁白、narration、解说
tags:
  - narration
  - tts
  - voice
  - dubbing
icon: 🎙️
---

# AI 解说 (AI Narration)

## 功能

为短剧投流素材生成与画面匹配的解说配音：先分析视频内容，再生成解说词脚本，经 Ark TTS 合成后替换原音轨。要求声音有吸引力，与画面节奏一致。

## 使用方法

1. 在后期处理面板选择成片视频，点击「AI 解说」。
2. 可选配置：音色（voice_id）、语速（speed）。
3. 脚本会先分析视频关键帧并生成旁白文案，再调用 TTS 合成并替换音频。

## 前置条件

- `.env` 中配置 `ARK_API_KEY`（用于视频分析与文案生成）。
- 可选：`ARK_TTS_ENDPOINT` 或 `ARK_TTS_MODEL` 用于语音合成；未配置时仅生成文案和占位静音，便于后续接入真实 TTS。

## 参数

- **voice_id**: TTS 音色，默认 `zh_female_huayan`。
- **speed**: 语速，默认 1.0。

## 输出

- 成片同目录下生成 `*_narration.mp4`（原画面 + 新解说音轨）。
- 若 TTS 未配置，会生成 `*_script.txt` 与占位音频。

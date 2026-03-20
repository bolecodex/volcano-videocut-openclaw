---
name: BGM自动匹配
description: 根据视频情绪/风格从音乐库中自动匹配合适的 BGM 并混音，支持 ducking
trigger: BGM、背景音乐、自动配乐、匹配BGM
tags:
  - bgm
  - music
  - mood
icon: 🎵
---

# BGM 自动匹配 (BGM Auto Match)

## 功能

分析视频情绪（可选 Ark 多模态），从 `assets/bgm/` 音乐库中按风格匹配最合适的 BGM，并调用混音脚本叠加到视频，支持对白段自动 ducking。

## 使用方法

1. 将 BGM 文件放入 `assets/bgm/`，可选在同目录创建 `bgm_index.json` 标注 emotion/style。
2. 在后期处理面板选择成片，点击「自动匹配 BGM」。
3. 未建索引时按文件名分类（如 tense_xxx.mp3、warm_xxx.mp3）。

## 前置条件

- 已安装 FFmpeg。
- 可选：`.env` 中配置 `ARK_API_KEY` 用于画面情绪分析；未配置时使用默认风格匹配。

## 输出

- 同目录生成 `*_bgm.mp4`（原视频 + 匹配 BGM，对白处自动压低 BGM）。

# 歌曲演唱者 / 乐器 / 音色推断规则（宿主 Agent 参考）

> 本文件为宿主 Agent 提供推断规则指引，具体实现逻辑不落入脚本，由上层编排负责。

## 1. 输入信息来源

- `S1_INTENT` 阶段输出的结构化信息：
  - `character`：角色或人设；
  - `emotion_theme`：情绪主题；
  - `music_style`：音乐风格；
  - `scene`：使用场景；
  - `duration_seconds`：目标时长等。
- `S2_LYRICS` 阶段生成的歌词文本：
  - 语气（第一/第三人称）；
  - 性别暗示（「我老猪」「她」等）；
  - 是否有对唱 / 轮唱 / 合唱的暗示。

## 2. 需要推断的关键字段

宿主 Agent 应在未显式指定的情况下，自动推断以下字段并写入 `song_meta.json`：

- `genre`：主曲风；
- `mood`：情绪；
- `vocal_gender`：`Male` / `Female` / 混合；
- `vocal_persona`：简要人设描述（如「沧桑中年男声」「少年感女声」等）；
- `timbre`：音色（从 GenSong `Timbre` 可选值中选 1–3 个）；
- `instrument`：主要乐器列表（从 GenSong `Instrument` 可选值中选 2–4 个）；
- `scene`：音乐场景标签（可映射到 GenSong `Scene`）。

## 3. 映射建议

### 3.1 情绪 → Mood

可参考 `歌曲生成参数信息.md` 中 `Mood` 表，结合 `emotion_theme` 与歌词内容：

- 「emo / 失恋 / 孤独」 → `Sentimental/Melancholic/Lonely`；
- 「励志 / 逆袭 / 成长」 → `Inspirational/Hopeful`；
- 「轻松 / 摸鱼 / 日常」 → `Chill` / `Happy`；
- 「怒火 / 反抗」 → `Angry/Aggressive` 等。

### 3.2 风格 / 角色 → Genre + Timbre

- 若 `music_style` 包含：
  - 「流行说唱 / emo 说唱」→ `Genre`: `Emo Rap, Pop Rap`；
  - 「国潮 / 国风」→ `Genre`: `Chinese Pop, Chinese Style`；
  - 「民谣」→ `Genre`: `Chinese Folk, Folk Pop`；
- 角色与人设：
  - 「中年」「沧桑」「社畜」→ `timbre`: `Husky,Deep,Smoky`；
  - 「少女」「治愈」→ `timbre`: `Gentle,Soothing,Soft`；
  - 「燃 / 热血少年」→ `timbre`: `Energetic,Powerful,Bright`。

### 3.3 场景 → Scene

根据 `scene`（如「通勤路上」「刷短视频」等），映射到：

- `Vlog/DailyLife`、`Commute`、`Viral short video`、`Outdoor` 等。

## 4. 输出约定

最终由宿主 Agent 写入：

```json
{
  "character": "猪八戒",
  "emotion_theme": "打工人职场疲惫与想回家的念头",
  "music_style": "流行 + 轻说唱",
  "duration_seconds": 70,
  "genre": "Chinese Pop,Emo Rap",
  "mood": "Sentimental/Melancholic/Lonely",
  "vocal_gender": "Male",
  "vocal_persona": "沧桑中年男声",
  "timbre": "Husky,Deep,Gentle",
  "instrument": "Acoustic_Guitar,Drums,Strings",
  "scene": "Vlog/DailyLife"
}
```

脚本仅消费这些字段，不负责推断。


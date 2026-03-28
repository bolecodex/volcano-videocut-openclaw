---
name: GenSong 人物情绪歌
description: >
  基于火山引擎 GenSong：从创意到成品歌曲（歌词、音频、结构化标签），不含 MV 生成。
  所有任务须从 P0_PRECHECK 开始，按阶段汇报进度；配置见 scripts/.env。
version: 1.0.0
trigger: GenSong、人物情绪歌、生成歌曲、作词、配乐素材
---

## 工作流总览

本 Skill 专注于**歌曲生成链路**，从一句模糊想法到「歌词 + 成品音频 + 结构化标签」，不涉及分镜与 MV 生成。

> **所有任务必须从 `P0_PRECHECK` 开始执行。**

整体阶段如下：

```text
[P0_PRECHECK] 环节准备与检测
  ↓
[S1_INTENT] 结构化意图 & 场景
  ↓
[S2_LYRICS] 歌词生成 & 清洗
  ↓
[S3_PARAM_INFER] 演唱者/乐器/音色推断（宿主 Agent）
  ↓
[S4_GENSONG_SUBMIT] GenSong 任务提交
  ↓
[S5_GENSONG_POLL] GenSong 结果轮询 & 下载
  ↓
输出：song.mp3 + lyrics.txt + song_meta.json
```

执行过程中，宿主 Agent 需要**实时向用户汇报当前阶段**，例如：

- 「当前阶段：P0_PRECHECK（环境 & 配置 & 输入检测）」  
- 「当前阶段：S2_LYRICS（歌词生成 & 清洗）」  
- 「当前阶段：S5_GENSONG_POLL（等待歌曲生成结果）」  

---

## P0_PRECHECK：环节准备与检测（必须为第一步）

在进入任何生成逻辑之前，必须先完成以下检查：

- **配置文件检查**
  - `scripts/.env` 文件必须存在且可读。
  - `.env` 中建议配置：
    - `VOLC_ACCESS_KEY_ID`
    - `VOLC_ACCESS_KEY_SECRET`
    - `VOLC_REGION`（可选，默认 `cn-beijing`）
    - `VOLC_SERVICE`（可选，默认 `imagination`）
    - `OUTPUT_ROOT`（可选，用于统一输出根目录）
- **环境依赖检查（使用 uv 安装与运行）**
  - 运行环境已安装 `python 3.10+` 与 `uv`；
  - 所有依赖应通过 `uv` 在 `scripts/pyproject.toml` 所在目录安装，例如：
    ```bash
    # 在 song-production/scripts 目录下
    uv sync
    ```
  - 运行脚本时统一使用：
    ```bash
    uv run python scripts/main.py --mode submit ...
    ```
- **输入检查（由宿主 Agent 完成）**
  - 用户输入至少包含以下信息之一：
    - 角色 / 人设（如「猪八戒」「社畜程序员」等）
    - 情绪/主题（如「打工人 emo」「毕业迷茫」等）
    - 场景（如「通勤路上」「睡前」等）
  - 若缺失重要要素，宿主 Agent 应先与用户澄清或用 LLM 补全，再进入 `S1_INTENT`。
- **输出目录预估**
  - 根据 `OUTPUT_ROOT`（若配置）和一次任务的歌名或随机 ID，规划本次的 `output_dir`：
    - 若设置 `OUTPUT_ROOT`：`OUTPUT_ROOT/music_output/<歌曲名|6位随机数>/`
    - 否则：`music_output/<歌曲名|6位随机数>/`
  - 宿主 Agent 应确保该目录可写。

通过以上检查后，宿主 Agent 需向用户确认当前阶段已完成，例如：

> 当前阶段：P0_PRECHECK 已通过，开始进入 S1_INTENT（结构化意图）。

---

## S1_INTENT：结构化意图 & 场景

### 目标

从用户的一句话或几句话中，提炼成适合火山 GenSong 调用的**结构化音乐描述信息**（角色、人设、情绪、场景、时长等）。

### 典型用户输入

- 「想让猪八戒吐槽打工人生活，偏 emo 一点，1 分钟左右。」
- 「以沙和尚视角写职场老黄牛的无奈，风格偏治愈。」
- 「给社畜程序员写一首 emo 的通勤歌。」

### 建议抽取字段

宿主 Agent 应构造一个结构化 JSON（示例）：

```json
{
  "character": "猪八戒",
  "emotion_theme": "打工人职场疲惫与想回家的念头",
  "music_style": "流行 + 轻说唱",
  "tempo_mood": "中速，主歌偏丧，副歌略带释怀和自嘲",
  "duration_seconds": 70,
  "scene": "下班地铁刷短视频",
  "platform": "Douyin",
  "notes": "强调高老庄、取经路与打工路的类比，把紧箍咒写成生活压力和 KPI。"
}
```

该结构将作为后续歌词创作与参数推断的统一输入。

---

## S2_LYRICS：歌词生成 & 清洗

### 目标

- 基于 `S1_INTENT` 的结构化信息，生成**完整歌词**与一个适合作为 GenSong `Prompt` 的音乐描述。
- 将歌词清洗为整洁的纯文本格式，写入 `lyrics.txt`，便于后续 GenSong 或其它系统直接使用。

### 建议系统提示（供宿主 Agent 调用 LLM 时参考）

可参考原 `music-generate` Skill 中的歌词创作模板，并做轻度泛化（不局限西游）：

> 你是一位擅长用 IP / 历史人物 / 原创人设做情绪歌二创的短视频音乐创作者。  
> 请以【{{character}}】为第一视角，创作一段**{{music_style}}**风格的中文歌词。  
> 要求：
> 1. 角色人设贴合其基础特质，但需加入「当代人情绪」：{{emotion_theme}}。
> 2. 歌词可以融入该题材世界观的专属元素（如地点、道具、称呼等），用场景隐喻现实困境。
> 3. 歌词结构建议包含主歌和副歌（可用 `[Verse 1]`、`[Chorus]` 标注），字数控制在适合 {{duration_seconds}} 秒左右的短视频歌曲长度。
> 4. 语言口语化，适合短视频平台传播，但要保证有 2–3 句具有共鸣感的金句。
> 5. 请先给出一句简短的歌名，然后给出一段简短的「音乐描述 prompt」（供音乐模型使用），最后输出完整歌词。

### 推荐输出格式（用于中间结果）

```markdown
歌名：《{{title}}》

音乐描述 Prompt：
{{enhanced_prompt}}

歌词：
{{lyrics}}
```

其中：

- `enhanced_prompt`：结合人物设定、情绪、风格与关键意象的中/英混合描述。
- `lyrics`：包含 `[Verse]` / `[Chorus]` 等标签的完整歌词。

### 歌词清洗

宿主 Agent 应在生成歌词后进行简单清洗：

- 移除「歌名」「音乐描述 Prompt」等头部信息；
- 如有 `[Verse 1]`、`[Chorus]` 等段落标签，可根据需要选择保留或去掉；
- 将歌词整理为按**行**分隔的中文文本，写入：
  - `output_dir/lyrics.txt`

---

## S3_PARAM_INFER：演唱者 / 乐器 / 音色推断（宿主 Agent）

> **本阶段完全由宿主 Agent 实现，脚本不内置规则。**

### 输入

- `S1_INTENT` 输出的结构化信息；
- `S2_LYRICS` 生成的歌词文本。

### 任务

宿主 Agent 应参考 `reference/performance_inference_rules.md`，推断：

- **演唱者相关：**
  - `vocal_gender`：如 `Male` / `Female`；
  - `vocal_persona`：如「沧桑中年男声」「少年感男声」「治愈系女声」等。
- **情绪与风格：**
  - 将 `emotion_theme` / `tempo_mood` 进一步映射为 `Mood`。
- **乐器/编配：**
  - 根据场景 + 风格选择 2–4 个主要乐器，对应 `Instrument` 可选值。
- **其他：**
  - `Scene`、`Lang`、`Duration` 等补充参数。

最终输出写入：

- `output_dir/song_meta.json`

### `song_meta.json` 字段设计 & GenSong 参数映射

> 字段均为「宿主 Agent 可读/可写」的中间层，调用脚本时再映射到 GenSong 的正式参数。

推荐字段（带约束）如下：

```json
{
  "character": "猪八戒",
  "emotion_theme": "打工人职场疲惫与想回家的念头",
  "music_style": "流行 + 轻说唱",

  "duration_seconds": 70,

  "model_version": "v4.3",

  "genre": "Chinese Pop,Chinese Ballad Pop",

  "mood": "Sorrow/Sad,Sentimental/Melancholic/Lonely",

  "vocal_gender": "Male",

  "timbre": "Husky,Deep,Gentle",

  "instrument": "Acoustic_Guitar,Drums,Strings",

  "scene": "Vlog/DailyLife",

  "lang": "Chinese",

  "vod_format": "wav",

  "skip_copy_check": false
}
```

其中与 GenSong `GenSongV4` 请求体的对应关系为：

- `model_version` → `ModelVersion`
- `genre` → `Genre`
- `mood` → `Mood`
- `vocal_gender` → `Gender`
- `timbre` → `Timbre`
- `duration_seconds` → `Duration`
- `instrument` → `Instrument`
- `scene` → `Scene`
- `lang` → `Lang`
- `vod_format` → `VodFormat`
- `skip_copy_check` → `SkipCopyCheck`

**取值与约束（强烈建议宿主 Agent 严格遵守）：**

- **Genre（`genre`）**
  - 来源：`reference/歌曲生成参数信息.md` 中的「Genre / GenreExtra 可选值」。
  - 规则：**最多 3 个**，用英文逗号`,` 分隔，如：`"Chinese Pop,Chinese Ballad Pop"`。
- **Mood（`mood`）**
  - 来源：同文档中的「Mood 可选值」。
  - 规则：**最多 2 个**，用英文逗号`,` 分隔，如：`"Sorrow/Sad,Sentimental/Melancholic/Lonely"`。
- **Gender（`vocal_gender`）**
  - 可选：`"Male"` / `"Female"`。
- **Timbre（`timbre`）**
  - 来源：文档中的「Timbre 可选值」。
  - 规则：**最多 3 个**，用英文逗号`,` 分隔，如：`"Husky,Deep,Gentle"`。
- **Instrument（`instrument`）**
  - 来源：文档中的「Instrument 可选值」。
  - 规则：**最多 5 个**，用英文逗号`,` 分隔，如：`"Acoustic_Guitar,Drums,Strings"`。
- **Scene（`scene`）**
  - 来源：文档中的「Scene 可选值」，如 `"Vlog/DailyLife"`、`"Commute"` 等。
- **Lang（`lang`）**
  - 人声歌常用：`"Chinese"` / `"English"`。
- **Duration（`duration_seconds`）**
  - 范围：\[30, 240\] 秒。
- **VodFormat（`vod_format`）**
  - 可选：`"wav"` / `"mp3"`。
- **SkipCopyCheck（`skip_copy_check`）**
  - `false` 表示**开启**版权检测（推荐默认）；`true` 表示关闭。

宿主 Agent 在做推断时，可以先在更自由的语义空间中思考，最终落地到 `song_meta.json` 时必须规整到上述枚举与约束范围内。

---

## S4_GENSONG_SUBMIT：创建歌曲生成任务

本阶段由脚本 `scripts/main.py` 负责，宿主 Agent 通过 CLI 调用。

### 调用约定（submit）

在 Skill 根目录（`song-production`）下执行：

```bash
uv run python scripts/main.py \
  --mode submit \
  --lyrics-file /absolute/path/to/output_dir/lyrics.txt \
  --genre "{{song_meta.genre}}" \
  --mood "{{song_meta.mood}}" \
  --gender "{{song_meta.vocal_gender}}" \
  --timbre "{{song_meta.timbre}}" \
  --duration {{song_meta.duration_seconds}} \
  --model-version {{song_meta.model_version}} \
  {{ song_meta.skip_copy_check ? "--skip-copy-check" : "" }}
```

- 具体参数取值应来自 `song_meta.json`（由 `S3_PARAM_INFER` 生成，字段设计见上一节）。
- `scripts/main.py` 会从 `scripts/.env` 读取 `VOLC_ACCESS_KEY_ID` 等配置。

### 环境变量

由 `.env` 提供（详见 P0_PRECHECK）：

- `VOLC_ACCESS_KEY_ID` / `VOLC_ACCESS_KEY_SECRET`
- `VOLC_REGION`（可选）
- `VOLC_SERVICE`（可选）

### 输出

- 标准输出中包含 `TaskID=xxx` 字样，宿主 Agent 需解析并持久化：
  - `output_dir/song_task.json` 中建议记录：

```json
{
  "task_id": "202408308513817850019840",
  "created_at": "2026-03-11T12:00:00+08:00"
}
```

---

## S5_GENSONG_POLL：轮询任务并下载歌曲

### 调用约定（poll）

```bash
uv run python scripts/main.py \
  --mode poll \
  --task-id YOUR_TASK_ID \
  --max-attempts 120 \
  --interval 5
```

脚本内部会调用 `DescribeSongJob` 等接口，返回结果格式可参考：

- `reference/歌曲结果查询任务结果.md`

示例返回：

```json
{
  "Result": {
    "TaskID": "202408308513817850019840",
    "Status": 2,
    "Progress": 100,
    "SongDetail": {
      "AudioUrl": "https://..."
    }
  }
}
```

### 下载与最终产物

- 宿主 Agent 应根据 `AudioUrl` 下载歌曲音频到：
  - `output_dir/song.mp3`
- 推荐使用独立下载脚本（如在 `mv-production` 中的 `download_audio.py`）或宿主环境能力。

### 阶段提示

在轮询过程中，宿主 Agent 需定期向用户报告：

- 当前阶段：S5_GENSONG_POLL
- 已轮询次数 / 预计最长等待时间

成功后，需明确告知：

- 歌曲已生成，并给出 `output_dir` 路径；
- 下一步可交由 `mv-production` Skill 继续生成 MV。

---

## 参考文档

- `reference/歌曲生成参数信息.md`：GenSong 主要参数说明与可选值。
- `reference/歌曲结果查询任务结果.md`：DescribeSongJob/查询结果示例。
- `reference/performance_inference_rules.md`：演唱者 / 乐器 / 音色推断规则（宿主 Agent 实现）。


---
name: MV 智能制作（歌词对齐·Seedance）
description: >
  在已有歌曲与歌词基础上，结合 ASR、文生图/文生视频生成高一致性 MV（首尾帧对齐、可选硬烧字幕）。
  使用 Seedream / Seedance 等；须从环境预检按序执行，保障音视频时长一致。
version: 1.0.0
trigger: MV、音乐视频、歌词对齐、分镜视频、Seedance MV
---

**必须保障音视频时长一致**

## 工作流总览

本 Skill 负责在已有 `song.mp3 + lyrics.txt` 的前提下，完成：

- ASR 识别与歌词对齐；
- 计算前奏与入口点，避免口型错位；
- **从剧本/歌词中提炼角色 / 动物 / 场景 / 道具等资产设定，并与用户确认细节**（头饰、发型、服装、体型、毛色、场景布局等）；
- 分镜设计与时间轴分配（由宿主 Agent 完成），并严格遵守资产一致性和出入场/动作连贯性约束；
- 调用 Seedream 5.0 结合剧本与分镜生成整支 MV 的首帧图（first_frame.png），再调用 Seedance 1.5 Pro 生成分镜视频；
- 拼接生成最终 MV，并支持本地硬编码字幕或通过 VOD 烧录字幕。

> **所有任务必须从 Step 1（环境预检）开始执行，并严格按编号顺序推进，禁止跳步。**

### 流程控制规则（全局约束）

宿主 Agent 在编排本 Skill 时，必须遵守以下**流程控制规则**，作为全局约束：

1. **严格按步骤顺序执行，禁止跳步**  
   必须按 Step 1 → Step 2 → … → Step 10 的顺序执行，不得跳过、颠倒或并行执行不同步骤的主流程。

2. **环境预检是最高优先级，必须首先执行**  
   Step 1（P0_PRECHECK）必须在任何其他步骤之前执行；未通过 Step 1 不得进入 Step 2。

3. **任一步骤失败立即停止，报告错误**  
   任一步骤执行失败时，必须立即停止后续步骤，并向用户或调用方报告错误信息，不得在失败状态下继续执行后续步骤。

4. **每步完成后输出检查点状态**  
   每步成功完成后，必须输出当前步骤的检查点状态（例如「Step N 已完成，产物 xxx 已就绪」），便于监控与从断点恢复。

### 执行约束（必须遵守）

宿主 Agent 在编排本 Skill 时，除上述流程控制规则外，还须遵守以下硬性约束：

- **阶段顺序不可更改**
  - 主链路必须严格按如下顺序执行，不得任意跳过或交换阶段：
    - `P0_PRECHECK → M0_AV_SEPARATION → M1_ASR → M2_LYRICS_ALIGN → M3_INTRO_OFFSET → M5_STORYBOARD → M4_IMAGE_REFERENCES → M6_SHOT_VIDEOS → M7_MV_COMPOSE → M8_SUBTITLE_BURN`
  - 说明：**先分镜（M5）再参考图（M4）**，参考图（角色三视图、场景图、道具图）须**基于分镜**中的 scene/props/character 生成。
- **参考图与首帧不得混淆**
  - 用户放入 `ref_images/` 的图为**参考图**（用于风格/生图参考），**不得**默认作为视频生成的「首帧」(first_frame)。
  - 视频接口的 `first_frame_image_url` 仅允许来自：**上一镜的尾帧**（由脚本自动衔接），或分镜中**显式指定**的某图作为该镜头首帧。不得将 `ref_images/` 下路径自动写入分镜的 `first_frame_image_url`，除非用户或分镜明确指定该图即为该镜头的首帧。
- **关键依赖不能缺失**
  - 未完成前一阶段的必需产物时，禁止进入下一阶段，例如：
    - 未生成 `voice.mp3`（且未记录异常降级）不得直接进入 `M1_ASR`；
    - 未生成 `asr_corrected.json` 不得进入 `M3_INTRO_OFFSET` / `M5_STORYBOARD`；
    - 未生成带 `video_path` 的 `storyboard_updated.json` 不得进入 `M7_MV_COMPOSE`。
- **禁止绕过纠错与对齐**
  - 字幕相关流程必须走完「`M1_ASR` → `M2_LYRICS_ALIGN` → 全局对齐修正 → 生成 `lyrics_aligned.srt`」；
  - 不得直接使用原始 ASR 文本生成字幕，更不得跳过歌词对齐与全局时间修正步骤。
- **显式状态与日志**
  - 推荐在实现中维护显式 `stage` 状态机：只有当前阶段成功完成且产物有效时，才允许迁移到下一阶段；
  - 日志与对用户的反馈中必须清晰标注当前阶段（如「当前阶段：M3_INTRO_OFFSET」），便于排查是否存在越级或漏执行。
- **从某阶段重新开始时必须清理后续产物**
  - 若用户明确要求从某一阶段重新开始（例如「从 ASR 阶段重新来」「从分镜开始重做」），宿主 Agent **必须先删除该阶段及其之后所有阶段在 `output_dir` 中已产生的文件**，再从该阶段起严格按流程重新执行。
  - 各阶段主要产物（便于按阶段清理）：
    - M0：`voice.mp3`、`background.mp3`、`.demucs_output/`
    - M1：`asr_raw.json`、`song_base64.txt`（若有）
    - M2：`asr_corrected.json`、`lyrics_aligned.srt`（若有）
    - M3：`timing_meta.json`
    - M4：`ref_images/`、`character_views/`、`key_scenes/`
    - M5：`storyboard.json`
    - M6：`storyboard_updated.json`、`*_last.png`、各 `shot_*.mp4`
    - M7：`mv.mp4`、`temp_video_silent.mp4`、`shots.txt`
    - M8：VOD 侧任务与烧录结果（若在本地有缓存也需一并清理）
  - 例如：用户说「从 ASR 重新开始」→ 删除 M1 及之后所列产物（从 `asr_raw.json` 到 M8），保留 M0 产物（`voice.mp3` 等），然后从 M1_ASR 开始执行。

### 显式编号步骤 + 前置依赖声明

以下步骤均带有明确的前置条件与依赖规则，**只有上一步骤全部通过后，才可进入下一步骤**；每步完成后须输出检查点状态。

| 步骤        | 阶段标识            | 前置条件    | 子任务摘要                                                                                                                                                                                                                                               | 依赖规则                                   |
| ----------- | ------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Step 1**  | P0_PRECHECK         | 无          | 检测 Python ≥3.10、uv、`.env` 配置；检测 `song.mp3`、`lyrics.txt` 存在；检测 `output_dir` 可写；可选：ASR/视频服务健康检查                                                                                                                               | **只有 Step 1 全部通过后，才进入 Step 2**  |
| **Step 2**  | M0_AV_SEPARATION    | Step 1 通过 | 对人声/背景音分离：运行 `av_separation.py`，得到 `voice.mp3`、`background.mp3`                                                                                                                                                                           | **只有 Step 2 全部通过后，才进入 Step 3**  |
| **Step 3**  | M1_ASR              | Step 2 通过 | 以 `voice.mp3` 调用 ASR，得到 `asr_raw.json`                                                                                                                                                                                                             | **只有 Step 3 全部通过后，才进入 Step 4**  |
| **Step 4**  | M2_LYRICS_ALIGN     | Step 3 通过 | 宿主 Agent 按 ASR 规则逐句逐字纠错，输出 `asr_corrected.json`、`lyrics_aligned.srt`                                                                                                                                                                      | **只有 Step 4 全部通过后，才进入 Step 5**  |
| **Step 5**  | M3_INTRO_OFFSET     | Step 4 通过 | 宿主 Agent 计算前奏与首句入口，输出 `timing_meta.json`                                                                                                                                                                                                   | **只有 Step 5 全部通过后，才进入 Step 6**  |
| **Step 6**  | M5_STORYBOARD       | Step 5 通过 | 宿主 Agent 生成分镜，输出 `storyboard.json`（含 scene/props/character 定义与描述，并在每个分镜的 image_description 中注入已确认的资产细节，如人物头饰/发型/服装、动物体型/毛色、场景结构/灯光等；依赖 asr_corrected、timing_meta、lyrics，不依赖参考图） | **只有 Step 6 全部通过后，才进入 Step 7**  |
| **Step 7**  | M4_IMAGE_REFERENCES | Step 6 通过 | 基于**整首歌词 / 剧本与分镜草案**设计首帧构图草案（人物/场景/道具/光线等），先与用户确认细节后，再调用 Seedream 5.0 生成首帧图 `first_frame.png`                                                                                                         | **只有 Step 7 全部通过后，才进入 Step 8**  |
| **Step 8**  | M6_SHOT_VIDEOS      | Step 7 通过 | 串行调用视频生成，每镜尾帧作为下一镜首帧，输出 `storyboard_updated.json` 及各镜头视频                                                                                                                                                                    | **只有 Step 8 全部通过后，才进入 Step 9**  |
| **Step 9**  | M7_MV_COMPOSE       | Step 8 通过 | 拼接分镜视频与歌曲音频，可选硬编码字幕，输出 `mv.mp4`                                                                                                                                                                                                    | **只有 Step 9 全部通过后，才进入 Step 10** |
| **Step 10** | M8_SUBTITLE_BURN    | Step 9 通过 | 生成时间轴字幕并调用 VOD 烧录（或仅上传带字版视频）                                                                                                                                                                                                      | 流程结束；可输出最终播放链接或 vid         |

**整体阶段如下：**（注意：参考图在分镜之后生成，基于分镜中的 scene/props/character）

```text
[P0_PRECHECK] 环境 & 依赖 & 输入检测
  ↓
[M0_AV_SEPARATION] 人声 / 背景音分离（必须在 ASR 之前执行）
  ↓
[M1_ASR] 基于人声音轨调用 ASR 获取原始字幕（asr_raw.json）
  ↓
[M2_LYRICS_ALIGN] 基于歌词与语义纠错 ASR 结果（仅宿主 Agent，禁止脚本实现）
  ↓
[M3_INTRO_OFFSET] 计算前奏 & 歌词入口点（宿主 Agent）
  ↓
[M5_STORYBOARD] 分镜生成与歌词扩写（宿主 Agent）→ 产出 storyboard.json（含 scene/props/character）
  ↓
[M4_IMAGE_REFERENCES] 基于分镜生成首帧图
  ↓
[M6_SHOT_VIDEOS] 调用视频生成（首尾帧 & 风格一致性）
  ↓
[M7_MV_COMPOSE] 镜头拼接 + 音视频对齐输出 mv.mp4（可选本地硬编码字幕压制：基于 lyrics_aligned.srt 直接烧入视频，推荐使用 `scripts/video_mv_generate.py` 实现）
  ↓
[M8_SUBTITLE_BURN] 生成时间轴字幕（lyrics_aligned.srt），可继续使用 `scripts/video_mv_generate.py` 输出带字版文件，或调用 VOD 进行线上字幕烧录 / 覆盖式压制
```

执行过程中，宿主 Agent 需要**每步完成后输出检查点状态**并实时向用户汇报当前阶段，例如：

- 「Step 1 已完成：P0_PRECHECK 通过，环境与输入就绪」
- 「Step 3 已完成：M1_ASR 通过，asr_raw.json 已生成」
- 「Step 8 进行中：M6_SHOT_VIDEOS，分镜视频生成中（已完成 8/20 个镜头）」

任一步骤失败时，须**立即停止**并明确报告错误，不得继续执行后续步骤。

---

## P0_PRECHECK：环境 & 依赖 & 输入检测（必须为第一步）

在进入 ASR 或视频生成前，必须先完成以下检查：

- **配置文件检查**
  - `scripts/.env` 文件必须存在且可读。
  - `.env` 中建议配置：
    - `DOUBAO_SPEECH_API_KEY`：大模型 ASR 访问密钥；
    - `VIDEO_API_URL`、`ARK_API_KEY`、`VIDEO_MODEL`：视频生成服务（如 Seedance）的访问配置；
    - `OUTPUT_ROOT`：统一输出根目录；
    - `VIDEO_DEFAULT_RESOLUTION`（如 `720p`）、`VIDEO_DEFAULT_RATIO`（如 `16:9`）；
    - `VIDEO_STYLE_SEED`：全局风格 seed（用于画面一致性）；
    - `VIDEO_MODE`：`text_only` / `first_frame` / `first_and_last`。

- **环境 / 依赖安装（使用 uv）**
  - 运行环境已安装 `python 3.10+` 与 `uv`；
  - 所有依赖应通过 `uv` 在 `scripts/pyproject.toml` 所在目录安装，例如：
    ```bash
    # 在 mv-production/scripts 目录下
    uv sync
    ```
  - 运行本 Skill 中的所有脚本时统一使用 `uv run`，例如：
    ```bash
    uv --project scripts run python av_separation.py ...
    uv --project scripts run python video_shot_generate.py ...
    uv --project scripts run python video_mv_generate.py ...
    ```

- **环境 / 外部服务初步检查**
  - 宿主 Agent 建议在首次调用前做一次轻量「健康检查」，例如：
    - 用一个短样本音频调用 ASR，确认服务可达；
    - 调用一次 Seedream / Seedance 接口确认网络连通与鉴权正常；

- **输入文件检测**
  - 当前任务必须具备：
    - `output_dir/song.mp3`：成品歌曲音频（或可下载 URL，需先下载到本地）；
    - `output_dir/lyrics.txt`：按 ASR 规范清洗后的纯歌词文本（详见 `reference/ASR_字幕生成规则.md`）。
  - 若缺少上述任一文件，应提示用户先在 `song-production` 完成歌曲生成，或自行提供音频与歌词。

- **输出目录准备**
  - 若配置了 `OUTPUT_ROOT`，本次任务的 `output_dir` 应为：
    - `OUTPUT_ROOT/music_output/<歌曲名|6位随机数>/`
  - 否则使用相对路径：
    - `music_output/<歌曲名|6位随机数>/`
  - 宿主 Agent 需确保该目录存在且可写。

通过检查后，宿主 Agent 应向用户说明：

> 当前阶段：P0_PRECHECK 已通过，开始进入 M0_AV_SEPARATION（人声 / 背景音分离），随后进入 M1_ASR（基于人声音轨获取原始字幕）。

---

## M0_AV_SEPARATION：人声 / 背景音分离（**必须在 ASR 之前执行**）

在调用 ASR 前，**必须先对整首歌做一次人声 / 背景音分离**，提取出更干净的「人声轨道」供 ASR 使用，可以显著减轻伴奏和环境声的干扰。

### 输入

- `output_dir/song.mp3`：原始歌曲音频。

### 脚本

本 Skill 在 `scripts/` 提供：

- `scripts/av_separation.py`：基于 Demucs 模型将输入音频拆分为：
  - `voice.mp3`：人声；
  - `background.mp3`：背景音。

在 `mv-production` 根目录下，典型调用示例为：

```bash
uv --project scripts run python av_separation.py \
  output_dir/song.mp3 \
  --output-dir output_dir
```

成功后，`output_dir` 中将新增：

- `voice.mp3`
- `background.mp3`

后续 ASR 步骤**必须**使用 `voice.mp3` 作为输入；仅当分离阶段异常失败（如文件缺失/损坏）时，才允许回退继续使用原始 `song.mp3`，并需在日志中明确记录该降级行为。

---

## M1_ASR：基于人声音轨调用 ASR 获取原始字幕（asr_raw.json）

本阶段使用 `scripts/audio_base64.py` 与 `scripts/volcengine_transcribe.py`，将**人声音轨**转为 base64 并提交给火山引擎大模型 ASR 服务。

### 步骤

1. **音频转 base64（严格优先使用人声音轨）**

- 正常流程：**始终使用 `output_dir/voice.mp3`** 作为 ASR 输入；
- 仅当 `voice.mp3` 不存在或明显异常（如 0 字节）时，才退回使用 `output_dir/song.mp3`，并在日志中明确记录已发生降级。

调用示例（假设使用人声音轨）：

```bash
uv --project scripts run python audio_base64.py \
  output_dir/voice.mp3 \
  -o output_dir/song_base64.txt
```

输出：`output_dir/song_base64.txt`，内容为 `data:audio/...;base64,xxxxx`。

2. **提交 ASR 任务并轮询**

```bash
uv --project scripts run python volcengine_transcribe.py \
  -f output_dir/song_base64.txt \
  -o output_dir/asr_raw.json
```

- `volcengine_transcribe.py` 会：
  - 从 `scripts/.env` 读取 `DOUBAO_SPEECH_API_KEY`；
  - 向大模型录音识别接口提交任务并轮询结果；
  - 在 `output_dir/asr_raw.json` 中写入完整返回，包含 `utterances` 等字段。

原始 ASR 结果结构与字段说明，可参考：

- 根目录下的 `asr使用文档.md`
- `reference/ASR_字幕生成规则.md`

---

## M2_LYRICS_ALIGN：基于歌词纠错 ASR 结果（宿主 Agent）

> **本阶段完全由宿主 Agent 实现，脚本不内置纠错逻辑。**  
> **每一句都必须按 `reference/ASR_字幕生成规则.md` 完整执行**：先逐句对齐、再逐字精修，行级 `start_time_ms`/`end_time_ms` 严格取自该行 words 的最小/最大时间，再做全局禁止重叠校正；输出前必须对每一行通过「每行校验清单」，不得对部分行简化或跳过规范。

### 输入

- `output_dir/asr_raw.json`：M1 输出的原始 ASR JSON，含 `utterances`/`words`；
- `output_dir/lyrics.txt`：已清洗的纯歌词文本。

### 目标

宿主 Agent 需按照 `reference/ASR_对齐与纠错流程.md` 与 `reference/ASR_字幕生成规则.md`：

- 对比每行歌词与 ASR 中的 `words.text` 序列；
- 允许少量识别错误（口误/错字），以歌词为权威文本；
- 在不改变整体节奏的前提下，将 ASR 结果「纠错」为歌词版本：
  - 为每一行歌词分配精确的 `start_time` / `end_time`；
  - 记录原始 ASR 文本，便于调试。

### 输出

宿主 Agent 应在 `output_dir` 写入：

- `asr_corrected.json`，建议结构示例：

```json
{
  "lines": [
    {
      "index": 0,
      "lyric": "当年灌江口，我曾是无名少年郎",
      "start_time_ms": 76580,
      "end_time_ms": 80380,
      "raw_text": "当年灌江口，我曾是无名少年郎",
      "words": [
        {
          "text": "当",
          "start_time_ms": 76580,
          "end_time_ms": 76700
        }
      ]
    }
  ]
}
```

该文件将作为后续前奏判定、分镜时间轴与字幕生成的统一时间基准。

---

## M3_INTRO_OFFSET：计算前奏 & 歌词入口点（宿主 Agent）

### 目标

- 根据 `asr_corrected.json` 中**第一句实际歌词**的 `start_time_ms`，计算前奏时长；
- 确定带人口型的画面应从何时开始，避免前奏阶段出现张口却无声的画面。

### 建议策略

- 找到 `lines` 数组中第一条含非空 `lyric` 的记录，其 `start_time_ms` 记为 `t_lyric_start`；
- 前奏时长 `intro_ms = t_lyric_start`，可根据项目规则限制最大前奏长度（如若过长，可在分镜中拆出多个 intro 镜头）。

宿主 Agent 应将结果写入：

- `output_dir/timing_meta.json`，例如：

```json
{
  "intro_ms": 5000,
  "first_lyric_index": 0
}
```

在后续分镜与视频生成阶段，**所有有口型的镜头起始时间不得早于 `intro_ms`**。

---

## M5_STORYBOARD：分镜生成与歌词扩写（宿主 Agent）

> **分镜由宿主 Agent 完成，本 Skill 仅规定结构与约束。** 分镜在参考图之前生成，产出含 scene/props/character 定义的 storyboard，供 M4 据此生成参考图。

### 输入

- 歌词：`output_dir/lyrics.txt`
- 纠错后 ASR：`output_dir/asr_corrected.json`
- 前奏信息：`output_dir/timing_meta.json`
- 本阶段**不依赖**角色与场景参考图（参考图在 M4 中基于本阶段产出的分镜再生成）。

### 指导文档

宿主 Agent 应参考：

- `reference/storyboard_prompt_spec.md`（由原 `STORYBOARD_PROMPT` 提炼）；
- `reference/lyrics_to_storyboard_expansion.md`（歌词驱动的分镜扩写规则）。

核心要求包括：

- 分镜按时间顺序覆盖整首歌，尽量保证每个镜头 2–6 秒；
- 分镜中须包含**角色、场景、道具**的定义与描述（id、description 等），并在每个分镜的 `image_description` 中**显式写入已确认的资产细节**（如人物头饰/发型/衣服/鞋子、动物体型/特征/毛色、场景结构/灯光等，若该分镜涉及这些元素），以便后续首帧与视频生成保持全局一致；
- 对 intro 段（`intro_ms` 之前）：
  - 画面以氛围 / 场景 / 道具为主，不安排明显口型；
- 对歌词段：
  - 每段分镜的时间范围必须落在对应歌词行的时间窗附近；
  - `dialogue` 字段内容须严格等于该时间窗内的歌词行或其子集；
  - `image_description` 和 `video_description` 可以对歌词做适度「故事化扩写」，但不得改变歌词真实时间。

最终分镜 JSON 应写入：

- `output_dir/storyboard.json`

### reference_assets.json：资产设定表（**必须与分镜完全一致且覆盖所有登场元素**）

在进入 M4/M6 之前，宿主 Agent **必须为本次任务写入/更新**：

- `output_dir/reference_assets.json`

该文件用于为整个 MV 提供**统一且精细的资产设定**，供首帧生成与视频生成阶段注入到 prompt 中，必须满足：

- **覆盖所有在分镜中出现的人物 / 动物 / 场景 / 道具**，不得遗漏（例如本例中的：小女孩、草莓熊、小熊猫、小狗、小鸡、小鸭、奶牛、猪、马等）；
- 每个资产都要有**清晰、可文生图/视频的 description**，包括：
  - 人物：年龄、性别、发型、头饰、衣服、鞋子、表情、风格（如「迪士尼风格动画」）；
  - 动物：体型、体态特征、毛色、表情、风格；
  - 场景：结构元素（谷仓、栅栏、池塘、牧场等）、光线、色调、风格；
  - 道具：颜色、材质、大小、用途及风格。

推荐结构示例：

```json
{
  "first_frame": { "description": "..." },
  "characters": [
    {
      "id": "character_girl",
      "description": "5-6岁的中国小女孩，黑色短发，身穿粉色可爱小裙子，白色袜子，粉色鞋子，面带甜美笑容，迪士尼风格动画，高清细节"
    },
    {
      "id": "character_strawberry_bear",
      "description": "粉色草莓熊玩偶，圆润身材，柔软绒毛，草莓图案肚皮，大眼睛，微笑表情，迪士尼风格动画"
    },
    {
      "id": "character_red_panda",
      "description": "红色小熊猫，圆滚滚身体，大尾巴带有浅色环纹，黑色眼罩，表情活泼可爱，迪士尼风格"
    },
    {
      "id": "character_dog",
      "description": "棕白相间的小狗，耷拉耳朵，大眼睛，活泼好动，迪士尼风格"
    }
  ],
  "scenes": [
    {
      "id": "scene_farm",
      "description": "阳光明媚的农场，红色谷仓，绿色草地，蓝天，白色栅栏，绿树环绕，乡村风格，温馨明亮，迪士尼风格"
    }
  ],
  "props": [
    {
      "id": "prop_chicks",
      "description": "黄色毛茸茸的小鸡，可爱卡通风格，迪士尼风格"
    },
    {
      "id": "prop_barn",
      "description": "红色木制谷仓，经典农场风格，白色窗框和门，迪士尼风格"
    }
  ]
}
```

> **硬性要求**：`reference_assets.json` 与 `storyboard.json` 中的 `characters` / `scene` / `props` ID 必须一一对应；若分镜中新引入了角色或道具，对应的资产描述也必须同步补充到 `reference_assets.json`，否则视为流程未完成，不得进入 M4/M6。

---

## M4_IMAGE_REFERENCES：基于分镜生成首帧图（first_frame.png）

> **当前版本仅需生成首帧图，不再生成角色三视图 / 场景图 / 道具图。**

本阶段在 **M5 分镜完成后** 执行，结合剧本与分镜的全局信息，使用 Doubao Seedream 5.0 **只生成一个首帧图** `first_frame.png`，供首个视频分镜作为首帧画面（`first_frame_image_url`）使用。

### 输入

- 分镜：`output_dir/storyboard.json`（用于理解整支 MV 的时间结构与主要场景/镜头氛围）；
- 歌词与 `song_meta.json`（若有），用于把控整体情绪与故事走向；
- 用户可选提供的参考图：
  - 用户参考图仅作风格/构图参考，可作为 Seedream 的 `image` 输入；
  - 不得默认当作视频首帧，只有在用户确认后，才以此为基准生成 `first_frame.png`。

### 首帧图设计与用户确认（强制）

在调用首帧生成脚本前，宿主 Agent 必须：

1. **通读整首歌词 / 剧本与分镜草案**，提炼：
   - 主角的最终视觉设定（人物外观、头饰、服装等，见前文「资产设定与全局一致性约束」）；
   - 主场景（如录音棚）的空间特征与灯光氛围；
   - 整支 MV 想要传达的核心情绪与基调。
2. 基于上述信息，给出**首帧构图草案**，至少包含：
   - 画面中出现的人物/动物及其位置、姿态、表情；
   - 所在场景与关键道具（如麦克风、音箱、调音台）的摆放；
   - 景别、构图方式与光线色调（如「近景，三分法构图，暖琥珀色顶光+侧光」）。
3. 将该草案以自然语言形式展示给用户，请用户确认 / 调整，只有在用户确认后，才进入首帧生成。

### 生成方式（仅首帧图）

确认好首帧设定后，宿主 Agent 调用本 Skill 提供的脚本 `scripts/generate_reference_image.py`，**只使用 `first_frame` 模式**：

```bash
uv --project scripts run python generate_reference_image.py \
  --config output_dir/reference_assets.json \   # 包含 first_frame/character/scenes 等设定，可由宿主写入
  --output-dir output_dir \
  --mode first_frame \
  [--reference-image output_dir/ref_images/用户参考图或本地路径]
```

说明：

- `reference_assets.json` 中的 `first_frame` 字段（或角色 + 首场景组合）用于提供首帧专用提示词；
- `--reference-image` 可选，用于将用户图片作为 Seedream 5.0 的 `image` 参考，实现文图结合；不传则为纯文生图；
- 脚本会在 `output_dir/first_frame.png` 写出首帧图。

### 与分镜 / 视频生成的衔接

- 首个分镜（通常为 `shot_001`）应在 `storyboard.json` 中显式引用首帧图，例如：

  ```json
  {
    "shot_id": "shot_001",
    "scene": "scene_studio",
    "characters": ["character_001"],
    "first_frame_image_url": "first_frame.png",
    ...
  }
  ```

- 在 `M6_SHOT_VIDEOS` 中：
  - 若首个分镜显式设置了 `first_frame_image_url`，则视频生成脚本会将 `first_frame.png` 作为该镜头的首帧图传入；
  - 后续镜头则延续脚本内部的「上一镜尾帧 → 下一镜首帧」衔接逻辑，不再额外生成其它参考图。

---

## M6_SHOT_VIDEOS：调用视频生成（首尾帧 & 风格一致性）

本阶段通过 Seedance 文生视频/图生视频接口，为每个分镜生成对应视频片段。接口字段与限制详见 `reference/视频生成接口文档.md`。

### 首尾帧与模式

- **首帧来源**：每个镜头的 `first_frame_image_url` 仅允许来自（1）**上一镜的尾帧**（由脚本自动衔接），或（2）分镜中**显式指定**的该镜头首帧图。用户放在 `ref_images/` 的参考图**不得**默认作为首帧传入；仅当分镜中显式将该图设为该镜的 `first_frame_image_url` 时才使用。
- 根据 `storyboard.json` 选定：
  - 开场镜头 `shot_01`；
  - 收束镜头 `shot_last`。
- 根据 `.env` 中的 `VIDEO_MODE` 决定生成策略：
  - `text_only`：仅使用文本提示词（content 中只有 `type=text`）；
  - `first_frame`：为整条 MV 预先生成一个首帧图片，并在每个镜头的请求中附带：
    - `content`: `[{"type": "image_url", "image_url": {"url": "<first_frame_url>"}, "role": "first_frame"}, {"type": "text", "text": "<该镜头的 video_description>"}]`
  - `first_and_last`：为首尾镜头分别生成首帧/尾帧图片，在关键镜头请求中使用：
    - `role="first_frame"` 和 `role="last_frame"` 的两张图片，配合文本提示词。

在所有请求中，建议统一：

- `model`: 来自 `.env` 中的 `VIDEO_MODEL`（如 `doubao-seedance-1-5-pro-251215`）；
- `resolution`: 使用 `VIDEO_DEFAULT_RESOLUTION`（如 `720p`）；
- `ratio`: 使用 `VIDEO_DEFAULT_RATIO`（如 `16:9`）；
- `duration`: 与该镜头 `duration` 字段对齐，必要时四舍五入到 Seedance 支持的整数秒；
- `seed`: 使用 `VIDEO_STYLE_SEED`，保证画面风格一致；
- `generate_audio`: 统一设为 `false`，音频只来自最终合成的歌曲；
- `draft`: 可选，默认 `false`。

### 推荐实现：使用本 Skill 的 `scripts/video_shot_generate.py`

本 Skill 在 `scripts/` 目录下内置脚本：

- `scripts/video_shot_generate.py`：根据分镜 JSON 调用 Seedance 生成每个镜头视频，支持：
  - **严格按分镜顺序串行生成**（不并行），保证上下文以及首尾对齐可控；
  - 自检与自动补齐缺失的 `visual_prompt`；
  - 断点续跑（`--skip-existing`）；
  - 生成自检报告和修复版分镜 JSON；
  - **自动加载 `reference_assets.json` 并将其中的人物 / 场景 / 道具精细描述与分镜自身字段组合成一个长 prompt 传给视频模型**。

关键参数如下（详见脚本内 docstring）：

- `--storyboard`：输入分镜 JSON 路径（数组）；
- `--output-dir` / `--song-name`：决定输出目录，内部调用 `resolve_output_dir`，默认使用 `music_output/<歌曲名|随机数>/`；
- `--api-url` / `--api-key`：可覆盖默认的 Ark 接口地址与鉴权 key，默认从 `scripts/.env` 中读取 `VIDEO_API_URL` / `ARK_API_KEY`；
- `--out-storyboard`：最终写回的带 `video_path` 字段的分镜 JSON（默认 `output_dir/storyboard_updated.json`）。
  （当前实现中 `--workers` 参数仅保留向后兼容，不再用于并行控制，所有分镜按顺序串行生成。）

**资产注入与单一 prompt 规则（必须执行）：**

- 在调用 Seedance 生成每个镜头时，脚本会为该分镜构造一个**融合后的唯一文本 prompt**，具体为：
  - 依次拼接分镜中的 `visual_prompt`、`prompt`、`video_description`（存在则全部追加，而不是三选一）；
  - 再追加该分镜的 `image_description`（前缀为「静态画面描述：...」）；
  - 再根据 `characters` / `scene` / `props` 字段，从 `reference_assets.json` 中按 `id` 取出对应的 `description`，整理为：
    - `角色设定：character_girl: ...； character_strawberry_bear: ...； ...`
    - `场景设定：scene_farm: ...`
    - `道具设定：prop_chicks: ...； prop_barn: ...`
- 上述所有内容会**顺序拼接成一个长的 `visual_prompt` 字符串**，作为该镜头请求中 `content` 里的 `type="text"` 部分传给 Seedance。
- 若分镜中引用了某个角色/场景/道具 ID，但 `reference_assets.json` 中没有对应 `description`，脚本会退回使用 ID 本身拼 prompt，但这被视为资产不完整，宿主 Agent 应在自检阶段阻止继续执行并提示用户补全资产表。

此外，为了让**相邻镜头之间的画面“首尾对齐”**，脚本内部还会做一层自动处理：

- 脚本以**串行方式**依次生成每个分镜视频；
- 每个分镜 `i` 生成完成后，会通过 ffmpeg 从 `video_path` 中提取**最后一帧图片**；
- 若分镜 `i+1` 未显式设置 `first_frame_*` 字段，则在调用 Seedance 生成该分镜时，自动将分镜 `i` 的最后一帧图片作为 `first_frame_image_url` 传入；
- 已显式设置 `first_frame_*` 的分镜不会被覆盖，上游仍可在需要时手动指定特殊首帧。

在本 Skill 根目录（`mv-production/`）下，典型调用示例为：

```bash
uv --project scripts run python video_shot_generate.py \
  --storyboard output_dir/storyboard.json \
  --song-name "我的歌"
```

脚本会：

- 使用 `scripts/.env` 中的 `VIDEO_API_URL` / `ARK_API_KEY` 与 Seedance 通信（接口格式见 `reference/视频生成接口文档.md`）；
- 为每个分镜生成视频并下载到 `output_dir`；
- 在 `output_dir/storyboard_updated.json` 中写入包含 `video_path` 的分镜数组。

### 输出与进度汇报

- 每个镜头生成成功后，`storyboard_updated.json` 中对应对象将带有 `video_path` 字段；
- 所有镜头生成完成后，方可进入 `M7_MV_COMPOSE`。

在长耗时阶段，宿主 Agent 需定期向用户报告：

- 当前阶段：M6_SHOT_VIDEOS；
- 已完成镜头数量 / 总镜头数。

---

## M7_MV_COMPOSE：镜头拼接 + 音视频对齐（可选本地硬编码字幕）

本阶段负责将所有分镜视频按顺序拼接，并与 `song.mp3` 对齐生成 `mv.mp4`，同时支持在本地直接基于 SRT 进行**硬编码字幕**（简单场景可不再依赖 VOD 烧录）。

### 方式一：本地拼接（参考 `scripts/video_mv_generate.py` 行为）

本 Skill 在 `scripts/` 目录提供脚本：

- `scripts/video_mv_generate.py`：基于带 `video_path` 的分镜 JSON 与歌曲音频，完成：
  - 静音拼接所有镜头（按照分镜顺序生成 `shots.txt` 并 concat）；
  - 探测歌曲音频时长并以此为最终视频时长；
  - 将静音视频与歌曲音频合成为最终 MV；
  - 若提供 SRT 字幕文件，则在本地通过 ffmpeg 的 `subtitles` 滤镜进行**硬编码字幕**。

关键参数：

- `--storyboard`：带 `video_path` 字段的分镜 JSON（建议使用 `output_dir/storyboard_updated.json`）；
- `--song-audio`：歌曲音频路径（例如 `output_dir/song.mp3`）；
- `--output`：最终 MV 输出路径（例如 `output_dir/mv.mp4`）；
- `--subtitle`：可选，SRT 字幕文件路径（例如 `output_dir/lyrics_aligned.srt`），若提供则在本地进行硬编码字幕；
- `--work-dir` / `--song-name`：工作目录，未指定时内部同样通过 `resolve_output_dir` 生成 `music_output/<歌曲名|随机数>/`。

在本 Skill 根目录（`mv-production/`）下，典型调用示例为：

```bash
uv --project scripts run python video_mv_generate.py \
  --storyboard output_dir/storyboard_updated.json \
  --song-audio output_dir/song.mp3 \
  --output output_dir/mv.mp4 \
  --subtitle output_dir/lyrics_aligned.srt \
  --song-name "我的歌"
```

输出：

- `output_dir/mv.mp4`

> 说明：当通过 `--subtitle` 已在本地完成硬编码字幕时，`M8_SUBTITLE_BURN` 可以仅用于分发到 VOD 平台（如上传带字版视频），也可以跳过字幕烧录步骤。

---

## M8_SUBTITLE_BURN：生成时间轴字幕并调用 VOD 烧录

### 步骤 1：生成 SRT（宿主 Agent 或工具脚本）

基于 `asr_corrected.json`：

- 将每行歌词的 `start_time_ms` / `end_time_ms` 转为 `hh:mm:ss,ms` 格式；
- 生成 `output_dir/lyrics_aligned.srt`；
- 具体规则详见：
  - `reference/ASR_字幕生成规则.md`
  - `reference/ASR_时间轴与字幕格式规范.md`。

### 步骤 2：调用 VOD 烧录字幕

结合 `mcp_service_vod` 中的：

- `video_batch_upload` / `get_play_url` / `add_subtitle` / `get_v_creative_task_result`；
- 典型流程：
  1. 将 `mv.mp4` 上传到 VOD；
  2. 将 `lyrics_aligned.srt` 上传到 VOD；
  3. 调用 `add_subtitle`：
     - `subtitle_url` 指向 SRT 文件；
     - 配置字体、字号、描边、位置等；
  4. 轮询 `get_v_creative_task_result` 直至成功，得到最终带字视频的播放地址或 vid。

宿主 Agent 在此阶段应向用户说明：

- 是否已完成字幕烧录；
  +- 是否提供 VOD 播放链接或 vid。

---

## 参考文档

- `reference/ASR_字幕生成规则.md`：ASR 输出结构与歌词对齐规则。
- `reference/参考图生成规则.md`：角色三视图、场景图、道具图生成规则及与剧本一致性约定；`scripts/generate_reference_image.py` 的配置格式与调用方式。
- `reference/image_generation_seedream.md`：Doubao Seedream 文生图 & 组图参数说明与本 Skill 推荐用法。
- `reference/视频生成接口文档.md`：Seedance 视频生成接口与首尾帧参数说明。
- `reference/lyrics_to_storyboard_expansion.md`：基于歌词进行分镜扩写的建议。
- `reference/视频生成一致性规范.md`：角色三视图、核心场景图及风格一致性约定。
- `mcp_service_vod/SKILL.md`：VOD 相关工具的能力索引与字幕烧录推荐用法。

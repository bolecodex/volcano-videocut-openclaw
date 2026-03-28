---
name: 视频翻译配音（端到端）
description: >
  「端到端」视频翻译：识别人声、复刻音色后译为目标语言，生成译文字幕并压制，输出翻译成片。
  须先完成环境准备，base 与 index-tts 环境隔离；脚本默认 `uv run` 执行。详见 reference/环境配置.md。
trigger: 视频翻译、出海配音、译制片、多语言成片、字幕翻译压制、音色复刻
---

> 环境准备必须优先执行，且 `base` 与 `index-tts` 环境必须隔离。详见 [环境配置.md](reference/环境配置.md)。  
> Python 脚本默认使用 `uv run` 执行（`index-tts` 相关流程使用 `scripts/vendors/index-tts/.venv/bin/python`）。

## Scope

本 Skill 用于视频翻译全链路执行与文档对齐，覆盖：

1. 环境准备（必须优先执行，且 base 与 index-tts 隔离）
2. 音视频预处理（静音、音轨提取、人声/背景分离、ASR）
3. ASR 结果处理（`asr.json -> asr_split.json`）
4. 人声片段剪切（`segments/`）
5. 人声语速预估（支持多语言并发）
6. 字幕翻译（本地化、人名映射）
7. TTS 音色复刻（index-tts 独立环境）
8. 音视频合并（TTS + 背景音 + 静音视频）
9. 字幕压制（自动布局 + 可自定义样式）

## Source of Truth

流程文档统一以 `reference/` 为准：

- [环境配置.md](reference/环境配置.md)：Python/uv 安装、base 与 index-tts 隔离环境初始化
- [输入&输出.md](reference/输入&输出.md)：输出目录约定、阶段总览与关键产物定义
- [音视频预处理.md](reference/音视频预处理.md)：静音、音轨提取、人声/背景分离、ASR 入口
- [ASR结果与处理.md](reference/ASR结果与处理.md)：`asr.json -> asr_split.json` 处理口径
- [人声片段剪切.md](reference/人声片段剪切.md)：按 `asr_split` 切分 `vocals` 到 `segments/`
- [人声语速预估.md](reference/人声语速预估.md)：基于片段估计语速，支持多语言并发
- [字幕翻译.md](reference/字幕翻译.md)：翻译规则、本地化、人名映射与输出约束
- [TTS音色复刻.md](reference/TTS音色复刻.md)：复刻策略、并发/队列、重试、时长对齐要求
- [音视频合并.md](reference/音视频合并.md)：TTS + 背景音 + 静音视频合成规则
- [字幕压制.md](reference/字幕压制.md)：字幕样式、布局、安全区、折行与压制参数

## Execution Rules

- 优先复用 `scripts/base` 既有脚本，不重复造轮子。
- 除非用户明确要求，否则不新增脚本；优先完善现有脚本和文档。
- 必须先完成环境准备，再执行后续任一流程阶段。
- `base` 目录下脚本默认使用 `uv run` 执行，禁止直接混用系统 Python。
- 处理链路必须保持上下游输入输出一致（文件名、目录结构、字段口径）。
- 当输入多个目标语言时，语速评估必须逐语言执行并分别产出 `speed_profile/<lang>/` 结果。
- 所有并发任务需有队列上限、重试策略和清晰日志。
- `index-tts` 依赖必须与 `base` 环境隔离，安装在 `scripts/vendors/index-tts/.venv`。

## Workflow

推荐按以下顺序执行，除第 0 阶段外，后续阶段均基于 `output/${剧名}/${视频名}` 目录串联：

1. **阶段 0：环境准备（必须优先）**
   - 文档：`reference/环境配置.md`
   - 目标：准备 `scripts/base` 与 `scripts/vendors/index-tts` 两套隔离环境。

2. **阶段 1：音视频预处理**
   - 脚本：`scripts/base/video_asr_pipeline.py`
   - 输入：视频文件路径/HTTPS 链接（支持批量；文件夹最多一个）
   - 输出：`original_video.mp4`、`muted_video.mp4`、`audio.mp3`、`vocals.mp3`、`background.mp3`、`asr.json`

3. **阶段 2：ASR 结果处理**
   - 文档：`reference/ASR结果与处理.md`
   - 输入：`asr.json`
   - 输出：`asr_split.json`

4. **阶段 3：人声片段剪切**
   - 脚本：`scripts/base/voice_segment.py`
   - 输入：`vocals.mp3` + `asr_split.json`
   - 输出：`segments/segment_*.wav`、`segments/mapping.json`

5. **阶段 4：人声语速预估**
   - 脚本：`scripts/base/count_speed_profile.py`
   - 输入：`segments/mapping.json` + `segments/`
   - 输出：`speed_profile/`（多语言时为 `speed_profile/<lang>/`）

6. **阶段 5：字幕翻译**
   - 文档：`reference/字幕翻译.md`
   - 输入：`asr_split.json` + 语速结果（可选人名映射）
   - 输出：`translates/transcript_{lang}.json`、剧集级 `mapping_name_{lang}.json`

7. **阶段 6：TTS 音色复刻**
   - 脚本：`scripts/base/run_tts.py`（在 `index-tts` 隔离环境执行）
   - 输入：`translates/transcript_{lang}.json` + `segments/mapping.json` + `segments/`
   - 输出：`tts/{lang}/segment_*.wav`、`tts/{lang}/tts_summary.json`

8. **阶段 7：音视频合并**
   - 脚本：`scripts/base/merge_audio_video.py`
   - 输入：`muted_video.mp4` + `tts/{lang}/` + `asr_split.json` + `background.mp3`
   - 输出：`${视频名}_translate_video.mp4`

9. **阶段 8：字幕压制**
   - 脚本：`scripts/base/burn_subtitle.py`
   - 输入：`${视频名}_translate_video.mp4` + `translates/transcript_{lang}.json`
   - 输出：`${视频名}_translate_video_subbed.mp4`（可选 `ASS` 文件）

## Expected Output Layout

默认输出根目录：`output/${剧名}/${视频名}/`

关键产物：

- `original_video.mp4`
- `muted_video.mp4`
- `audio.mp3`
- `vocals.mp3`
- `background.mp3`
- `asr.json`
- `asr_split.json`
- `segments/`
- `speed_profile/`
- `translates/transcript_{lang}.json`
- `tts/{lang}/`
- `${视频名}_translate_video.mp4`

剧集级产物：

- `output/${剧名}/mapping_name_{lang}.json`
- `output/${剧名}/pipeline_report.json`

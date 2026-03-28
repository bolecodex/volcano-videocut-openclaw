# TTS 音色复刻

## 流程阶段

- 阶段 6
- 上游：`字幕翻译.md`、`人声片段剪切.md`
- 下游：`音视频合并.md`

## 目标

基于 `index-tts` 对翻译后的台词进行音色复刻，输出目标语言音频片段，并尽可能贴合原片段时长。

## 前置约束

- `index-tts` 依赖必须与 `base` 环境隔离。
- `index-tts` 相关依赖仅安装在 `scripts/vendors/index-tts/.venv`。
- 禁止将 `index-tts` 依赖安装到 `scripts/base` 环境。

## 输入

来自前置流程的两个输入：

1. 字幕翻译结果（参考 `字幕翻译.md`）
   - `transcript_{lang}.json`
2. 人声片段切分结果（参考 `人声片段剪切.md`）
   - `segments/mapping.json`
   - `segments/segment_*.wav`（或 mp3，按 mapping 的 `file` 字段）

可选输入：

- 剧集级人名映射：`mapping_name_{lang}.json`

## 输出

建议按语言分目录输出：

- `tts/{lang}/segment_tts_0001.wav`
- `tts/{lang}/segment_tts_0002.wav`
- `tts/{lang}/...`
- `tts/{lang}/tts_mapping.json`
- `tts/{lang}/tts_summary.json`

其中：

- `tts_mapping.json`：逐片段结果（输入文本、输出文件、目标时长、实际时长、状态、重试次数）
- `tts_summary.json`：汇总统计（总数、成功、失败、平均时长偏差等）

## 处理要求

1. **时长优先对齐**
   - 目标：生成音频时长尽可能接近原始片段时长。
   - 目标时长来源：`segments/mapping.json` 的 `duration`（或 `end-start`）。
   - 方案 C 策略：TTS 阶段不做倍速、不做裁剪；仅可选在偏短时补尾部静音（`--pad-to-target`）。
2. **对齐失败回退**
   - 若整句无法满足时长约束，按 `字幕翻译.md` 的翻译口径进行单句拆分后重试。
3. **人名本地化一致**
   - 优先读取剧集级 `mapping_name_{lang}.json`。
   - 缺失条目补充回写，保证同剧一致。
4. **清晰日志**
   - 至少输出：阶段开始/结束、片段 id、重试次数、失败原因、最终状态。
5. **错误重试**
   - 每个片段失败自动重试（建议 3 次，指数退避）。

## 并发与队列

- 支持批量处理。
- 单次并发上限：`10`。
- 超出并发上限的任务进入队列等待执行。
- 建议参数：
  - `max_workers=10`
  - `queue_size=10`（或更大，按资源调整）

## 建议执行形态

在 `index-tts` 独立环境中运行复刻流程（示意）：

```bash
scripts/vendors/index-tts/.venv/bin/python scripts/base/run_tts.py \
  --transcript-path "/path/to/output/剧名/视频名/translates/transcript_en.json" \
  --mapping-path "/path/to/output/剧名/视频名/segments/mapping.json" \
  --segments-dir "/path/to/output/剧名/视频名/segments" \
  --output-dir "/path/to/output/剧名/视频名/tts/en"
```

如需仅在偏短时补静音（不做倍速/裁剪）：

```bash
scripts/vendors/index-tts/.venv/bin/python scripts/base/run_tts.py \
  --transcript-path "/path/to/output/剧名/视频名/translates/transcript_en.json" \
  --mapping-path "/path/to/output/剧名/视频名/segments/mapping.json" \
  --segments-dir "/path/to/output/剧名/视频名/segments" \
  --output-dir "/path/to/output/剧名/视频名/tts/en" \
  --pad-to-target
```

> 说明：实际入口脚本为 `scripts/base/run_tts.py`；运行时会校验并要求使用 `scripts/vendors/index-tts/.venv/bin/python`。

## 质量检查

- 片段成功率（success/total）
- 时长偏差（`abs(generated_duration - source_duration)`）分布
- 人名译名一致性（同角色同译名）
- 失败片段可追溯（错误类型、重试轨迹、最终状态）

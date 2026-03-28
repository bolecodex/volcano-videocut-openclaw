---
name: LAS 大模型语音识别
description: >
  基于豆包大模型 ASR（LAS-ASR-PRO）的高精度语音转写：支持视频自动抽取音轨、降噪预处理、超大文件与超长时长、
  TOS 内网路径（tos://）输入；输出带时间戳的分句 JSON，可选说话人分离、情感/性别/语速、敏感词过滤等扩展分析。
  异步 submit/poll。适用于台词精转、会议纪要、多语言音视频（支持多格式与自动语种检测）。需 LAS 侧鉴权与算子配置。
trigger: LAS ASR、大模型转写、高精度语音识别、说话人分离、台词提取
---

# LAS-ASR-PRO（las_asr_pro）

本 Skill 用于把「LAS-ASR-PRO 接口文档」里的 `submit/poll` 异步调用流程，封装成可重复使用的脚本化工作流：

- `POST https://operator.las.cn-beijing.volces.com/api/v1/submit` 提交转写任务
- `POST https://operator.las.cn-beijing.volces.com/api/v1/poll` 轮询任务状态并获取识别结果

## 快速开始

在本 skill 目录执行：

```bash
python3 scripts/skill.py --help
```

### 提交并等待

```bash
python3 scripts/skill.py submit \
  --audio-url "https://example.com/audio.wav" \
  --audio-format wav \
  --model-name bigmodel \
  --region cn-beijing \
  --out result.json
```

### 仅提交（返回 task_id）

```bash
python3 scripts/skill.py submit \
  --audio-url "https://example.com/audio.wav" \
  --audio-format wav \
  --no-wait
```

### 轮询 / 等待

```bash
python3 scripts/skill.py poll <task_id>
python3 scripts/skill.py wait <task_id> --timeout 1800 --out result.json
```

## 参数与返回字段

详见 `references/api.md`。

## 常见问题

- API Key 未找到：设置环境变量 `LAS_API_KEY` 或提供 `env.sh`。
- Parameter.Invalid：检查字段结构/枚举值是否符合文档（推荐先最小化 payload，再逐项加字段）。
- `audio_format` 不正确：请确保容器格式与真实音频一致（以服务端支持为准）。

---
name: 火山 AI MediaKit（VOD 音视频）
description: >
  火山引擎 VOD + AI MediaKit：拼接/裁剪/变速/翻转、图生视频、音画合成、提取音轨、混音、人声分离、降噪、画质修复、AI 超分、智能补帧等；任务完成后返回点播播放链接。
  需在 .env 配置 VOLCENGINE_ACCESS_KEY、VOLCENGINE_SECRET_KEY、VOD_SPACE_NAME。
  触发：MediaKit、VOD、视频拼接、裁剪、超分、人声分离、降噪、补帧、画质增强。
version: 1.0.1
trigger: MediaKit、VOD、视频拼接、裁剪、变速、超分、人声分离、降噪、补帧、火山引擎
env:
  - VOLCENGINE_ACCESS_KEY
  - VOLCENGINE_SECRET_KEY
  - VOD_SPACE_NAME
clawhub: https://clawhub.ai/volc-ai-mediakit/volcengine-ai-mediakit
---

# Volcengine AI MediaKit

---

## 前置条件

- **Python**：确认 `python --version` ≥ 3.6
- **环境变量**（必需，也可通过工作目录下的 `.env` 文件配置，脚本会自动加载）：
  - `VOLCENGINE_ACCESS_KEY` — 火山引擎 Access Key
  - `VOLCENGINE_SECRET_KEY` — 火山引擎 Secret Key
  - `VOD_SPACE_NAME` — VOD 空间名称
- **依赖**：首次运行脚本会自动检测并安装 `volcengine`、`python-dotenv`（无需手动操作）

---

## 参数传入方式

所有脚本支持两种 JSON 参数传入方式：

1. **内联 JSON**（适合简单参数）：`python script.py '{"key":"value"}'`
2. **文件引用**（推荐，避免 shell 转义问题）：`python script.py @params.json`

`@` 前缀表示从文件读取 JSON 内容，文件路径相对于当前工作目录。

---

## 工作流程

### 1) 识别输入视频类型（必要时先上传拿 `vid://...`）

后续所有处理脚本**优先使用 VOD 侧资源引用**：

- Vid：`vid://vxxxx`（或部分脚本接受裸 `vxxxx` 并自动补 `vid://`）
- DirectUrl / FileName：`directurl://<vod_file_name>`（媒体类任务用 `DirectUrl` 时会要求 `FileName + SpaceName`）

当用户提供的是以下输入之一，需要先执行上传逻辑，拿到 `Vid` 后再继续：

- 本地文件路径：如 `/path/to/a.mp4`
- `http/https` 链接：如 `https://example.com/a.mp4`（会走 URL 拉取上传，并轮询上传结果）

统一用 `scripts/upload_media.py`：

```bash
python <SKILL_DIR>/scripts/upload_media.py "<local_file_path_or_http_url>" [space_name]
```

脚本输出中 `Source` 字段即 `vid://...`，可直接作为后续处理输入。

> **安全限制**：本地文件上传仅允许 workspace/、userdata/ 和 /tmp 目录下的文件。

### 2) 识别用户意图 → 选择对应处理脚本

根据用户需求，按以下决策树选择脚本：

```
用户意图                                    → 脚本
─────────────────────────────────────────────────────
多个视频/音频合成一个（顺序拼接）               → stitching
截取视频/音频的某个时间片段                    → clipping
加速/慢放/变速                               → speedup
镜像/上下翻转/左右翻转                        → flip
多张图片串联生成视频                          → image_to_video
替换/叠加视频的背景音乐                       → compile
只要视频里的音频轨                            → extract_audio
多条音频同时叠加播放（混音）                   → mix_audios
分离人声和伴奏/背景音                          → voice_separation
去除环境噪音/电流杂音/风噪                     → noise_reduction
模糊/低画质视频修复（压缩伪影/噪点/划痕）       → quality_enhance
低分辨率视频提升（如 720P→1080P）               → super_resolution
低帧率视频插帧提升流畅度（如 30fps→60fps）      → interlacing
```

### 3) 构造参数并执行

#### 视频编辑类

| 脚本 | 用途 | 详细参数 |
|------|------|---------|
| `stitching.py '<json>'` | 视频/音频拼接 | [references/01-stitching.md](references/01-stitching.md) |
| `clipping.py '<json>'` | 视频/音频裁剪 | [references/02-clipping.md](references/02-clipping.md) |
| `flip.py '<json>'` | 视频翻转 | [references/03-flip.md](references/03-flip.md) |
| `speedup.py video '<json>'` | 视频变速 | [references/04-speedup.md](references/04-speedup.md) |
| `speedup.py audio '<json>'` | 音频变速 | [references/04-speedup.md](references/04-speedup.md) |
| `image_to_video.py '<json>'` | 图片转视频 | [references/05-image-to-video.md](references/05-image-to-video.md) |
| `compile.py '<json>'` | 音视频合成 | [references/06-compile.md](references/06-compile.md) |
| `extract_audio.py '<json>'` | 提取音轨 | [references/07-extract-audio.md](references/07-extract-audio.md) |
| `mix_audios.py '<json>'` | 混音 | [references/08-mix-audios.md](references/08-mix-audios.md) |

#### 媒体处理类

| 脚本 | 用途 | 详细参数 |
|------|------|---------|
| `voice_separation.py '<json>'` | 人声分离 | [references/10-voice-separation.md](references/10-voice-separation.md) |
| `noise_reduction.py '<json>'` | 音频降噪 | [references/11-noise-reduction.md](references/11-noise-reduction.md) |
| `quality_enhance.py '<json>'` | 综合画质修复 | [references/12-quality-enhance.md](references/12-quality-enhance.md) |
| `super_resolution.py '<json>'` | AI 超分辨率 | [references/13-super-resolution.md](references/13-super-resolution.md) |
| `interlacing.py '<json>'` | 智能补帧 | [references/14-interlacing.md](references/14-interlacing.md) |

#### 重启轮询

| 脚本 | 用途 |
|------|------|
| `poll_vcreative.py <VCreativeId>` | 重启编辑类任务轮询 |
| `poll_media.py <task_type> <RunId>` | 重启媒体处理类任务轮询 |

超时响应中的 `resume_hint.command` 字段包含可直接复制执行的重启命令。

---

## 示例

```bash
# 本地文件先上传拿到 vid（后续脚本统一用 vid://... 作为输入）
python <SKILL_DIR>/scripts/upload_media.py "/path/to/local.mp4" my_space

# 拼接两个视频，加转场
python <SKILL_DIR>/scripts/stitching.py \
  '{"type":"video","videos":["vid://v0001","vid://v0002"],"transitions":["1182359"]}'

# 使用 @file.json 传参（推荐，避免转义问题）
python <SKILL_DIR>/scripts/stitching.py @params.json

# 人声分离（注意 type 首字母大写）
python <SKILL_DIR>/scripts/voice_separation.py '{"type":"Vid","video":"v0310abc"}'

# 超分到 1080P
python <SKILL_DIR>/scripts/super_resolution.py '{"type":"Vid","video":"v0310xyz","Res":"1080p"}'

# 超时后重启编辑类轮询
python <SKILL_DIR>/scripts/poll_vcreative.py vcreative_xxx my_space

# 超时后重启媒体类轮询
python <SKILL_DIR>/scripts/poll_media.py videSuperResolution run_yyy my_space
```

---

## 错误输出

所有错误统一格式：`{"error": "说明"}`

超时输出（含重启指令）：
```json
{
  "error": "轮询超时（360 次 × 5s），任务仍在处理中",
  "resume_hint": {
    "description": "任务尚未完成，可用以下命令重启轮询",
    "command": "python <SKILL_DIR>/scripts/poll_media.py videSuperResolution run_yyy my_space"
  }
}
```

## 约束
- 调用脚本前**必须**查看脚本详细参数说明

---

## 计费说明

仅当用户主动咨询费用或计费规则时，再参考 `references/00-billing-instructions.md` 中的计费说明，向用户简要说明 volcengine-ai-mediakit 所依赖的 VOD 资源的计费构成，避免在普通剪辑/处理对话中主动展开计费细节。


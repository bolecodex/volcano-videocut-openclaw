---
name: novel-06-shots-to-ai-video
description: 将分镜头数据转换为 AI 动画视频。读取 shots/*.yaml 分镜文件，使用 Seedance Lite 模型生成视频片段，支持参考图生视频、图生视频和文生视频三种模式。当用户想要为分镜生成 AI 视频、制作动画片段、将分镜图片转为动态视频时使用此 skill。
---

# 分镜头 AI 视频生成

使用 Seedance Lite 模型将分镜头数据转换为 AI 动画视频，根据角色参考图自动选择最佳生成模式。

## 项目目录定位规则（必须首先执行）

> **本 skill 的所有读写操作都基于 `{项目目录}`，不是 workspace 根目录。**

`{项目目录}` 是 workspace 根目录下以剧本简称命名的子目录，由上游 skill 创建：

```
{workspace根目录}/
├── {剧本简称}/          ← 这就是 {项目目录}
│   ├── style.yaml
│   ├── shots/
│   └── ...
└── 剧本原文.md
```

### 如何定位

1. 用户指定了项目名 → 直接使用 `{workspace}/{项目名}/`
2. 用户未指定 → 列出 workspace 下的子目录，找到包含 `shots/` 和 `style.yaml` 的目录
3. **禁止**在 workspace 根目录下直接读写产物文件

---

## 模型选择策略

| 优先级 | 条件 | 模型 | 说明 |
|--------|------|------|------|
| 1 | 有角色参考图 | `reference-to-video` | 角色外貌一致性最好 |
| 2 | 有分镜图片(`image_url`) | `image-to-video` | 以分镜图为首帧生成动画 |
| 3 | 无任何图片 | `text-to-video` | 纯文本描述生成视频 |

## 工作流程

```
任务进度：
- [ ] 步骤 1：读取资产清单
- [ ] 步骤 2：选择场景
- [ ] 步骤 3：生成 AI 视频
- [ ] 步骤 4：更新状态并展示结果
```

---

## 步骤 1：读取资产清单

读取以下文件：

```
{项目目录}/style.yaml                    # 全局风格配置（视频参数）
{项目目录}/shots/_manifest.yaml          # 分镜索引
{项目目录}/{剧本名}_角色资产.yaml        # 角色图片
```

### 1.1 从 `style.yaml` 提取视频参数

```python
style_base = style_yaml['style_base']                    # 全局风格词（文生视频模式用）
aspect_ratio = style_yaml['video']['aspect_ratio']       # 视频宽高比，如 "9:16"
resolution = style_yaml['video']['resolution']           # 分辨率，如 "720p"
duration_default = style_yaml['video']['duration_default']  # 默认时长，如 "5"
```

### 1.2 从 `_manifest.yaml` 提取

- `characters`: 角色 ID 与描述映射
- `files`: 所有场景分镜文件列表

### 1.3 从角色资产 YAML 提取角色图片 URL 映射表

```python
# 从 {剧本名}_角色资产.yaml 提取
角色图片映射 = {}
for char in yaml_data['characters']:
    if char.get('image_url') and char.get('image_status') == 'completed':
        角色图片映射[char['id']] = char['image_url']
```

---

## 步骤 2：选择场景

展示场景列表及资源状态：

```
可用场景：
1. SC_01_开篇悬念 (2 镜头, 图片: 2/2 ✅)
2. SC_02_西市日常 (4 镜头, 图片: 4/4 ✅)
...

请选择要生成 AI 视频的场景编号（或 "all"）：
```

读取选中场景的分镜 YAML 文件。

---

## 步骤 3：生成 AI 视频

对每个镜头按优先级选择模式并生成视频。

### 3.1 判断生成模式

```python
# 伪代码
for shot in scene.shots:
    # 收集角色参考图
    ref_images = []
    for char in shot.characters:
        if char.ref in 角色图片映射:
            ref_images.append(角色图片映射[char.ref])
    
    if ref_images:
        # 模式 1：参考图生视频（最优）
        generate_reference_to_video(shot, ref_images)
    elif shot.image_url and shot.image_status == "completed":
        # 模式 2：图生视频（用分镜图做首帧）
        generate_image_to_video(shot)
    else:
        # 模式 3：文生视频
        generate_text_to_video(shot)
```

### 3.2 构建视频提示词

视频提示词 = 动作描述 + 场景氛围，**不需要包含角色外貌特征**（参考图已提供）。

**提示词模板**：

```
{场景描述}，{氛围/光照}。
{角色1动作描述}，{角色1情绪}。
{角色2动作描述}，{角色2情绪}。
{镜头运动描述}。
```

**示例（SC_07_001）**：

```
简陋卧房内，雨夜暗调，窗外闪电偶尔照亮房间。
一个女子惊醒坐起在床上，眼神惊恐地看向地面。
一个男子躺在床边地上，面容扭曲挣扎，额上青筋暴起，口中念念有词。
中景镜头，缓慢推近。
```

> **注意**：参考图模式中，提示词中用"一个女子"、"一个男子"等泛称即可，因为模型会从参考图中识别角色外貌。若只有一个角色参考图，则该角色用泛称，提示词聚焦动作和场景。

### 3.3 模式 1：参考图生视频（reference-to-video）

当镜头有角色参考图时使用。参考图中的人物会出现在视频中。

使用 MCP 工具 `generate`：

```json
{
  "model": "fal-ai/bytedance/seedance/v1/lite/reference-to-video",
  "prompt": "简陋卧房内，雨夜暗调...",
  "aspect_ratio": "9:16",
  "duration": "5",
  "options": {
    "reference_image_urls": [
      "https://v3b.fal.media/苏晚.png",
      "https://v3b.fal.media/陈屠.png"
    ],
    "resolution": "720p"
  }
}
```

**参数说明**：
- `reference_image_urls`: 1-4 张角色参考图 URL
- `aspect_ratio`: 与分镜图保持一致，默认 `9:16`
- `resolution`: 默认 `720p`
- `duration`: 默认 `5` 秒，可根据台词时长调整（2-12 秒）

### 3.4 模式 2：图生视频（image-to-video）

当无角色参考图但有分镜图片时使用。以分镜图为首帧生成动画。

使用 MCP 工具 `generate`：

```json
{
  "model": "fal-ai/bytedance/seedance/v1/lite/image-to-video",
  "prompt": "画面中的人物开始动作...",
  "image_url": "https://v3b.fal.media/分镜图.png",
  "aspect_ratio": "9:16",
  "duration": "5",
  "options": {
    "resolution": "720p"
  }
}
```

### 3.5 模式 3：文生视频（text-to-video）

当无任何图片时使用。纯文本描述生成视频。

使用 MCP 工具 `generate`：

```json
{
  "model": "fal-ai/bytedance/seedance/v1/lite/text-to-video",
  "prompt": "真人写实高清，古风场景...",
  "aspect_ratio": "9:16",
  "duration": "5",
  "options": {
    "resolution": "720p"
  }
}
```

> 文生视频模式下，提示词需要包含完整的风格描述和角色外貌特征（因为没有参考图）。此时使用 `style_base` + 原始 prompt。

### 3.6 时长选择策略

根据镜头台词数量和内容估算合适时长：

| 台词数 | 建议时长 | 说明 |
|--------|---------|------|
| 0-1 条 | 3-4 秒 | 快速过渡镜头 |
| 2-3 条 | 5-6 秒 | 标准叙事镜头 |
| 4-5 条 | 7-8 秒 | 重要剧情镜头 |
| 6+ 条 | 10-12 秒 | 高潮/转折镜头 |

> 这只是参考，最终视频会与音频在后期合成时对齐时长。AI 视频主要提供动画素材。

### 3.7 查询任务结果

使用 MCP 工具 `get_result` 轮询查询结果，获取生成的视频 URL。

**轮询策略**：
1. 提交任务后等待 30 秒
2. 每 15 秒使用 `get_result` 查询一次状态
3. 超时 5 分钟则标记失败

---

## 步骤 4：更新状态并展示结果

### 4.1 更新分镜 YAML

每个镜头生成成功后，立即更新 YAML：

```yaml
- id: "SC_07_001"
  # ... 其他字段保持不变
  video_url: "https://v3b.fal.media/files/xxx.mp4"
  video_status: completed
  video_mode: reference   # reference / image / text
  video_duration: "5"
  video_generated_at: "2026-02-06T10:30:00"
```

新增字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `video_url` | string | 生成视频的 URL |
| `video_status` | string | `pending` / `completed` / `failed` |
| `video_mode` | string | 生成模式: `reference` / `image` / `text` |
| `video_duration` | string | 视频时长（秒） |
| `video_generated_at` | string | 生成时间 |

### 4.2 展示结果

```markdown
## 场景 SC_07_雨夜惊梦 AI 视频生成完成

### 镜头 SC_07_001: 雨夜惊醒
- 模式：🎯 参考图生视频（苏晚 + 陈屠）
- 时长：5 秒
- 视频：[点击查看](视频URL)
- 状态：✅ 已写入 YAML

### 镜头 SC_07_002: 梦中呓语
- 模式：🎯 参考图生视频（陈屠）
- 时长：5 秒
- 视频：[点击查看](视频URL)
- 状态：✅ 已写入 YAML

---
✅ 已自动更新 YAML 文件
如需重新生成某个镜头，请告诉我镜头编号。
```

---

## 完整示例

### 示例：生成 SC_07_001 镜头视频

**镜头数据**：
```yaml
- id: "SC_07_001"
  title: "雨夜惊醒"
  shot_type: "中景"
  characters:
    - ref: "@szj_suwan"
      action: 惊醒坐起
      emotion: 惊恐
    - ref: "@szj_chentu"
      action: 躺在地上挣扎
      emotion: 梦中痛苦
  mood: 紧张、恐惧
  lighting: 雨夜暗调，闪电
```

**角色图片映射**：
```yaml
"@szj_suwan": "https://v3b.fal.media/files/.../苏晚.png"
"@szj_chentu": "https://v3b.fal.media/files/.../陈屠.png"
```

**判断**：两个角色都有参考图 → 使用 `reference-to-video`

**构建提示词**：
```
简陋卧房内，雨夜暗调，窗外闪电偶尔照亮房间。
一个女子惊醒坐起在床上，眼神惊恐地看向地面。
一个男子躺在床边地上，面容扭曲挣扎，额上青筋暴起。
中景镜头，缓慢推近，紧张恐惧氛围。
```

使用 MCP 工具 `generate`：

```json
{
  "model": "fal-ai/bytedance/seedance/v1/lite/reference-to-video",
  "prompt": "简陋卧房内，雨夜暗调，窗外闪电偶尔照亮房间。一个女子惊醒坐起在床上，眼神惊恐地看向地面。一个男子躺在床边地上，面容扭曲挣扎，额上青筋暴起。中景镜头，缓慢推近，紧张恐惧氛围。",
  "aspect_ratio": "9:16",
  "duration": "5",
  "options": {
    "reference_image_urls": [
      "https://v3b.fal.media/files/.../苏晚.png",
      "https://v3b.fal.media/files/.../陈屠.png"
    ],
    "resolution": "720p"
  }
}
```

---

## 批量生成策略

### 并行提交

由于视频生成耗时较长（约 60-120 秒/个），建议：

1. 一次提交一个场景的所有镜头任务
2. 使用 `generate` 提交后记录 `task_id`
3. 等待一段时间后批量查询结果
4. 每完成一个镜头立即写入 YAML

### 重试策略

| 失败原因 | 处理方式 |
|---------|---------|
| 角色图片 URL 失效 | 提示用户重新生成角色图片 |
| 生成超时 | 自动重试 1 次 |
| 内容审核失败 | 调整提示词后重试 |
| 角色无参考图 | 回退到图生视频或文生视频模式 |

---

## 参数参考

### aspect_ratio 选择（从 style.yaml 读取）

视频宽高比统一从 `style.yaml → video.aspect_ratio` 读取：

| 值 | 说明 | 适用场景 |
|----|------|---------|
| `16:9` | 横屏 | B站、YouTube |
| `9:16` | 竖屏 | 抖音、快手 |
| `1:1` | 方形 | 微信朋友圈 |

> **不在本 skill 中硬编码宽高比**，统一由 `style.yaml` 控制，保证与分镜图尺寸一致。

### resolution 选择

| 分辨率 | 速度 | 质量 | 推荐场景 |
|--------|------|------|---------|
| `480p` | 快 | 一般 | 快速预览 |
| `720p` | 中 | 好 | 正式生成（默认）|

### duration 范围

支持 2-12 秒，以字符串形式传入（如 `"5"`）。

---

## 步骤 5：刷新可视化页面

完成 AI 视频生成后，**必须**运行脚本刷新 HTML 可视化页面，让视频播放器在页面中展示：

```bash
python {novel-03-skill目录}/scripts/generate_storyboard.py --project "{项目目录}/"
```

> 该脚本读取所有 `shots/*.yaml` 中的最新数据（包括刚写入的 `video_url`），重新生成 `{项目目录}/index.html`。

```bash
open "{项目目录}/index.html"
```

**页面展示内容**：
- 每个镜头的视频播放器（如有 `video_url`，使用分镜图作为封面）
- 视频生成模式标签（reference / image / text）
- 视频时长显示
- 统计面板：已生视频/总镜头数

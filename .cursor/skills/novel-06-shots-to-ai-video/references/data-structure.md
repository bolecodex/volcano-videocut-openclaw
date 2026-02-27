# AI 视频字段 - YAML 数据结构扩展

## 新增字段

在已有的分镜 YAML 结构基础上，每个 shot 新增以下视频相关字段：

```yaml
shots:
  - id: "SC_07_001"
    title: "雨夜惊醒"
    # ... 原有字段保持不变 ...
    
    # 图片字段（已有）
    image_url: "https://v3b.fal.media/files/.../shot_001.png"
    image_status: completed
    
    # 视频字段（新增）
    video_url: "https://v3b.fal.media/files/.../video_001.mp4"
    video_status: completed        # pending / completed / failed
    video_mode: reference          # reference / image / text
    video_duration: "5"            # 视频时长（秒）
    video_generated_at: "2026-02-06T10:30:00"
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video_url` | string | 生成后必填 | AI 生成的视频 URL |
| `video_status` | string | 是 | 生成状态 |
| `video_mode` | string | 是 | 使用的生成模式 |
| `video_duration` | string | 是 | 视频时长（秒），范围 2-12 |
| `video_generated_at` | string | 生成后必填 | ISO 8601 时间戳 |

## video_mode 取值

| 值 | 模型 ID | 说明 |
|----|---------|------|
| `reference` | `fal-ai/bytedance/seedance/v1/lite/reference-to-video` | 使用角色参考图生成，角色一致性最好 |
| `image` | `fal-ai/bytedance/seedance/v1/lite/image-to-video` | 以分镜图为首帧生成动画 |
| `text` | `fal-ai/bytedance/seedance/v1/lite/text-to-video` | 纯文本生成视频 |

## 模式选择决策树

```
镜头(shot)
  │
  ├─ characters 中有角色?
  │   ├─ 是 → 查找角色图片映射
  │   │   ├─ 找到参考图 → mode: reference (参考图生视频)
  │   │   └─ 未找到参考图 ─┐
  │   └─ 否 ─────────────┤
  │                       │
  │   ┌───────────────────┘
  │   │
  │   ├─ 有 image_url 且 image_status=completed?
  │   │   ├─ 是 → mode: image (图生视频)
  │   │   └─ 否 → mode: text (文生视频)
```

## 三种模型参数对比

### reference-to-video

```json
{
  "model_id": "fal-ai/bytedance/seedance/v1/lite/reference-to-video",
  "parameters": {
    "prompt": "必填 - 动作/场景描述",
    "reference_image_urls": ["必填 - 1-4张参考图"],
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "duration": "5"
  }
}
```

### image-to-video

```json
{
  "model_id": "fal-ai/bytedance/seedance/v1/lite/image-to-video",
  "parameters": {
    "prompt": "必填 - 动作描述",
    "image_url": "必填 - 首帧图片URL",
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "duration": "5"
  }
}
```

### text-to-video

```json
{
  "model_id": "fal-ai/bytedance/seedance/v1/lite/text-to-video",
  "parameters": {
    "prompt": "必填 - 完整场景+角色描述",
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "duration": "5"
  }
}
```

## 提示词差异

| 模式 | 提示词内容 | 是否包含风格词 | 是否包含角色外貌 |
|------|-----------|--------------|----------------|
| reference | 动作 + 场景 + 镜头运动 | 否 | 否（参考图已有） |
| image | 动作描述 | 否 | 否（首帧已有） |
| text | style_base + 场景 + 角色外貌 + 动作 | 是 | 是 |

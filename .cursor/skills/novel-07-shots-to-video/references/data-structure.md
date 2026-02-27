# 分镜 YAML 数据结构

## 场景文件结构

```yaml
# shots/SC_XX_场景名.yaml

scene_id: "SC_01"
scene_name: "开篇悬念"
scene_ref: "scenes/SC_01_开篇悬念.md"
scene_type: "prologue"
scene_description: "简陋卧房，油灯摇曳，夜晚"
scene_mood: "神秘、悬疑"
scene_lighting: "油灯侧逆光，暖黄昏暗"

shots:
  - id: "SC_01_001"
    title: "秘密揭示"
    shot_type: "中景"
    
    characters:
      - ref: "@szj_suwan"
        action: 坐在床边凝视熟睡的陈屠
        emotion: 神秘、若有所思
      - ref: "@szj_chentu"
        action: 熟睡中，眉头紧锁
        emotion: 梦魇
    
    composition:
      angle: 平视
      focus: 苏晚侧脸
      background: 油灯摇曳的简陋卧房
    
    mood: 神秘、悬疑
    lighting: 油灯侧逆光
    
    # 台词/音频列表
    lines:
      - speaker: 旁白
        text: 我那夫君，有个秘密。
        audio_url: "https://minimax-xxx.mp3"
        audio_status: completed
      - speaker: 旁白
        text: 他杀的，不止是猪。
        audio_url: "https://minimax-xxx.mp3"
        audio_status: completed
      - speaker: 苏晚
        text: 夫君，今晚，替我多砍几刀。
        emotion: 颤抖、决绝
        audio_url: "https://minimax-xxx.mp3"
        audio_status: completed
    
    # 图片信息
    prompt: |
      简陋卧房内，木板床，厚棉被，油灯摇曳...
    image_path: "SC_01_开篇悬念/shot_001.png"
    image_status: completed
    image_url: "https://fal.media/xxx.png"
    generated_at: "2026-02-05T17:38:27"
```

## 关键字段说明

### 图片相关

| 字段 | 类型 | 说明 |
|------|------|------|
| `image_url` | string | 生成图片的在线 URL |
| `image_path` | string | 本地存储路径 |
| `image_status` | string | 状态: `pending` / `completed` / `failed` |

### 音频相关

| 字段 | 类型 | 说明 |
|------|------|------|
| `lines` | array | 台词列表 |
| `lines[].text` | string | 台词文本 |
| `lines[].speaker` | string | 说话人 |
| `lines[].audio_url` | string | TTS 生成的音频 URL |
| `lines[].audio_status` | string | 状态: `pending` / `completed` / `failed` |

## 视频合成逻辑

```
单个镜头(shot):
  ┌─────────────────────────────────────────────┐
  │  image_url (静态图片)                        │
  │                                             │
  │  + lines[0].audio + lines[1].audio + ...    │
  │    (按顺序合并的音频)                         │
  │                                             │
  │  = shot_video.mp4                           │
  │    (图片显示时长 = 音频总时长)                 │
  └─────────────────────────────────────────────┘

场景视频:
  shot_001.mp4 + shot_002.mp4 + ... = scene_video.mp4

完整视频:
  scene_01.mp4 + scene_02.mp4 + ... = final_video.mp4
```

## 资源完整性检查

合成视频前必须检查：

1. **图片完整**：`image_status == "completed"` 且 `image_url` 有效
2. **音频完整**：所有 `lines[].audio_status == "completed"` 且 `audio_url` 有效

缺少任一资源的镜头将被跳过。

# 分镜 YAML 数据结构

与 novel-07-shots-to-video 共享相同的数据格式，详见该 skill 的 references/data-structure.md。

## Remotion 所需的转换

prepare-data.ts 脚本将 YAML 数据转换为 Remotion inputProps (JSON) 格式：

```
YAML 字段              → Remotion Props 字段
────────────────────    ────────────────────
scene_id               → sceneId
scene_name             → sceneName
shot.id                → shots[].id
shot.title             → shots[].title
shot.shot_type         → shots[].shotType
shot.image_url         → (下载到 public/) → shots[].imageSrc
shot.lines[].text      → shots[].lines[].text
shot.lines[].speaker   → shots[].lines[].speaker
shot.lines[].audio_url → (下载到 public/) → shots[].lines[].audioSrc
(ffprobe 计算)          → shots[].lines[].durationInSeconds
(音频时长合计 + 0.5s)   → shots[].durationInFrames
```

## inputProps JSON 结构

```json
{
  "sceneId": "SC_01",
  "sceneName": "开篇悬念",
  "shots": [
    {
      "id": "SC_01_001",
      "title": "夫君的秘密",
      "imageSrc": "images/SC_01_001.png",
      "lines": [
        {
          "speaker": "旁白",
          "text": "我那夫君，有个秘密。",
          "audioSrc": "audio/SC_01_001_line_00.mp3",
          "durationInSeconds": 2.5
        }
      ],
      "totalDurationInSeconds": 5.2,
      "durationInFrames": 171
    }
  ],
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "transitionDurationInFrames": 15,
  "transitionType": "fade",
  "enableKenBurns": true,
  "enableSubtitles": true,
  "subtitleStyle": {
    "fontSize": 42,
    "fontFamily": "Noto Sans SC, sans-serif",
    "color": "#FFFFFF",
    "backgroundColor": "rgba(0, 0, 0, 0.6)",
    "position": "bottom"
  }
}
```

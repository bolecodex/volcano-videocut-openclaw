---
name: scene-detector
description: >
  使用 FFmpeg 检测视频中的场景切换点，输出场景边界时间戳和代表帧截图。
  在以下场景使用：(1) 检测视频场景变化点，(2) 提取场景代表帧，(3) 为 AI 分析提供场景索引。
  触发关键词："场景检测"、"场景切割"、"转场检测"、"scene detection"。
---

# 场景切割检测

使用 FFmpeg 检测视频中的场景切换点。

## 前置条件

- FFmpeg 已安装
- Python 3.10+

## 工作流程

### 第一步：运行检测

```bash
# 检测单个视频的场景变化
python3 scripts/scene_detect.py "video/原始短剧/05.mp4" -o video/output/

# 批量检测目录下所有视频
python3 scripts/scene_detect.py "video/原始短剧/" -o video/output/

# 调整检测灵敏度（阈值越低越灵敏，默认 0.3）
python3 scripts/scene_detect.py "video/05.mp4" -t 0.2

# 跳过缩略图提取（更快）
python3 scripts/scene_detect.py "video/05.mp4" --no-thumbnails
```

### 输出格式

```json
{
  "video": "05.mp4",
  "total_duration": 300.5,
  "scene_count": 15,
  "scenes": [
    {
      "scene_id": 1,
      "timestamp": "00:00:00.00",
      "seconds": 0.0,
      "end_seconds": 18.5,
      "duration": 18.5,
      "thumbnail": "video/output/scene_thumbs/scene_000_0s.jpg"
    }
  ]
}
```

### 与分析联动

场景数据辅助 AI 分析确保切点在场景边界附近：

```bash
# 先检测场景，再分析视频
python3 scripts/scene_detect.py "video/原始短剧/" -o video/output/
python3 scripts/analyze_video.py "video/原始短剧/" -o video/output/
```

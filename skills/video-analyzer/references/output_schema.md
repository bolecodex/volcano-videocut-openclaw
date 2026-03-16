# 视频分析输出格式

```json
{
  "episode": "string — 视频文件名或集数",
  "total_duration": "string — 视频总时长，格式 HH:MM:SS",
  "summary": "string — 本集剧情概要（2-3 句话）",
  "highlights": [
    {
      "id": "integer — 片段唯一标识（从 1 开始）",
      "start_time": "string — 开始时间 HH:MM:SS",
      "end_time": "string — 结束时间 HH:MM:SS",
      "duration_seconds": "integer — 片段时长（秒）",
      "type": "string — 类型：opening（开头）| hook（钩子）| conflict（冲突）| climax（高潮）| emotional（情感）| suspense（悬念）",
      "reason": "string — 该片段适合投流的具体理由",
      "priority": "integer — 优先级 1（最低）到 5（最高）",
      "suggested_position": "string — 建议位置：opening（开头）| middle（中间）| ending（结尾）",
      "tags": ["string — 描述标签，如：背叛、情绪激动、悬念"],
      "audio_note": "string — 音频特点描述"
    }
  ],
  "recommended_combinations": [
    {
      "version": "integer — 版本号（从 1 开始）",
      "name": "string — 版本名称，如：冲突开场版",
      "segments": ["integer — 按播放顺序排列的高光 ID 列表"],
      "estimated_duration_seconds": "integer — 预估总时长（秒）",
      "rationale": "string — 该编排方式的理由，为什么这样排列能最大化吸引力"
    }
  ],
  "scenes_to_remove": [
    {
      "start_time": "string — HH:MM:SS",
      "end_time": "string — HH:MM:SS",
      "reason": "string — 删除理由（如：片尾字幕、违规内容）"
    }
  ]
}
```

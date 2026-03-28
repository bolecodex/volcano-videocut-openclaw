# 动效清单与规范

## 动效清单

| 组件 | 场景与要点 | 配置字段 |
|------|-----------|----------|
| 人物条 (lower_third) | 开头出现，展示姓名、职位、公司 | name, role, company, startMs, durationMs |
| 章节标题 (chapter_title) | 话题明显切换时使用 | number, title, subtitle, startMs, durationMs |
| 花字 (fancy_text) | 用短语概括观点 | text, style, startMs, endMs, position |
| 名词卡片 (term_card) | 解释专业术语，与花字互补 | english, description, firstAppearanceMs |
| 金句卡片 (quote_callout) | 突出可引用的完整句子 | text, author, startMs, durationMs, position |
| 数据动画 (animated_stats) | 出现数字、百分比时使用 | prefix, number, unit, label, startMs, position |
| 要点列表 (bullet_points) | 内容可概括为要点时使用 | title, points[], startMs, durationMs, position |
| 社交媒体条 (social_bar) | 结尾引导关注；platform: twitter/weibo/youtube/tiktok | platform, label, handle, startMs, durationMs, position |

## 关键规范

1. 花字必须是短语形式，不能只是单词，且不与名词卡片重复。
2. 花字默认放在字幕上方区域，避免遮挡人脸。
3. 花字需避免与其他动效出现在同一帧。
4. term-card 的 position 支持 lt/lb/rt/rb，分别对应左上、左下、右上、右下
5. 其他 position 可选值为：'top' | 'tl' | 'tr' | 'bottom' | 'bl' | 'br' | 'left' | 'lt' | 'lb' | 'right' | 'rt' | 'rb'。
6. 章节标题时长在5秒左右。
7. 社交媒体条通常在结尾出现，时长建议 8-10 秒。


## 输出格式

请以 JSON 格式输出建议，包含以下字段：

- theme：推荐主题（tiktok/notion/cyberpunk/apple/aurora）
- lowerThirds：人物条信息
- chapterTitles：章节标题列表
- keyPhrases：花字列表（短语观点，非单词）
- termDefinitions：名词卡片列表（术语解释）
- quotes：金句列表
- stats：数据动画列表
- bulletPoints：要点列表
- socialBars：社交媒体条列表


每个组件都需要包含 startMs（开始时间毫秒）字段。如下：

```
{
  "theme": "tiktok",
  "videoInfo": {
    "width": 576,
    "height": 1024
  },
  "lowerThirds": [
    {
      "name": "Dario Amodei",
      "role": "CEO",
      "company": "Anthropic",
      "startMs": 1000,
      "durationMs": 5000
    }
  ],
  "chapterTitles": [
    {
      "number": "Part 1",
      "title": "指数增长的本质",
      "subtitle": "The Nature of Exponential Growth",
      "startMs": 0,
      "durationMs": 4000
    }
  ],
  "keyPhrases": [
    {
      "text": "AI发展是平滑曲线",
      "style": "emphasis",
      "startMs": 2630,
      "endMs": 5500
    }
  ],
  "termDefinitions": [
    {
      "english": "Moore's Law",
      "description": "集成电路晶体管数量每18-24个月翻一番",
      "firstAppearanceMs": 37550,
      "displayDurationSeconds": 6
    }
  ],
  "quotes": [
    {
      "text": "AI 的发展是一个非常平滑的指数曲线",
      "author": "— Dario Amodei",
      "startMs": 30000,
      "durationMs": 5000
    }
  ],
  "stats": [
    {
      "prefix": "增长率 ",
      "number": 240,
      "unit": "%",
      "label": "计算能力年增长",
      "startMs": 45000,
      "durationMs": 4000
    }
  ],
  "bulletPoints": [
    {
      "title": "核心观点",
      "points": [
        "AI 发展是平滑的指数曲线",
        "类似摩尔定律的智能增长",
        "没有突然的奇点时刻"
      ],
      "startMs": 50000,
      "durationMs": 6000
    }
  ]
}
```

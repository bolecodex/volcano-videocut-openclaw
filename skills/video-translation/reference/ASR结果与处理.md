# ASR结果与处理

## 流程阶段

- 阶段 2
- 上游：`音视频预处理.md`
- 下游：`人声片段剪切.md`、`字幕翻译.md`

**禁止生成新的脚本进行内容处理**

## 输入

- 音视频预处理的 asr 结果

## asr 格式如下：

```json
{
  "language": "Chinese",
  "language_probability": 1.0,
  "duration": 123.97133786848073,
  "segments": [
    {
      "id": 1,
      "start": 3.97,
      "end": 4.478,
      "text": "是。",
      "words": [
        {
          "word": "是",
          "start": 3.97,
          "end": 4.05,
          "probability": 1.0
        }
      ]
    },
    {
      "id": 2,
      "start": 59.01,
      "end": 62.849999999999994,
      "text": "好不容易弄到一拜大师建庙会的 V I P 邀请卡",
      "words": [
        {
          "word": "好",
          "start": 59.01,
          "end": 59.089999999999996,
          "probability": 1.0
        },
        {
          "word": "不",
          "start": 59.089999999999996,
          "end": 59.25,
          "probability": 1.0
        },
        {
          "word": "容",
          "start": 59.25,
          "end": 59.41,
          "probability": 1.0
        },
        {
          "word": "易",
          "start": 59.41,
          "end": 59.57,
          "probability": 1.0
        },
        {
          "word": "弄",
          "start": 59.57,
          "end": 59.73,
          "probability": 1.0
        },
        {
          "word": "到",
          "start": 59.73,
          "end": 59.97,
          "probability": 1.0
        },
        {
          "word": "一",
          "start": 60.05,
          "end": 60.129999999999995,
          "probability": 1.0
        },
        {
          "word": "拜",
          "start": 60.129999999999995,
          "end": 60.29,
          "probability": 1.0
        },
        {
          "word": "大",
          "start": 60.29,
          "end": 60.449999999999996,
          "probability": 1.0
        },
        {
          "word": "师",
          "start": 60.449999999999996,
          "end": 60.69,
          "probability": 1.0
        },
        {
          "word": "建",
          "start": 60.69,
          "end": 60.85,
          "probability": 1.0
        },
        {
          "word": "庙",
          "start": 60.85,
          "end": 61.089999999999996,
          "probability": 1.0
        },
        {
          "word": "会",
          "start": 61.089999999999996,
          "end": 61.25,
          "probability": 1.0
        },
        {
          "word": "的",
          "start": 61.25,
          "end": 61.33,
          "probability": 1.0
        },
        {
          "word": "V",
          "start": 61.489999999999995,
          "end": 61.57,
          "probability": 1.0
        },
        {
          "word": "I",
          "start": 61.57,
          "end": 61.73,
          "probability": 1.0
        },
        {
          "word": "P",
          "start": 61.73,
          "end": 61.89,
          "probability": 1.0
        },
        {
          "word": "邀",
          "start": 61.89,
          "end": 62.05,
          "probability": 1.0
        },
        {
          "word": "请",
          "start": 62.05,
          "end": 62.21,
          "probability": 1.0
        },
        {
          "word": "卡",
          "start": 62.21,
          "end": 62.849999999999994,
          "probability": 1.0
        }
      ]
    }
  ]
}
```

## 处理要求：

1. 需要根据上下文理解当前说话的语气、语境等
2. 根据语气、语境等结合 `words` 做好拆分
3. 如果语句过长需要判断在合适的时机进行拆分，需要结合 `words` 实现

## 输出

- 输出为 `asr_split.json`, 结构 `asr.json` 一致
- 建议存放位置：`output/${剧名}/${视频名}/asr_split.json`

---
name: 封面与关键帧提取
description: >
  从视频中提取高冲击力帧作为封面候选，可选调用 AI 评估最佳封面。
  在以下场景使用：(1) 生成投流素材封面，(2) 提取视频关键帧，(3) AI 评估封面效果。
  触发关键词："封面"、"首帧"、"缩略图"、"cover"、"thumbnail"、"关键帧"。
---

# 封面/首帧生成

从视频中提取高冲击力帧作为封面候选。投流素材的封面直接影响点击率。

## 前置条件

- FFmpeg 已安装
- `.env` 中配置 `ARK_API_KEY`（用于 AI 评分，可选）

## 工作流程

### 第一步：生成封面候选

```bash
# 生成 12 张候选封面（默认）
python3 scripts/gen_cover.py video/output/promo_final.mp4

# 生成更多候选
python3 scripts/gen_cover.py video.mp4 -n 20

# 跳过 AI 评分（更快）
python3 scripts/gen_cover.py video.mp4 --no-ai

# 自定义输出目录
python3 scripts/gen_cover.py video.mp4 -o covers/
```

### 第二步：查看结果

脚本输出 `covers_{视频名}.json`，包含：
- 所有候选帧的路径和时间戳
- AI 评分和推荐理由（如果启用）
- Top 3 推荐封面

候选帧图片保存在 `cover_candidates/` 子目录。

### AI 评分维度

1. **视觉冲击力** -- 画面是否吸引眼球
2. **情绪张力** -- 是否有强烈情绪表达
3. **信息量** -- 画面是否有趣/有悬念
4. **构图质量** -- 人物清晰度、画面协调性

## 提取策略

- 偏前期采样（前 40% 时长采样更密集）
- 投流视频的前几秒决定点击率，所以优先从开头附近选封面
- AI 综合评分后排序推荐

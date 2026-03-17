---
name: multi-platform-export
description: >
  一键将视频导出为多个投放平台所需的不同规格（抖音/快手/视频号/头条/朋友圈）。
  在以下场景使用：(1) 导出多平台视频规格，(2) 视频裁切为竖屏/方形，(3) 批量生成不同时长版本。
  触发关键词："多平台导出"、"抖音规格"、"竖屏"、"方形视频"、"平台适配"、"导出"。
---

# 多平台规格导出

一键将投流素材导出为多个平台的标准规格。

## 前置条件

- FFmpeg 已安装
- 输入视频文件

## 支持平台

| 平台 | 比例 | 分辨率 | 时长版本 |
|------|------|--------|---------|
| 抖音/快手 | 9:16 | 1080x1920 | 15s, 30s, 60s |
| 微信视频号 | 9:16 | 1080x1920 | 30s, 60s, 180s |
| 微信视频号 3:4 | 3:4 | 1080x1440 | 30s, 60s |
| 头条/穿山甲 | 16:9 | 1920x1080 | 60s, 120s, 180s |
| 朋友圈广告 | 1:1 | 1080x1080 | 15s, 30s |

## 工作流程

```bash
# 导出所有平台所有规格
python3 scripts/platform_export.py video/output/promo_final.mp4

# 只导出抖音和朋友圈
python3 scripts/platform_export.py video.mp4 -p douyin moments

# 自定义输出目录
python3 scripts/platform_export.py video.mp4 -o exports/

# 查看所有平台
python3 scripts/platform_export.py --list-platforms
```

## 裁切策略

- 横屏→竖屏：智能居中裁切（保留画面中心区域）
- 竖屏→横屏：居中裁切或加黑边
- 任意→方形：居中裁切

## 输出

导出的文件命名格式：`{原始名}_{平台}_{时长}.mp4`

同时生成 `{原始名}_exports.json` 清单文件，方便自动化上传。

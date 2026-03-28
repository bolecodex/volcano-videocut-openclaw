---
name: 漫剧视频全流程
description: >
  一句话生成漫剧：故事扩写、角色/场景/道具图、分镜、短片生成与最终合成；可选配音与字幕。
  产物在 .yiwa/<project_id>/；分阶段说明见 reference/。
trigger: 漫剧、动态漫画、故事视频、自动分镜、网文漫改
---

# motion-comics-production（漫剧生成）

目标：把“故事想法”变成可交付的漫剧视频（含分镜、画面、动效视频片段、可选配音与字幕）。

## 使用前请阅读

- [安装与环境配置](./reference/安装与环境配置.md)
- [工作流程总览](./reference/工作流程.md)
- [阶段 1：剧本与资产](./reference/阶段1-剧本与资产.md)
- [阶段 2：分镜脚本](./reference/阶段2-分镜脚本.md)
- [阶段 3：素材图生成（角色/道具/场景）](./reference/阶段3-素材图生成.md)
- [阶段 4：分镜图生成](./reference/阶段4-分镜图生成.md)
- [阶段 5：视频片段生成](./reference/阶段5-视频片段生成.md)
- [阶段 6：合成输出](./reference/阶段6-合成输出.md)
- [恢复与排错](./reference/恢复与排错.md)

## 工作流程

从技能目录（也就是 SKILL.md 所在目录）执行脚本，产物会写入当前目录下的 `.yiwa/<project_id>/...`。

阶段与脚本对应关系（详细操作见 reference）：

1. 剧本与资产：`expand-script.js` →（生成 JSON）→ `save-script-info.js`
2. 分镜脚本：`expand-storydoard-script.js` →（逐帧确认）→ `save-storyboards.js`
3. 素材图：`generate-image.js`（角色/道具/场景）
4. 分镜图：`generate-storyboard.js`（必要时 `modify-storyboard.js`）
5. 视频片段：`generate-video.js`
6. 配音与字幕（可选）：`generate-audio.js`、`generate-subtitle.js`
7. 合成输出：`compose-video.js`

## 注意事项

1. 每个阶段完成后必须展示结果并等待用户确认，不要自动进入下一阶段。
2. 需要你生成 JSON 的阶段（剧本、分镜）必须严格只输出 JSON，不要夹带解释文字。
3. 统一从技能目录执行命令；不要在 `scripts/` 目录里运行，否则 `.yiwa/` 可能落到错误位置。
4. `.env` 写在 `motion-comics-production/.env`（参考 `.env.example`）；不要把 Key/Token 明文输出到对话中。
5. 禁止为该技能临时生成新的脚本写入仓库；只使用 `scripts/` 里已有脚本。
6. 命令失败时，直接回显错误信息与可重试的命令，不要静默跳过。

## 恢复中断的项目

用户提供 `project_id` 时，先运行进度查看，再按 `stage` 回到对应阶段继续（详见 [恢复与排错](./reference/恢复与排错.md)）。

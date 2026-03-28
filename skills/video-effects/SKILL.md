---
name: 视频花字与动效包装
description: >
  为视频添加花字、卡片、人物条、章节标题等动效；支持多主题，先分析画面生成建议清单，用户确认后再渲染叠加。
  须先安装依赖并生成字幕；禁止向本 skill 内写入新脚本。详见 reference/。
trigger: 花字、动效、人物条、章节条、视频包装、Remotion
---

## 使用前请阅读

- [安装](./reference/install.md)
- [详细工作流程](./reference/workflow.md)
- [动效清单与规范](./reference/effects.md)
- [主题系统](./reference/themes.md)

## 工作流程
1. 安装依赖。
2. 生成字幕。
3. 参考动效使用规范生成建议。
4. 渲染动效视频。
5. 动效叠加原视频输出成片。

## 注意事项

1. 必须先生成字幕并给出建议清单，等待用户确认后再渲染。
2. 生成 config.json 时保持内容语言与字幕一致。
3. 禁止生成新的脚本写入到skill中

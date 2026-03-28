# 工作流程（搭配命令行）

## 第一步：生成字幕

执行以下命令生成字幕文件（默认输出到项目根目录下的 temp 目录）。

```bash
python3 scripts/gen_subtitle.py video.mp4
```

## 第二步：生成特效建议

1. 根据 effects.md 的规范与输出格式生成特效建议（人物条、章节标题、花字、名词卡片、金句卡片、数据动画、要点列表、社交媒体条），输出建议清单并等待用户审核。

2. 用户审核特效建议，可以删除、修改、新增特效建议。

3. 用户审核通过后，生成 config.json。该文件格式参考 effects.md 中的说明，config.json 也应放在项目根目录下的 temp 目录。

4. 用 FFmpeg 获取视频宽高并注入 config.json。

获取视频宽高的命令可参考：

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 video.mp4
```

将输出结果写入 config.json 的 videoInfo 字段，例如：

```json
{
  "videoInfo": {
    "width": 1280,
    "height": 720
  }
}
```

## 第三步：渲染动效视频

```bash
node scripts/remotion-templates/render.mjs config.json
```

根据 config.json，渲染透明动效视频，输出目录为项目根目录下的 temp。

## 第四步：动效叠加原视频输出成片

```bash
python3 scripts/video_processor.py video.mp4 temp/config.json temp output.mp4
```

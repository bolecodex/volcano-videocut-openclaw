# doubao-seedream 图片生成（文生图）使用规范

本文件基于根目录 `文生图.md`，仅保留与本 Skill 相关的要点，并补充本项目约定。

## 1. 模型能力简述

- **文生图**：根据文本提示词生成单张图片；
- **文生组图**：根据文本提示词生成一组内容关联的图片；
- **图生图 / 多图生图**：根据一张或多张参考图 + 文本提示词生成风格统一的新图。

本 Skill 主要使用：

- 单图文生图：生成角色三视图（正面 / 侧面 / 背面）、**场景图**、**道具图**；
- 文生组图：可生成多张核心场景参考图。

**一致性要求**：场景图与道具图须**根据剧本/资产列表**生成（见 `reference/参考图生成规则.md`），保证与分镜中的 `scene`、`props` 一致。

## 2. 关键参数

- `model`：如 `doubao-seedream-4.0`；
- `prompt`：文本提示词，建议不超过 300 字；
- `image`：可选，作为参考图的 URL 或 Base64；
- `size`：
  - 推荐 `2K`，由模型根据描述推断具体宽高；
- `sequential_image_generation`：
  - `"disabled"`：单图模式；
  - `"auto"`：组图模式；
- `sequential_image_generation_options.max_images`：
  - 组图时生成的最大张数；
- `response_format`：
  - 建议使用 `"url"`；
- `watermark`：
  - 默认 `true`。

完整字段与限制（图片格式、尺寸等）详见根目录 `文生图.md`。

## 3. 推荐调用模式

### 3.1 角色三视图（正面 / 侧面 / 背面）

为保证视频中人物的一致性，建议对同一角色生成三视图：

- 使用相同的 `model`、`size` 和基础风格描述；
- 仅在 prompt 中切换视角描述：
  - `front view, character turnaround front`
  - `side view, character turnaround side`
  - `back view, character turnaround back`

示例请求体（伪代码）：

```json
{
  "model": "doubao-seedream-4.0",
  "prompt": "cartoon style, chinese office worker pig character, front view, character turnaround front, high detail, consistent with MV style",
  "size": "2K",
  "sequential_image_generation": "disabled",
  "response_format": "url",
  "watermark": true
}
```

生成结果建议写入：

- `output_dir/character_views/front.png`
- `output_dir/character_views/side.png`
- `output_dir/character_views/back.png`

并在分镜 JSON 中引用这些路径，用于后续视频生成的参考。

### 3.2 核心场景组图

对于 MV 中多次出现的关键场景（如办公室 / 地铁 / 家等），可以使用组图模式一次生成多张风格统一的参考图：

```json
{
  "model": "doubao-seedream-4.0",
  "prompt": "night city office, commuting, emotional mood, consistent with MV style, multiple shots",
  "size": "2K",
  "sequential_image_generation": "auto",
  "sequential_image_generation_options": {
    "max_images": 5
  },
  "response_format": "url",
  "watermark": true
}
```

生成结果建议写入：

- `output_dir/key_scenes/scene_01.png` 等。

### 3.3 与视频生成的衔接

- 角色三视图与场景图应作为 Seedance 或其它视频模型的参考：
  - 若视频接口支持 `image_url` 作为 `first_frame` / `last_frame`，应优先使用；
  - 若只支持文本 prompt，应在 prompt 中显式加入「同角色三视图」/「同场景组图」的描述。

## 4. 注意事项

沿用模型的通用限制（格式、像素、大小等）：

- 支持的图片格式：jpeg、png、webp、bmp、tiff、gif；
- 宽高比范围：[1/16, 16]；
- 总像素不超过 3600 万；
- 参考图数量 + 输出图数量 ≤ 15 张。


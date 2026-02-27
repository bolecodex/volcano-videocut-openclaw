---
name: novel-01-character-extractor
description: 从剧本中提取所有角色，生成标准角色风格卡（三行结构），包含不可变特征和可引用ID。当需要提取角色、建立角色库、生成角色描述时使用。
---

# 角色提取器

从剧本中提取所有角色，生成 YAML 角色资产文件，并通过脚本生成 HTML 可视化展示页面。

## 核心原则

- **不可变特征冻结**：脸型/发型/服装/主配色/标志道具/气质作为"硬约束"
- **三行结构强制**：风格/形象/视图，不可省略
- **ID 唯一可检索**：每个角色必须有唯一 ID，格式统一
- **数据与展示分离**：YAML 存数据，脚本生 HTML

## 项目目录确定规则（必须首先执行）

> **这是最关键的一步，所有产物都必须放在正确的项目目录下。**

### 什么是 `{项目目录}`

每个剧本拥有独立的项目子目录，位于 **workspace 根目录**下，**不是 workspace 根目录本身**。

```
{workspace根目录}/
├── {剧本简称}/          ← 这就是 {项目目录}
│   ├── style.yaml
│   ├── {剧本简称}_角色资产.yaml
│   ├── {剧本简称}_角色展示.html
│   ├── scenes/
│   └── shots/
├── 另一个剧本/
│   └── ...
└── 剧本原文.md          ← 剧本原文可以在根目录
```

### 如何确定 `{剧本简称}`

从剧本标题中提取简短名称，作为目录名和文件前缀：

| 剧本标题 | 剧本简称 | 项目目录 |
|----------|---------|---------|
| 全班穿成NPC，我把宫斗玩成总动员 | 全班穿成NPC | `{workspace}/全班穿成NPC/` |
| 杀猪匠夫君 | 杀猪匠夫君 | `{workspace}/杀猪匠夫君/` |
| 剑来之陈风传 | 剑来之陈风传 | `{workspace}/剑来之陈风传/` |

规则：
- 取剧本标题的**前半部分**或**核心名词**，去掉副标题、标点
- 长度控制在 2-8 个字
- 若用户已有同名目录，直接复用

### 执行前必须检查

1. **检查 `{项目目录}` 是否存在** → 不存在则 `mkdir -p` 创建
2. **检查 `{项目目录}/style.yaml` 是否存在** → 不存在则创建（参考已有项目或根据剧本风格新建，使用下方默认模板）
3. **所有输出产物**（YAML、HTML）都**必须写入 `{项目目录}/` 下**，禁止写在 workspace 根目录

### 默认 style.yaml 模板

创建新项目的 `style.yaml` 时，**图片和视频默认均使用 9:16 竖版**（适配抖音/快手竖屏内容）：

```yaml
version: "1.0"

style_base: >-
  真人写实高清，超细节刻画，光影细腻，氛围感拉满，
  服饰纹理清晰，面部神态精准

style_base_character: >-
  真人写实高清，超细节刻画，光影细腻，
  服饰纹理清晰，面部神态精准

negative_prompt: >-
  低质量，模糊，变形，多余手指，文字水印，
  过度曝光，卡通风格，2D平面

image_sizes:
  character:
    preset: "portrait_16_9"
    description: "角色全身立绘，9:16 竖版，白底设定图"
  storyboard:
    preset: "portrait_16_9"
    description: "分镜头配图，9:16 竖版"
  scene:
    preset: "portrait_16_9"
    description: "场景图，9:16 竖版"

video:
  aspect_ratio: "9:16"
  resolution: "720p"
  duration_default: "5"
  fps: 24
```

> **关于 9:16 默认值**：所有图片尺寸（角色立绘、分镜配图、场景图）和视频比例默认都使用 9:16 竖版，这是当前短视频平台（抖音、快手等）的标准格式。如需横版内容可手动改为 `landscape_16_9`。

---

## 输入要求

### 必填
- **剧本正文**：包含角色出场、对白、动作描写
- **`{项目目录}/style.yaml`**：全局风格配置文件，从中读取 `style_base`（绘画风格词）、`image_sizes.character`（角色立绘尺寸，默认 9:16）和 `video`（视频配置，默认 9:16）

### 可选
- **已有角色卡**：若已有，优先沿用，不改 ID
- **角色参考图**：用于锁定外形细节

### 读取 style.yaml

执行前必须先读取项目的 `style.yaml`，提取以下字段：

```python
style_base = style_yaml['style_base']                       # 全局风格词（用于场景/分镜）
style_base_character = style_yaml.get('style_base_character', '')  # 角色立绘专用风格词
char_image_size = style_yaml['image_sizes']['character']['preset']  # 角色立绘尺寸，默认 portrait_16_9（9:16）
negative_prompt = style_yaml.get('negative_prompt', '')      # 负面提示词（可选）

# 视频相关配置
video_aspect_ratio = style_yaml.get('video', {}).get('aspect_ratio', '9:16')  # 视频比例，默认 9:16
video_duration = style_yaml.get('video', {}).get('duration_default', '5')      # 默认时长（秒）

# 若 style_base_character 为空，则从 style_base 自动剥离氛围/色调/背景词
if not style_base_character:
    # 保留纯画质词，剥离会诱导背景的词
    # 详见 format-rules.md 第6节
    pass
```

> **重要区分**：
> - `style_base` = 完整风格词，包含氛围/色调/光线，用于**场景配图和分镜绘图**
> - `style_base_character` = 角色立绘专用风格词，**只含画质词**，不含任何氛围/色调/光线/背景词
>
> **为什么要区分？** 角色立绘需要纯白背景，但 `style_base` 中的氛围词（如"宫廷华丽色调""暖黄宫灯光线""氛围感拉满"）会严重干扰白底效果，诱导模型生成场景背景、多人画面、摄影棚环境等问题。
>
> 角色资产 YAML 的 `style` 字段记录 `style_base` 快照（用于展示），但 `prompt` 字段必须使用 `style_base_character`。

---

## 输出产物

> **所有产物必须在 `{项目目录}/` 下，禁止输出到 workspace 根目录。**

```
{workspace根目录}/{剧本简称}/          ← {项目目录}
├── style.yaml                        # 全局风格配置（若不存在需先创建）
├── {剧本简称}_角色资产.yaml           # 核心产物：结构化角色数据
└── {剧本简称}_角色展示.html           # 由脚本从 YAML 生成的可视化页面
```

### 具体示例

假设 workspace 为 `/Users/me/codes/project`，剧本标题为「全班穿成NPC，我把宫斗玩成总动员」：

```
/Users/me/codes/project/
├── 全班穿成NPC/                      ← {项目目录}
│   ├── style.yaml
│   ├── 全班穿成NPC_角色资产.yaml
│   └── 全班穿成NPC_角色展示.html
└── npc.md                            ← 剧本原文（在根目录）
```

### 生成顺序

1. **确定 `{项目目录}`，检查并创建目录和 `style.yaml`**
2. **提取角色 → 输出 YAML 文件到 `{项目目录}/`**（核心数据）
3. **调用脚本 → 生成 HTML 展示页面到 `{项目目录}/`**（可视化）
4. **`open` 命令打开 HTML 预览**

---

## 提取流程

### 步骤 0：确定项目目录（最先执行）

1. 从剧本标题提取 `{剧本简称}`（参见上方"项目目录确定规则"）
2. 设定 `{项目目录}` = `{workspace根目录}/{剧本简称}/`
3. 若 `{项目目录}` 不存在 → `mkdir -p {项目目录}`
4. 若 `{项目目录}/style.yaml` 不存在 → 根据剧本风格创建
5. 读取 `{项目目录}/style.yaml`，提取 `style_base`、`style_base_character`、`image_sizes`（默认 9:16）、`video`（默认 9:16）等字段

> **后续所有步骤中的文件读写，都必须基于 `{项目目录}` 路径。**

### 步骤 1：扫描剧本角色

从剧本中提取所有出场角色：
- 主角（戏份最多）
- 重要配角（多场出现）
- 次要角色（单场或少量出现）
- 群演角色（甲/乙/丙）

### 步骤 2：分析角色信息

对每个角色提取：
- 姓名/称呼
- 年龄/性别
- 外形描写（剧本中的）
- 服装描写
- 性格/气质
- 与其他角色关系
- 标志性动作/口头禅

### 步骤 3：生成角色风格卡

按三行结构为每个角色输出风格卡（见下方 YAML 格式中的 `style` / `description` / `view` 字段）。

### 步骤 4：提取不可变特征

确定 3-7 条不可变特征，用于保持跨镜头一致性。

### 步骤 5：生成角色图片

使用角色提示词（`prompt` 字段）调用图像生成模型，获取角色立绘图片 URL，写入 `image_url` 字段。

**图片尺寸**：从 `style.yaml` 的 `image_sizes.character.preset` 读取，默认使用 `portrait_16_9`（9:16 竖版白底立绘，适配抖音/快手竖屏）。

**角色立绘提示词规范（必须遵守）**：
1. prompt 必须以 `solo, single character,` 开头，防止出现多人
2. 风格词使用 `style_base_character`（纯画质词），**禁止**使用 `style_base` 中的氛围/色调/光线词
3. 背景描述使用 `solid pure white background，no background elements`，双重强化白底
4. 结尾添加 `character design reference sheet，ultra detailed` 锁定设定图格式
5. 详细模板见 [format-rules.md](references/format-rules.md) 第6节

### 步骤 6：输出 YAML 角色资产文件

将所有角色数据写入 `{剧本名}_角色资产.yaml`，格式见下方。

### 步骤 7：运行脚本生成 HTML

```bash
python {skill_dir}/scripts/generate_gallery.py \
  --input "{项目目录}/{剧本名}_角色资产.yaml"
```

脚本自动：
- 读取 YAML 数据
- 加载 HTML 模板
- 生成 `{剧本名}_角色展示.html`（与 YAML 同目录）

### 步骤 8：打开预览

```bash
open "{项目目录}/{剧本名}_角色展示.html"
```

---

## YAML 角色资产格式

### 完整结构

```yaml
# {剧本名}_角色资产.yaml
version: "1.0"
project_name: "{项目名}"
style_ref: "style.yaml"                    # 指向全局风格配置（style_base 从那里读取）
generated_at: "2026-02-07T12:00:00"
total_characters: 4

characters:
  # ── 主角 ──
  - id: "@szj_suwan"
    name: 苏晚
    type: 主角
    first_appearance: SC_01
    style: "真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满..."
    description: "18岁女性，乌发如缎及肩简单束起，杏眼清亮，肤若凝脂，粗布襦裙，袖口挽起，眼神坚韧中带哀伤，气质温婉坚韧"
    view: "白底全身设定图"
    immutable_features:
      - 乌发如缎及肩简单束起
      - 杏眼清亮，肤若凝脂
      - 粗布襦裙，袖口挽起
      - 眼神坚韧中带哀伤
      - 气质温婉坚韧
    prompt: "solo, single character, 真人写实高清，超细节刻画，古风人像写实，光影细腻，服饰纹理清晰，面部神态精准，18岁亚洲女性，乌发如缎及肩简单束起，杏眼清亮，肤若凝脂，粗布襦裙，袖口挽起，气质温婉坚韧，正面站立，面对镜头，全身像，双手自然下垂，solid pure white background，no background elements，character design reference sheet，ultra detailed"
    image_url: ""
    image_status: pending    # pending / completed / failed

  # ── 配角 ──
  - id: "@szj_renyazi"
    name: 人牙子
    type: 配角
    first_appearance: SC_04
    style: "..."
    description: "中年男性，尖嘴猴腮，谄媚笑容，破旧长袍，油滑市井气质"
    view: "白底全身设定图"
    immutable_features:
      - 尖嘴猴腮
      - 谄媚笑容
      - 破旧长袍
      - 油滑市井气质
    prompt: "..."
    image_url: ""
    image_status: pending

  # ── 群演 ──
  - id: "@szj_jiefang"
    name: 街坊
    type: 群演
    first_appearance: SC_02
    style: "..."
    description: "中年女性，粗布衣裳，八卦神情，市井妇女"
    view: "白底全身设定图"
    immutable_features:
      - 粗布衣裳
      - 八卦神情
      - 市井妇女形象
    prompt: "..."
    image_url: ""
    image_status: pending
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | string | 是 | 格式版本号 |
| `project_name` | string | 是 | 项目/剧本名称 |
| `style_ref` | string | 是 | 指向全局风格配置文件路径（`style.yaml`） |
| `generated_at` | string | 是 | 生成时间 ISO 格式 |
| `total_characters` | int | 是 | 角色总数 |
| `characters` | list | 是 | 角色列表 |

### 角色字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 角色唯一 ID，格式 `@{项目缩写}_{拼音}` |
| `name` | string | 是 | 角色名称 |
| `type` | string | 是 | 角色类型：主角/配角/群演/特殊 |
| `first_appearance` | string | 否 | 首次出场场景 ID |
| `style` | string | 是 | 三行结构-风格行（引用 STYLE_BASE） |
| `description` | string | 是 | 三行结构-形象行（年龄/发型/面部/体型/服装/气质） |
| `view` | string | 是 | 三行结构-视图行 |
| `immutable_features` | list | 是 | 不可变特征列表（3-7 条） |
| `prompt` | string | 是 | 完整角色提示词（可直接用于生图） |
| `image_url` | string | 否 | 生成图片的 URL |
| `image_status` | string | 否 | 图片状态：pending/completed/failed |

---

## ID 命名规范

### 格式
```
@{项目缩写}_{角色拼音或英文}
```

### 示例
- `@jl_chenfeng` - 剑来-陈风
- `@jl_ningyu` - 剑来-宁雨
- `@cbpk_lina` - 赛博朋克-莉娜
- `@dushi_zhangsan` - 都市-张三

### 规则
- 全小写
- 下划线分隔
- 项目缩写 2-4 字母
- 角色名拼音或英文
- 同名角色加数字后缀：`@jl_xiaoer_1`

---

## 角色类型模板

### 主角模板

```yaml
  - id: "@jl_chenfeng"
  name: 陈风
  type: 主角
  first_appearance: SC_01
  style: "真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准，青绿山水色调，仙侠清冷氛围"
  description: "20岁男性，剑眉星目，黑发束冠，身形修长挺拔，白色仙袍金边点缀，腰佩青锋剑，气质清冷如玉"
  view: "白底全身设定图"
  immutable_features:
    - 黑发束冠，发丝根根分明
    - 剑眉星目，眼神清冷
    - 白色仙袍，金边装饰
    - 腰佩青锋剑，剑穗白色
    - 身形修长，肩宽腰窄
    - 气质清冷出尘
  prompt: "solo, single character, 真人写实高清，超细节刻画，古风人像写实，光影细腻，服饰纹理清晰，面部神态精准，20岁亚洲男性，剑眉星目，黑发束冠，身形修长挺拔，白色仙袍金边点缀，腰佩青锋剑，气质清冷如玉，正面站立，面对镜头，全身像，双手自然下垂，solid pure white background，no background elements，character design reference sheet，ultra detailed"
  image_url: ""
  image_status: pending
```

### 配角模板

```yaml
- id: "@jl_ningyu"
  name: 宁雨
  type: 配角
  first_appearance: SC_03
  style: "真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准，青绿山水色调，仙侠清冷氛围"
  description: "18岁女性，柳眉杏眼，黑发如瀑及腰，身材纤细，淡紫色襦裙，手持玉笛，气质温婉灵动"
  view: "白底全身设定图"
  immutable_features:
    - 黑发如瀑及腰
    - 柳眉杏眼，眼神温柔
    - 淡紫色襦裙，绣花装饰
    - 手持白玉笛
    - 身材纤细，气质温婉
  prompt: "..."
  image_url: ""
  image_status: pending
```

### 群演模板

```yaml
- id: "@jl_huwei_jia"
  name: 护卫甲
  type: 群演
  first_appearance: SC_05
  style: "真人写实高清，超细节刻画，古风人像写实，光影细腻，青绿山水色调"
  description: "30岁男性，国字脸，短发，黑色劲装，腰佩长刀，神情肃穆"
  view: "白底全身设定图"
  immutable_features:
    - 黑色劲装统一制服
    - 腰佩长刀
    - 神情肃穆
  prompt: "..."
  image_url: ""
  image_status: pending
```

---

## 特殊角色处理

### 系统/AI 角色

```yaml
- id: "@jl_system"
  name: 系统
  type: 特殊
  style: "真人写实高清，超细节刻画，光影细腻，青蓝科技光效"
  description: "无实体，以光幕/悬浮文字/语音形式出现，青蓝色半透明界面"
  view: "无"
  immutable_features:
    - 光幕：青蓝色半透明面板
    - 文字：发光字体，带科技感边框
    - 语音：电子合成音，无画面
  prompt: ""
  image_url: ""
  image_status: pending
```

### 妖兽/非人类

```yaml
- id: "@jl_xuelang"
  name: 血狼
  type: 特殊
  style: "真人写实高清，超细节刻画，光影细腻，暗红血腥色调"
  description: "巨型妖狼，通体漆黑，双眼泛红光，利爪如刀，獠牙外露，黑雾缭绕"
  view: "白底妖形全身设定图"
  immutable_features:
    - 通体漆黑皮毛
    - 双眼泛红光
    - 利爪如刀
    - 黑雾缭绕
  prompt: "..."
  image_url: ""
  image_status: pending
```

---

## HTML 展示生成

### 脚本位置

```
scripts/generate_gallery.py
```

### 使用方法

```bash
# 基本用法（自动推导输出路径）
python scripts/generate_gallery.py --input "{项目目录}/{剧本名}_角色资产.yaml"

# 指定输出路径
python scripts/generate_gallery.py \
  --input "{项目目录}/{剧本名}_角色资产.yaml" \
  --output "{项目目录}/{剧本名}_角色展示.html"

# 指定自定义模板
python scripts/generate_gallery.py \
  --input "{项目目录}/{剧本名}_角色资产.yaml" \
  --template "path/to/custom_template.html"
```

### 脚本参数

| 参数 | 缩写 | 必填 | 说明 |
|------|------|------|------|
| `--input` | `-i` | 是 | 角色资产 YAML 文件路径 |
| `--template` | `-t` | 否 | HTML 模板路径（默认使用 skill 内置模板） |
| `--output` | `-o` | 否 | 输出 HTML 路径（默认: YAML 同目录下 `{项目名}_角色展示.html`） |

### 模板位置

```
assets/templates/gallery.html
```

### 生成后操作

```bash
# 打开生成的展示页面
open "{项目目录}/{剧本名}_角色展示.html"
```

---

## 质量检查

生成 YAML 后必须自检：
- [ ] **所有产物是否在 `{项目目录}/` 下？**（不得在 workspace 根目录）
- [ ] `{项目目录}/style.yaml` 是否存在？
- [ ] 是否所有角色都有唯一 ID？
- [ ] 三行结构是否完整（style / description / view）？
- [ ] 不可变特征是否足够具体可视化（3-7 条）？
- [ ] 风格是否引用 STYLE_BASE？
- [ ] 角色提示词是否可直接用于生图？
- [ ] YAML 格式是否合法（缩进、引号）？

---

## 与下游 skill 的数据衔接

### _manifest.yaml 中的 characters 字段

`novel-03-scenes-to-storyboard` 生成的 `_manifest.yaml` 会包含 `characters` 字段，其数据应从本 skill 输出的 YAML 提取：

```yaml
# _manifest.yaml 中的角色索引（简化版）
characters:
  - id: "@szj_suwan"
    name: 苏晚
    type: 主角
    prompt_ref: "18岁女性，乌发如缎及肩..."
```

### novel-04 绘图时的角色图片映射

`novel-04-shots-to-images` 需要从角色资产 YAML 的 `image_url` 字段提取角色图片映射：

```python
# 伪代码
for char in yaml_data['characters']:
    if char['image_url'] and char['image_status'] == 'completed':
        角色图片映射[char['id']] = char['image_url']
```

---

## 额外资源

- 角色描述规则：[format-rules.md](references/format-rules.md)
- HTML 模板：[gallery.html](assets/templates/gallery.html)
- 生成脚本：[generate_gallery.py](scripts/generate_gallery.py)

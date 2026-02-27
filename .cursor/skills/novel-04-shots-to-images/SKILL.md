---
name: novel-04-shots-to-images
description: 将分镜头数据转换为 AI 绘画图像。读取 shots/*.yaml 分镜文件，使用 Seedream 4.5 模型进行图生图绘画，保持角色和场景一致性。当用户想要绘制分镜、生成镜头图片、将分镜转为图像时使用此 skill。
---

# 分镜头图像生成

使用 Seedream 4.5 模型将分镜头数据转换为 AI 绘画图像，保持角色和场景的一致性。

## 项目目录定位规则（必须首先执行）

> **本 skill 的所有读写操作都基于 `{项目目录}`，不是 workspace 根目录。**

`{项目目录}` 是 workspace 根目录下以剧本简称命名的子目录，由上游 skill 创建：

```
{workspace根目录}/
├── {剧本简称}/          ← 这就是 {项目目录}
│   ├── style.yaml
│   ├── shots/
│   └── ...
└── 剧本原文.md
```

### 如何定位

1. 用户指定了项目名 → 直接使用 `{workspace}/{项目名}/`
2. 用户未指定 → 列出 workspace 下的子目录，找到包含 `shots/` 和 `style.yaml` 的目录
3. **禁止**在 workspace 根目录下直接读写产物文件

---

## 工作流程

```
任务进度：
- [ ] 步骤 1：读取资产清单
- [ ] 步骤 2：选择场景
- [ ] 步骤 3：生成镜头图像
- [ ] 步骤 4：自动更新状态并展示结果
```

---

## 步骤 1：读取资产清单

读取以下文件获取资源索引：

```
{项目目录}/style.yaml                    # 全局风格配置（最重要）
{项目目录}/shots/_manifest.yaml          # 分镜索引
{项目目录}/{剧本名}_角色资产.yaml        # 角色图片
```

### 1.1 从 `style.yaml` 提取（优先级最高）

```python
style_base = style_yaml['style_base']                              # 全局风格词
image_size = style_yaml['image_sizes']['storyboard']['preset']     # 分镜图尺寸（如 portrait_16_9）
negative_prompt = style_yaml.get('negative_prompt', '')            # 负面提示词
```

> **重要**：`style_base` 是保证全剧画风一致的唯一数据源。所有镜头的风格词都从 `style.yaml` 读取，会覆盖分镜 yaml 里写死的风格词。修改画风只需改 `style.yaml` 这一处。

### 1.2 从 `_manifest.yaml` 提取

- `characters`: 角色 ID 与提示词映射
- `files`: 所有场景分镜文件列表

### 1.3 从角色资产 YAML 提取角色图片 URL 映射表

```python
# 从 {剧本名}_角色资产.yaml 提取
角色图片映射 = {}
for char in yaml_data['characters']:
    if char.get('image_url') and char.get('image_status') == 'completed':
        角色图片映射[char['id']] = char['image_url']
```

---

## 步骤 2：选择场景

向用户展示可用场景列表，让用户选择要绘制的场景：

```
可用场景：
1. SC_01_开篇悬念 (2 镜头)
2. SC_02_西市日常 (5 镜头)
3. SC_03_苏府抄家 (5 镜头)
...

请选择要绘制的场景编号（或输入 "all" 绘制全部）：
```

读取选中场景的分镜文件 `shots/SC_XX_场景名.yaml`。

---

## 步骤 3：生成镜头图像

对每个镜头执行以下操作：

### 3.1 提取镜头信息

从 shot 数据中提取：
- `id`: 镜头 ID
- `characters`: 角色列表（包含 ref, action, emotion）
- `prompt`: 预设的画面提示词
- `composition`: 构图信息
- `mood`: 氛围
- `lighting`: 光照

### 3.1.1 风格词替换（关键步骤）

**必须执行**：用 `_manifest.yaml` 的 `style_base` 替换分镜 prompt 里的风格词，确保全局风格一致。

**替换规则**：
1. 分镜 prompt 的第一行通常是风格词（如 `2.5D国风动画...` 或 `真人写实高清...`）
2. 识别并移除 prompt 第一行中的风格相关词汇
3. 用 `style_base` 替换

**风格词识别模式**（正则）：
```
^(2\.?5D国风动画|2D国风|国风动画|真人写实高清|真人写实|写实古装|古风人像写实).*?(，|,)\s*
```

**替换伪代码**：
```python
# 从 _manifest.yaml 读取的全局风格
style_base = "真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准，动态自然，暖黄色的光线，背景虚化氛围感强"

# 原始 prompt（分镜 yaml 里写死的）
original_prompt = shot.prompt

# 移除原始风格词（第一行到场景描述之前）
# 通常以"简陋卧房"、"肉铺内"等场景词开头的才是内容部分
import re
content_start_pattern = r'(简陋|卧房|肉铺|西市|街口|庭院|书房|大殿|牢房|城门|.{2,4}内，|.{2,4}外，)'
match = re.search(content_start_pattern, original_prompt)
if match:
    content_part = original_prompt[match.start():]
else:
    # 保险：跳过第一行
    content_part = '\n'.join(original_prompt.split('\n')[1:])

# 组装最终 prompt
final_prompt = f"{style_base}，{content_part}"
```

**示例**：
- 原始 prompt: `2.5D国风动画，暗金市井色调，工笔细腻材质，油灯侧逆光，简陋卧房内，...`
- style_base: `真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准，动态自然，暖黄色的光线，背景虚化氛围感强`
- 最终 prompt: `真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准，动态自然，暖黄色的光线，背景虚化氛围感强，简陋卧房内，...`

### 3.2 查找角色参考图

根据 `characters[].ref` 查找角色图片 URL：

```python
# 伪代码
character_images = []
for char in shot.characters:
    if char.ref.startswith("@"):  # 主要角色
        image_url = 角色图片映射[char.ref]
        character_images.append(image_url)
```

### 3.3 构建图生图提示词

使用 Seedream 4.5 的多图引用语法：

```
Figure 1 是 [角色1名称] 的参考图，Figure 2 是 [角色2名称] 的参考图。
生成画面：[原始 prompt]
确保 Figure 1 的人物出现在画面中，[角色1动作描述]。
确保 Figure 2 的人物出现在画面中，[角色2动作描述]。
```

### 3.4 调用 Seedream 4.5

使用 MCP 工具 `generate`：

```json
{
  "model": "fal-ai/bytedance/seedream/v4.5/edit",
  "prompt": "[构建的提示词]",
  "image_size": "[从 style.yaml → image_sizes.storyboard.preset 读取]",
  "options": {
    "image_urls": ["[角色1图片URL]", "[角色2图片URL]"]
  }
}
```

**无角色参考图时**（如群演、纯场景镜头），使用文生图：

```json
{
  "model": "fal-ai/bytedance/seedream/v4.5/text-to-image",
  "prompt": "[原始 prompt]",
  "image_size": "[从 style.yaml → image_sizes.storyboard.preset 读取]"
}
```

> **图片尺寸统一**：所有分镜配图的 `image_size` 从 `style.yaml` 的 `image_sizes.storyboard.preset` 读取，保证全剧尺寸一致。

### 3.5 查询任务结果

使用 `get_result` 查询结果，获取生成的图片 URL。

---

## 步骤 4：自动更新状态并展示结果

生成完成后，**立即自动更新** YAML 文件，无需等待用户确认。

### 4.1 更新分镜 YAML 文件

每个镜头生成成功后，立即更新对应的分镜 YAML 文件：

```yaml
- id: "SC_01_001"
  # ... 其他字段保持不变
  image_path: "SC_01_开篇悬念/shot_001.png"
  image_status: completed
  image_url: "https://生成的图片URL"
  generated_at: "2026-02-05T14:30:00"
```

### 4.2 更新 manifest

同时更新 `_manifest.yaml` 中的 `images_ready` 计数。

### 4.3 展示结果

更新完成后，展示生成结果：

```markdown
## 场景 SC_01_开篇悬念 生成完成

### 镜头 SC_01_001: 秘密揭示
![镜头001](生成的图片URL)
- 角色：苏晚（坐在床边凝视）、陈屠（熟睡中）
- 状态：✅ 已写入 YAML

### 镜头 SC_01_002: 决绝握手
![镜头002](生成的图片URL)
- 角色：苏晚、陈屠
- 状态：✅ 已写入 YAML

---
✅ 已自动更新 YAML 文件
如需重新生成某个镜头，请告诉我镜头编号。
```

---

## 提示词模板

### 单角色镜头

```
Figure 1 是 {角色名} 的参考图。
{style_base}，{场景描述}，{场景光照}，
Figure 1 的人物 {角色动作}，{角色情绪表情}，
{镜头类型}镜头，{构图描述}，{氛围}，高清细节
```

### 双角色镜头

```
Figure 1 是 {角色1名} 的参考图，Figure 2 是 {角色2名} 的参考图。
{style_base}，{场景描述}，{场景光照}，
Figure 1 的人物 {角色1动作}，{角色1情绪}，
Figure 2 的人物 {角色2动作}，{角色2情绪}，
{镜头类型}镜头，{构图描述}，{氛围}，高清细节
```

### 特写镜头（聚焦细节）

```
Figure 1 是 {角色名} 的参考图。
{style_base}，{特写内容描述}，
特写镜头，聚焦 {焦点}，{背景虚化描述}，
{氛围}，高清细节，精细材质渲染
```

---

## 参数说明

### image_size 选择（从 style.yaml 读取）

图片尺寸统一从 `style.yaml → image_sizes.storyboard.preset` 读取：

| preset 值 | 宽高比 | 适用场景 |
|-----------|--------|---------|
| `landscape_16_9` | 16:9 横版 | B站、YouTube、电影短片 |
| `portrait_16_9` | 9:16 竖版 | 抖音、快手、小红书 |
| `portrait_4_3` | 3:4 竖版 | 小红书图文、微信视频号 |
| `square` | 1:1 方形 | 微信朋友圈 |

> **重要**：不在本 skill 中硬编码尺寸，统一由 `style.yaml` 控制，保证全剧所有镜头尺寸一致。

### 模型选择

| 场景 | 模型 |
|-----|------|
| 有角色参考图 | `fal-ai/bytedance/seedream/v4.5/edit` |
| 无参考图 | `fal-ai/bytedance/seedream/v4.5/text-to-image` |

---

## 完整示例

### 示例：生成 SC_01 第一个镜头

**镜头数据：**
```yaml
- id: "SC_01_001"
  title: "秘密揭示"
  shot_type: "中景"
  characters:
    - ref: "@szj_suwan"
      action: 坐在床边凝视熟睡的陈屠
      emotion: 神秘、若有所思
    - ref: "@szj_chentu"
      action: 熟睡中，眉头紧锁
      emotion: 梦魇
```

**构建的提示词：**
```
Figure 1 是苏晚的参考图，Figure 2 是陈屠的参考图。
真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准，动态自然，暖黄色的光线，背景虚化氛围感强，
简陋卧房内，木板床，厚棉被，油灯摇曳，暗角氛围，
Figure 1 的人物侧坐床边，乌发及肩简单束起，粗布襦裙，
神情神秘若有所思，凝视着Figure 2，
Figure 2 的人物躺在床上熟睡中，眉头紧锁，做着噩梦，
中景镜头，三分构图，暖黄色调，高清细节
```

**API 调用：**
```json
{
  "model": "fal-ai/bytedance/seedream/v4.5/edit",
  "prompt": "Figure 1 是苏晚的参考图，Figure 2 是陈屠的参考图...",
  "image_size": "portrait_16_9",
  "options": {
    "image_urls": [
      "https://p16-dreamina-sign-sg.ibyteimg.com/.../苏晚.jpeg",
      "https://p16-dreamina-sign-sg.ibyteimg.com/.../陈屠.jpeg"
    ]
  }
}
```

---

## 批量生成策略

### 单场景模式（推荐）

1. 一次生成一个场景的所有镜头
2. 生成完成后**立即自动写入 YAML**
3. 展示结果，继续下一场景

### 全量生成模式

1. 批量生成所有场景
2. 每完成一个镜头**立即写入 YAML**
3. 每完成一个场景输出进度
4. 失败的镜头记录下来最后统一重试

---

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 角色图片 URL 失效 | 提示用户重新生成角色图片 |
| 生成超时 | 自动重试 1 次，仍失败则跳过并记录 |
| 内容审核失败 | 调整提示词，移除敏感词后重试 |
| 角色无参考图 | 回退到文生图模式，使用角色文字描述 |

---

## 步骤 5：刷新可视化页面

完成图像生成后，**必须**运行脚本刷新 HTML 可视化页面，让新生成的图片在页面中展示：

```bash
python {novel-03-skill目录}/scripts/generate_storyboard.py --project "{项目目录}/"
```

> 该脚本读取所有 `shots/*.yaml` 中的最新数据（包括刚写入的 `image_url`），重新生成 `{项目目录}/index.html`。

```bash
open "{项目目录}/index.html"
```

**页面展示内容**：
- 所有镜头的生成图片（点击可全屏查看）
- 图片生成状态标签（待生图/已生图）
- 统计面板：已生图/总镜头数
- 搜索、过滤、一键复制提示词等交互功能

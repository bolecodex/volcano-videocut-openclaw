# 输出格式说明

## 前置输入

本 skill 需要 **novel-02-script-to-scenes** 的输出作为输入：

```
{项目目录}/
├── {剧本名}_场景索引.yaml      # 必需
└── scenes/                      # 必需
    ├── SC_01_场景名.md
    └── ...
```

---

## 输出产物

采用 **场景级独立文件** 架构，每个场景对应一个分镜 YAML 文件：

```
{项目目录}/
├── {剧本名}_场景索引.yaml      # 原有（不修改）
├── index.html                   # 新增：可视化查看器
├── scenes/                      # 原有（不修改）
└── shots/                       # 新增：分镜文件目录
    ├── _manifest.yaml           # 分镜索引（列出所有分镜文件）
    ├── SC_01_开篇悬念.yaml      # 场景01的分镜
    ├── SC_02_西市日常.yaml      # 场景02的分镜
    ├── ...
    ├── SC_01_开篇悬念/          # 场景01的配图目录
    │   ├── shot_001.png
    │   └── shot_002.png
    └── SC_02_西市日常/          # 场景02的配图目录
        └── ...
```

**命名规则：**

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 分镜文件 | `{场景ID}_{场景名}.yaml` | `SC_01_开篇悬念.yaml` |
| 配图目录 | `{场景ID}_{场景名}/` | `SC_01_开篇悬念/` |
| 配图文件 | `shot_{序号}.png` | `shot_001.png` |

**优势：**
- 单场景独立修改，不影响其他场景
- Git diff 更清晰，便于版本管理
- 支持并行生成多个场景的分镜
- 增量更新时只需重新生成变化的场景

---

## 分镜数据格式

### 1. 分镜索引文件 `_manifest.yaml`

```yaml
# shots/_manifest.yaml
# 分镜索引文件，列出所有分镜文件及统计信息

version: "1.0"
script_name: 杀猪匠的使命
style_base: 真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准，动态自然，暖黄色的光线，背景虚化氛围感强
source_script: 杀猪匠的使命_对话脚本.md
scene_index: 杀猪匠的使命_场景索引.yaml
character_asset: 杀猪匠的使命_角色资产.md
generated_at: "2026-02-04T10:30:00"
total_scenes: 25
total_shots: 120

# 角色索引（从角色资产提取或新建）
characters:
  - id: "@szj_chentu"
    name: 陈屠
    type: 主角
    prompt_ref: "28岁男性，短发蓬乱乌黑，剑眉浓重..."
  - id: "@szj_suwan"
    name: 苏晚
    type: 主角
    prompt_ref: "18岁女性，乌发如缎及肩..."

# 分镜文件列表
files:
  - file: "SC_01_开篇悬念.yaml"
    scene_id: "SC_01"
    scene_name: "开篇悬念"
    shots_count: 4
    images_ready: 0
  - file: "SC_02_西市日常.yaml"
    scene_id: "SC_02"
    scene_name: "西市日常"
    shots_count: 6
    images_ready: 2
  # ...按场景顺序列出所有文件
```

### 2. 单场景分镜文件 `SC_XX_场景名.yaml`

```yaml
# shots/SC_01_开篇悬念.yaml
# 单个场景的分镜数据

scene_id: "SC_01"
scene_name: "开篇悬念"
scene_ref: "scenes/SC_01_开篇悬念.md"
scene_type: "prologue"
scene_description: "卧房，油灯摇曳，夜晚"
scene_mood: "神秘悬疑"
scene_lighting: "油灯暖光"

shots:
  - id: "SC_01_001"
    title: "苏晚床边凝视"
    shot_type: "中景"
    
    script_lines:
      start: 24
      end: 30
    
    characters:
      - ref: "@szj_suwan"
        action: 侧坐床边
        emotion: 决绝
      - ref: "@szj_chentu"
        action: 熟睡中
        emotion: 眉头紧锁
    
    composition:
      angle: 平视
      focus: 苏晚
    
    mood: 紧张、神秘、决绝
    lighting: 油灯侧逆光
    
    lines:
      - speaker: 旁白
        text: 我那夫君，有个秘密。
      - speaker: 旁白
        text: 他杀的，不止是猪。
      - speaker: 旁白
        text: 每晚噩梦，他都会念出一个名字。
      - speaker: 旁白
        text: 第二天，那名字的主人必定暴毙。
      - speaker: 旁白
        text: 直到那晚他在梦中吐出害死我爹的仇人的名字——
      - speaker: 旁白
        text: 我颤抖着握住他的手，
      - speaker: 苏晚
        text: 夫君，今晚，替我多砍几刀。
        emotion: 颤抖、决绝
    
    prompt: |
      真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准，动态自然，暖黄色的光线，背景虚化氛围感强，
      简陋卧房内，木板床，厚棉被，油灯摇曳，
      苏晚(@szj_suwan)侧坐床边，乌发及肩简单束起，粗布襦裙，
      低头凝视熟睡中眉头紧锁的陈屠(@szj_chentu)，
      一只手轻轻覆在陈屠手上，眼神坚韧中带决绝，
      中景镜头，三分构图，暖色调，高清细节
    
    image_path: "SC_01_开篇悬念/shot_001.png"
    image_status: pending
    
  - id: "SC_01_002"
    title: "苏晚握手特写"
    shot_type: "特写"
    # ...
```

### 字段说明

**_manifest.yaml 字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | string | ✅ | 格式版本 |
| `script_name` | string | ✅ | 剧本名称 |
| `style_base` | string | ⬜ | 统一风格描述 |
| `generated_at` | string | ✅ | 生成时间 |
| `total_scenes` | number | ✅ | 总场景数 |
| `total_shots` | number | ✅ | 总镜头数 |
| `characters` | array | ⬜ | 角色索引列表 |
| `files` | array | ✅ | 分镜文件列表 |

**单场景分镜文件字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `scene_id` | string | ✅ | 场景ID |
| `scene_name` | string | ✅ | 场景名称 |
| `scene_ref` | string | ✅ | 场景文件路径 |
| `shots` | array | ✅ | 镜头列表 |

**镜头（shot）字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 镜头唯一标识，格式 `SC_XX_NNN` |
| `title` | string | ✅ | 镜头标题，简短描述内容 |
| `shot_type` | string | ✅ | 景别（特写/中景/全景/远景） |
| `script_lines` | object | ✅ | 对应脚本行号范围 |
| `characters` | array | ✅ | 出场角色列表 |
| `composition` | object | ⬜ | 构图信息 |
| `mood` | string | ✅ | 情绪氛围 |
| `lighting` | string | ⬜ | 光线描述 |
| `lines` | array | ✅ | 台词列表 |
| `prompt` | string | ✅ | 配图提示词 |
| `image_path` | string | ✅ | 图片存储路径（相对于 shots/） |
| `image_status` | string | ✅ | 图片状态 |

### 图片状态值

| 状态 | 说明 |
|------|------|
| `pending` | 待生成 |
| `generated` | 已生成，待审核 |
| `approved` | 已审核通过 |
| `rejected` | 已拒绝，需重新生成 |

### 构图信息字段

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `shot_type` | 景别 | 特写、中景、全景、远景 |
| `angle` | 视角 | 平视、俯视、仰视 |
| `focus` | 焦点 | 主要聚焦的角色或元素 |
| `background` | 背景 | 背景描述（可选） |

---

## HTML 查看器

采用 **数据与展示分离** 架构，HTML 作为通用查看器，动态读取 `shots/` 目录下的 YAML 文件渲染。

### 使用方式

**自动加载（推荐）**

HTML 会自动加载 `shots/_manifest.yaml`，然后并行加载所有分镜文件：

```
杀猪匠的使命/
├── index.html                   ← 查看器
└── shots/
    ├── _manifest.yaml           ← 索引文件（首先加载）
    ├── SC_01_开篇悬念.yaml      ← 并行加载
    ├── SC_02_西市日常.yaml      ← 并行加载
    └── ...
```

**URL 参数**

```
# 查看指定场景
index.html?scene=SC_01

# 跳转到指定镜头
index.html#SC_01_002
```

### 启动本地服务器

```bash
# Python 3
python -m http.server 8080

# Node.js
npx serve .

# PHP
php -S localhost:8080
```

然后访问：`http://localhost:8080/杀猪匠的使命/`

### 功能特性

- 🔍 **搜索**：搜索台词、角色、场景
- 🏷️ **过滤**：按图片状态过滤（待生图/已生图）
- 🖼️ **放大**：点击图片可全屏查看
- 📋 **复制**：一键复制配图提示词
- 📊 **统计**：显示镜头数、台词数等统计
- 🎯 **导航**：快速跳转到指定镜头
- ⌨️ **快捷键**：`/` 聚焦搜索，`Esc` 关闭弹窗

---

## 数据流转

```
场景索引.yaml + scenes/*.md
            │
            ▼
┌─────────────────────────────────────┐
│  novel-03-scenes-to-storyboard       │
│  - 遍历场景文件                      │
│  - 单场景内划分镜头                  │
│  - 生成配图提示词                    │
│  - 输出场景级分镜YAML                │
└─────────────────────────────────────┘
            │
            ├──► shots/_manifest.yaml（索引）
            ├──► shots/SC_01_xxx.yaml（场景1分镜）
            ├──► shots/SC_02_xxx.yaml（场景2分镜）
            │    ...
            └──► index.html（查看器）
                      │
                      ▼
┌─────────────────────────────────────┐
│      index.html（通用查看器）        │
│  1. fetch() 读取 _manifest.yaml     │
│  2. 并行加载所有场景分镜文件         │
│  3. js-yaml 解析                    │
│  4. JavaScript 动态渲染             │
└─────────────────────────────────────┘
```

### 迭代工作流

1. **首次生成**：运行 skill 生成分镜数据 + 复制 HTML
2. **查看效果**：启动本地服务器，浏览器打开 HTML
3. **迭代修改**：编辑单个场景的 YAML 文件，刷新浏览器即可
4. **图片生成**：生成图片后放入对应场景的子目录，更新 `image_status`
5. **增量更新**：重新生成时只覆盖变化的场景文件，自动更新 manifest

---

## 目录结构总览

完整产物目录结构：

```
{项目目录}/
├── {剧本名}_场景索引.yaml        # novel-02-script-to-scenes 产物
├── index.html                     # novel-03-scenes-to-storyboard 产物
├── scenes/                        # novel-02-script-to-scenes 产物
│   ├── SC_01_开篇悬念.md
│   ├── SC_02_西市日常.md
│   └── ...
└── shots/                         # novel-03-scenes-to-storyboard 产物
    ├── _manifest.yaml             # 分镜索引
    ├── SC_01_开篇悬念.yaml        # 场景1分镜
    ├── SC_02_西市日常.yaml        # 场景2分镜
    ├── ...
    ├── SC_01_开篇悬念/            # 场景1配图目录
    │   ├── shot_001.png
    │   └── shot_002.png
    └── SC_02_西市日常/            # 场景2配图目录
        ├── shot_001.png
        └── ...
```

相关文件（可放在同目录或上级目录）：
```
├── {剧本名}_对话脚本.md          # 原始脚本
└── {剧本名}_角色资产.md          # 角色设定（如有）
```

---

## 场景与分镜文件对应关系

```
scenes/                          shots/
├── SC_01_开篇悬念.md    ──────►  ├── SC_01_开篇悬念.yaml
├── SC_02_西市日常.md    ──────►  ├── SC_02_西市日常.yaml
├── SC_03_苏府抄家.md    ──────►  ├── SC_03_苏府抄家.yaml
└── ...                          └── ...
```

文件名保持一一对应，便于追溯和管理。

# 输出格式说明

## 文件命名规范

```
{项目目录}/
├── {剧本名}_场景索引.yaml      # 核心数据文件
└── scenes/                      # 场景文件目录
    ├── SC_01_场景名.md
    ├── SC_02_场景名.md
    └── ...
```

示例：
```
杀猪匠的使命/
├── 杀猪匠的使命_场景索引.yaml
└── scenes/
    ├── SC_01_开篇悬念.md
    ├── SC_02_西市日常.md
    ├── SC_03_苏府抄家.md
    └── ...
```

---

## 场景索引格式

### 完整结构

```yaml
# 杀猪匠的使命_场景索引.yaml

# 元数据
meta:
  title: 杀猪匠的使命
  source_script: 杀猪匠的使命_对话脚本.md
  character_asset: 杀猪匠的使命_角色资产.md  # 可选
  total_scenes: 29
  total_lines: 612
  avg_lines_per_scene: 21
  created_at: 2026-02-04

# 类型统计
type_summary:
  reality: 23
  flashback: 3
  dream: 2
  montage: 2
  prologue: 1

# 场景列表
scenes:
  - id: SC_01
    name: 开篇悬念
    type: prologue
    location: 卧房
    time_period: 某晚
    script_lines:
      start: 24
      end: 30
    line_count: 7
    main_characters:
      - 苏晚
      - 陈屠
    mood: 神秘、悬疑
    notes: 预告性质hook，与SC_25-26呼应
    warnings: []

  - id: SC_02
    name: 西市日常
    type: reality
    location: 猪肉铺
    time_period: 白天
    script_lines:
      start: 32
      end: 47
    line_count: 16
    main_characters:
      - 苏晚
      - 陈屠
      - 街坊甲
      - 街坊乙
    mood: 市井、苦涩
    notes: 引出苏晚身世，触发闪回
    warnings: []

  - id: SC_03
    name: 苏府抄家
    type: flashback
    location: 苏府→人市
    time_period: 过去（抄家当日）
    time_reference: 苏家被抄那日  # 闪回专用
    script_lines:
      start: 49
      end: 58
    line_count: 10
    main_characters:
      - 苏晚
    mood: 悲凉、绝望
    notes: null
    warnings: []

  - id: SC_12
    name: 血雾世界
    type: dream
    location: 梦境血界
    time_period: 梦中
    script_lines:
      start: 172
      end: 191
    line_count: 20
    main_characters:
      - 陈屠
      - 苏晚
      - 猪人怪物
    mood: 恐怖、超现实
    visual_style: 血红色调，雾气翻涌，无明确光源  # 梦境专用
    notes: 苏晚首次进入陈屠梦境
    warnings: []

  - id: SC_19
    name: 坦白盟约
    type: reality
    location: 里屋
    time_period: 紧接上一场
    script_lines:
      start: 317
      end: 357
    line_count: 41
    main_characters:
      - 苏晚
      - 陈屠
    mood: 紧张→释然→坚定
    notes: 包含照顾、坦白、倾诉、立约四个情节段
    warnings:
      - "台词数>35，建议复核是否需要拆分"
      - "包含多个情绪转折点"

  - id: SC_24
    name: 清洗蒙太奇
    type: montage
    location: 铺子/卧房
    time_period: 一个月
    time_span: 一个月        # 蒙太奇专用
    estimated_shots: 6-8     # 蒙太奇专用
    script_lines:
      start: 487
      end: 499
    line_count: 13
    main_characters:
      - 苏晚
      - 陈屠
    mood: 紧张、肃杀
    notes: 多个暴毙事件并置，需要快切节奏
    warnings: []
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 场景唯一标识，格式 SC_XX |
| `name` | string | ✅ | 场景标题，简短描述内容 |
| `type` | enum | ✅ | 场景类型：reality/flashback/dream/montage/prologue |
| `location` | string | ✅ | 地点描述 |
| `time_period` | string | ✅ | 时间段描述 |
| `script_lines` | object | ✅ | 对应脚本行号范围 {start, end} |
| `line_count` | number | ✅ | 台词条数 |
| `main_characters` | array | ✅ | 主要出场角色 |
| `mood` | string | ⬜ | 情绪氛围 |
| `notes` | string | ⬜ | 备注说明 |
| `warnings` | array | ⬜ | 警告信息列表 |

### 特殊类型专用字段

| 类型 | 专用字段 | 说明 |
|------|----------|------|
| flashback | `time_reference` | 闪回的时间参考点（如"苏家被抄那日"） |
| dream | `visual_style` | 梦境的视觉风格提示 |
| montage | `time_span` | 蒙太奇的时间跨度 |
| montage | `estimated_shots` | 预估的快切镜头数 |

---

## 场景文件格式

每个场景输出为独立的 Markdown 文件：`scenes/SC_XX_场景名.md`

### 文件结构

```markdown
# SC_12_血雾世界.md

## 场景元信息

| 字段 | 值 |
|------|------|
| 场景ID | SC_12 |
| 场景名 | 血雾世界 |
| 类型 | 梦境 |
| 地点 | 梦境血界（无边无际的血色雾气空间） |
| 时间 | 梦中 |
| 主要角色 | 陈屠、苏晚（旁观者）、猪人怪物（王文远） |
| 情绪基调 | 恐怖、超现实、震撼 |
| 视觉风格 | 血红色调，雾气翻涌，无明确光源 |
| 脚本行号 | 172-191 |
| 台词数 | 20 |
| 前接场景 | SC_11（苏晚触摸陈屠额头） |
| 后接场景 | SC_13（苏晚从梦境退出） |

---

## 对话内容

旁白：眼前的卧房消失了，我坠入一片无边无际的血色雾气中，
旁白：雾气中央，陈屠站在那里，
旁白：他手持一把铺子里一模一样的剔骨刀，眼神空洞，
...（后续台词）
```

### 元信息字段说明

| 字段 | 说明 |
|------|------|
| 场景ID | 与场景索引中的 id 一致 |
| 场景名 | 与场景索引中的 name 一致 |
| 类型 | 现实/闪回/梦境/蒙太奇/预告 |
| 地点 | 详细的地点描述 |
| 时间 | 时间段描述 |
| 主要角色 | 出场角色列表 |
| 情绪基调 | 该场景的整体情绪 |
| 视觉风格 | 梦境/闪回等特殊场景的视觉提示 |
| 脚本行号 | 在原脚本中的行号范围 |
| 台词数 | 该场景包含的台词条数 |
| 前接场景 | 上一个场景的ID和简述 |
| 后接场景 | 下一个场景的ID和简述 |

---

## 目录结构示例

完整的场景切分产物：

```
杀猪匠的使命/
├── 杀猪匠的使命_场景索引.yaml
└── scenes/
    ├── SC_01_开篇悬念.md
    ├── SC_02_西市日常.md
    ├── SC_03_苏府抄家.md
    ├── SC_04_人市被买.md
    ├── SC_05_新婚之夜.md
    ├── SC_06_日子过渡.md
    ├── SC_07_雨夜惊梦.md
    ├── SC_08_雨后清晨.md
    ├── SC_09_观察期.md
    ├── SC_10_李三之死.md
    ├── SC_11_梦境初探.md
    ├── SC_12_血雾世界.md
    ├── SC_13_守护秘密.md
    ├── SC_14_苏晚实验_晚饭.md
    ├── SC_15_苏晚实验_夜.md
    ├── SC_16_钱扒皮死讯.md
    ├── SC_17_前夫挑衅.md
    ├── SC_18_道士探查.md
    ├── SC_19_坦白盟约.md
    ├── SC_20_刺客来袭.md
    ├── SC_21_炉火疗伤.md
    ├── SC_22_街口被捕.md
    ├── SC_23_太子书房.md
    ├── SC_24_清洗蒙太奇.md
    ├── SC_25_决战前夜.md
    ├── SC_26_梦斗魏忠贤.md
    ├── SC_27_魏党突袭.md
    ├── SC_28_皇城面圣.md
    └── SC_29_一年后尾声.md
```

---

## 后续流程

场景切分完成后，使用 **novel-03-scenes-to-storyboard** skill 进行分镜划分：

```
novel-02-script-to-scenes  →  对话脚本 + 场景索引 + 场景文件
                                       ↓
                               （可人工调整）
                                       ↓
novel-03-scenes-to-storyboard  →  分镜数据 + HTML查看器
```

---
name: novel-05-shots-to-audio
description: 将分镜头数据转换为配音音频。读取 shots/*.yaml 分镜文件，使用 Minimax TTS 为每条台词生成配音，支持固定角色音色映射。当用户想要为分镜配音、生成台词音频、制作有声内容时使用此 skill。
---

# 分镜头配音生成

使用 Minimax TTS 将分镜头台词转换为配音音频，保持角色音色一致性。

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
- [ ] 步骤 2：确认音色映射
- [ ] 步骤 3：选择场景
- [ ] 步骤 4：生成台词配音
- [ ] 步骤 5：更新状态
```

---

## 步骤 1：读取资产清单

读取分镜索引文件：

```
{项目目录}/shots/_manifest.yaml
```

提取以下信息：
- `voice_mapping`: 角色-音色映射表（若无则需创建）
- `files`: 所有场景分镜文件列表
- `characters`: 角色 ID 与名称映射

---

## 步骤 2：确认音色映射

### 2.1 检查已有映射

若 `_manifest.yaml` 中存在 `voice_mapping` 字段，展示给用户确认：

```
当前音色映射：
┌──────────┬──────────────────────────────────────────┬──────────────┐
│ 角色     │ 音色 ID                                   │ 音色名       │
├──────────┼──────────────────────────────────────────┼──────────────┤
│ 旁白     │ Chinese (Mandarin)_Male_Announcer        │ 播报男声     │
│ 苏晚     │ female-yujie-jingpin                     │ 御姐音色-beta │
│ 陈屠     │ male-qn-badao-jingpin                    │ 霸道青年音色  │
└──────────┴──────────────────────────────────────────┴──────────────┘

是否使用此映射？[Y/n]
```

### 2.2 创建默认映射

若无映射，使用默认配置并写入 `_manifest.yaml`：

```yaml
# 新增到 _manifest.yaml
voice_mapping:
  旁白:
    voice_id: "Chinese (Mandarin)_Male_Announcer"
    voice_name: "播报男声"
    description: "沉稳权威的叙事者"
  苏晚:
    voice_id: "female-yujie-jingpin"
    voice_name: "御姐音色-beta"
    description: "18岁温婉坚韧女性"
  陈屠:
    voice_id: "male-qn-badao-jingpin"
    voice_name: "霸道青年音色-beta"
    description: "28岁沉稳带杀气男性"
  赵衍:
    voice_id: "Chinese (Mandarin)_Gentleman"
    voice_name: "温润男声"
    description: "高贵儒雅病弱太子"
  沈清河:
    voice_id: "male-qn-qingse-jingpin"
    voice_name: "青涩青年音色-beta"
    description: "轻佻嫌恶的前夫"
  道士:
    voice_id: "Chinese (Mandarin)_Reliable_Executive"
    voice_name: "沉稳高管"
    description: "中年阴鸷道士"
  _default_male:
    voice_id: "male-qn-jingying-jingpin"
    voice_name: "精英青年音色-beta"
  _default_female:
    voice_id: "female-chengshu"
    voice_name: "成熟女性音色"
```

### 2.3 更换角色音色

若用户需要更换音色，调用 MCP 工具 `speak` 获取可用音色列表：

```python
# 获取可用音色列表
voices = speak(action="list_voices")
chinese_voices = [v for v in voices['public_voices'] 
                  if '中文' in v.get('tags', [])]
```

展示供用户选择：

```
可用中文音色：
1. male-qn-qingse - 青涩青年音色 [青年/男]
2. male-qn-jingying - 精英青年音色 [青年/男]
3. male-qn-badao - 霸道青年音色 [青年/男]
4. female-shaonv - 少女音色 [青年/女]
5. female-yujie - 御姐音色 [青年/女]
...

请输入编号选择音色：
```

---

## 步骤 3：选择场景

展示可用场景列表：

```
可用场景：
┌────┬─────────────────────┬────────┬────────┬────────────┐
│ #  │ 场景名               │ 镜头数 │ 台词数 │ 配音状态   │
├────┼─────────────────────┼────────┼────────┼────────────┤
│ 1  │ SC_01_开篇悬念       │ 2      │ 7      │ 0/7 未完成 │
│ 2  │ SC_02_西市日常       │ 5      │ 20     │ 0/20 未完成│
│ 3  │ SC_03_苏府抄家       │ 5      │ 25     │ 0/25 未完成│
└────┴─────────────────────┴────────┴────────┴────────────┘

请选择场景编号（或 "all" 全部配音）：
```

读取选中场景的分镜文件 `shots/SC_XX_场景名.yaml`。

---

## 步骤 4：生成台词配音

对每个镜头的每条台词执行：

### 4.1 提取台词信息

从 shot 数据中提取 `lines` 字段：

```yaml
lines:
  - speaker: 旁白
    text: 我那夫君，有个秘密。
  - speaker: 苏晚
    text: 夫君，今晚，替我多砍几刀。
    emotion: 颤抖、决绝
```

### 4.2 匹配音色

```python
def get_voice_id(speaker, voice_mapping):
    """获取角色对应的音色 ID"""
    if speaker in voice_mapping:
        return voice_mapping[speaker]['voice_id']
    # 未映射角色使用默认音色
    return voice_mapping.get('_default_male', {}).get('voice_id')
```

### 4.3 调用 TTS API

使用 MCP 工具 `speak`：

```python
result = speak(
    action="synthesize",
    text=line.text,
    voice_id=voice_id,
    model="speech-2.8-hd"       # 高质量模型
)
audio_url = result['audio_url']
```

**参数说明**：

| 参数 | 值 | 说明 |
|-----|-----|------|
| `action` | `synthesize` | 语音合成操作 |
| `text` | string | 要合成的文本（最大 10000 字符） |
| `voice_id` | string | 音色 ID（通过 `action=list_voices` 获取） |
| `model` | `speech-2.8-hd` | 高质量模型，支持语气词标签 |
| `speed` | 0.5-2.0 | 语速，默认 1.0（可选） |

### 4.4 处理情绪标签（可选）

若台词有 `emotion` 字段，可使用 speech-2.8 支持的语气词标签：

```python
EMOTION_TAGS = {
    '笑': '(laughs)',
    '叹气': '(sighs)',
    '哭': '(crying)',
    '愤怒': '(angry)',
    '颤抖': '(trembling voice)',
}

def apply_emotion(text, emotion):
    """在文本中添加语气词标签"""
    if not emotion:
        return text
    for key, tag in EMOTION_TAGS.items():
        if key in emotion and tag:
            return f"{tag} {text}"
    return text
```

### 4.5 更新分镜数据

将生成的音频 URL 写入对应 line：

```yaml
lines:
  - speaker: 旁白
    text: 我那夫君，有个秘密。
    audio_url: "https://cdn.minimax.chat/audio/xxx.mp3"   # 新增
    audio_status: completed                               # 新增
  - speaker: 苏晚
    text: 夫君，今晚，替我多砍几刀。
    emotion: 颤抖、决绝
    audio_url: "https://cdn.minimax.chat/audio/yyy.mp3"
    audio_status: completed
```

### 4.6 展示进度

```
[SC_01_001] 生成中... 4/4 ✓
  ├─ 旁白: "我那夫君，有个秘密。" ✓
  ├─ 旁白: "他杀的，不止是猪。" ✓
  ├─ 旁白: "每晚噩梦，他都会念出一个名字。" ✓
  └─ 旁白: "第二天，那名字的主人必定暴毙。" ✓

[SC_01_002] 生成中... 3/3 ✓
  ├─ 旁白: "直到那晚他在梦中吐出..." ✓
  ├─ 旁白: "我颤抖着握住他的手，" ✓
  └─ 苏晚: "夫君，今晚，替我多砍几刀。" ✓
```

---

## 步骤 5：更新状态

### 5.1 结果展示

生成完成后，展示结果供用户确认：

```markdown
## 场景 SC_01_开篇悬念 配音结果

### 镜头 SC_01_001: 秘密揭示

| # | 说话人 | 台词 | 音色 | 试听 |
|---|--------|------|------|------|
| 1 | 旁白 | 我那夫君，有个秘密。 | 播报男声 | [▶️](url1) |
| 2 | 旁白 | 他杀的，不止是猪。 | 播报男声 | [▶️](url2) |
| 3 | 旁白 | 每晚噩梦，他都会念出一个名字。 | 播报男声 | [▶️](url3) |
| 4 | 旁白 | 第二天，那名字的主人必定暴毙。 | 播报男声 | [▶️](url4) |

### 镜头 SC_01_002: 决绝握手

| # | 说话人 | 台词 | 情绪 | 音色 | 试听 |
|---|--------|------|------|------|------|
| 1 | 旁白 | 直到那晚他在梦中吐出... | - | 播报男声 | [▶️](url5) |
| 2 | 旁白 | 我颤抖着握住他的手， | - | 播报男声 | [▶️](url6) |
| 3 | 苏晚 | 夫君，今晚，替我多砍几刀。 | 颤抖、决绝 | 御姐音色 | [▶️](url7) |

---
请确认是否满意？
- [满意] 继续下一场景
- [重新生成] 重新生成指定台词（输入编号）
- [更换音色] 更换某角色音色后重新生成
```

### 5.2 更新分镜 YAML

用户确认后，更新分镜文件（已在 4.5 步骤完成）。

### 5.3 更新 _manifest.yaml

更新索引文件中的配音统计：

```yaml
files:
  - file: "SC_01_开篇悬念.yaml"
    scene_id: "SC_01"
    scene_name: "开篇悬念"
    shots_count: 2
    images_ready: 2
    audio_ready: 7       # 新增：已完成配音数
    audio_total: 7       # 新增：总台词数
```

---

## 完整示例

### 示例：生成 SC_01 第一条台词

**输入数据**：
```yaml
- speaker: 旁白
  text: 我那夫君，有个秘密。
```

**音色查找**：
```python
voice_id = voice_mapping['旁白']['voice_id']
# => "Chinese (Mandarin)_Male_Announcer"
```

**API 调用**：
```python
result = speak(
    action="synthesize",
    text="我那夫君，有个秘密。",
    voice_id="Chinese (Mandarin)_Male_Announcer",
    model="speech-2.8-hd"
)
```

**返回结果**：
```json
{
  "audio_url": "https://cdn.minimax.chat/audio/abc123.mp3",
  "duration": 2.5,
  "characters": 9
}
```

**更新 YAML**：
```yaml
- speaker: 旁白
  text: 我那夫君，有个秘密。
  audio_url: "https://cdn.minimax.chat/audio/abc123.mp3"
  audio_status: completed
```

---

## 批量生成策略

### 单场景模式（推荐）

1. 一次生成一个场景的所有台词配音
2. 展示结果供用户确认
3. 确认后再进行下一场景

### 全量生成模式

1. 用户确认后批量生成所有场景
2. 每完成一个场景输出进度
3. 失败的台词记录下来最后统一重试

---

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 角色无音色映射 | 使用默认音色，并警告用户 |
| TTS API 超时 | 自动重试 2 次，仍失败则跳过并记录 |
| 余额不足 | 提示用户充值，暂停任务 |
| 文本过长 | 拆分文本分段生成后合并 |

---

## 费用说明

Minimax TTS 按字符计费：

| 模型 | 价格 | 说明 |
|------|------|------|
| speech-2.8-hd | 3.5元/万字符 | 高质量，支持语气词 |
| speech-2.8-turbo | 2元/万字符 | 速度快，性价比高 |

**字符计算规则**：
- 1 汉字 = 2 字符
- 英文/标点 = 1 字符

**预估费用示例**：
- 场景 SC_01（7条台词，约100字）≈ 200字符 ≈ 0.07元

---

## 步骤 6：刷新可视化页面

完成配音生成后，**必须**运行脚本刷新 HTML 可视化页面，让音频播放器在页面中展示：

```bash
python {novel-03-skill目录}/scripts/generate_storyboard.py --project "{项目目录}/"
```

> 该脚本读取所有 `shots/*.yaml` 中的最新数据（包括刚写入的 `audio_url`），重新生成 `{项目目录}/index.html`。

```bash
open "{项目目录}/index.html"
```

**页面展示内容**：
- 每条台词旁的音频播放器（如有 `audio_url`）
- 统计面板：已配音/总台词数
- 搜索台词文本，快速定位

---

## 音色参考

详见 [references/voice-mapping.md](references/voice-mapping.md)

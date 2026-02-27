# 分镜数据结构说明

## 分镜索引 (_manifest.yaml)

```yaml
version: "2.0"
script_name: 杀猪匠的使命
style_base: 真人写实高清，超细节刻画，古风人像写实，光影细腻...（示例）

# 角色索引
characters:
  - id: "@szj_chentu"
    name: 陈屠
    type: 主角
    prompt_ref: "28岁男性，身材高大魁梧..."

# 分镜文件列表
files:
  - file: "SC_01_开篇悬念.yaml"
    scene_id: "SC_01"
    scene_name: "开篇悬念"
    shots_count: 2
    images_ready: 0
```

## 单场景分镜 (SC_XX_场景名.yaml)

```yaml
scene_id: "SC_01"
scene_name: "开篇悬念"
scene_ref: "scenes/SC_01_开篇悬念.md"
scene_type: "prologue"  # prologue/reality/flashback/dream/montage
scene_description: "简陋卧房，油灯摇曳，夜晚"
scene_mood: "神秘、悬疑"
scene_lighting: "油灯侧逆光，暖黄昏暗"

shots:
  - id: "SC_01_001"
    title: "秘密揭示"
    shot_type: "中景"  # 远景/全景/中景/近景/特写
    
    script_lines:
      start: 24
      end: 27
    
    characters:
      - ref: "@szj_suwan"      # 角色 ID
        action: 坐在床边凝视    # 角色动作
        emotion: 神秘、若有所思  # 角色情绪
    
    composition:
      angle: 平视              # 平视/俯视/仰视
      focus: 苏晚侧脸          # 聚焦对象
      background: 油灯摇曳的简陋卧房
    
    mood: 神秘、悬疑
    lighting: 油灯侧逆光
    
    lines:                      # 对应台词
      - speaker: 旁白
        text: 我那夫君，有个秘密。
    
    prompt: |                   # 预设提示词
      真人写实高清，超细节刻画，古风人像写实...
    
    image_path: "SC_01_开篇悬念/shot_001.png"
    image_status: pending       # pending/completed/failed
```

## 角色资产文件 (杀猪匠的使命_角色资产.md)

角色信息块格式：
```markdown
### 陈屠 (@szj_chentu)

- **风格：**真人写实高清...
- **形象：**陈屠 (@szj_chentu) 28岁男性...
- **视图：**白底全身设定图

**角色提示词：**
```
真人写实高清...
```

**生成图片：**
![陈屠](https://p16-dreamina-sign-sg.ibyteimg.com/...)
```

## 角色图片 URL 提取正则

```regex
!\[([^\]]+)\]\((https://p\d+-dreamina-sign-sg\.ibyteimg\.com/[^)]+)\)
```

提取结果映射到角色 ID：
```
@szj_chentu -> https://p16-dreamina-sign-sg.ibyteimg.com/.../陈屠.jpeg
@szj_suwan -> https://p16-dreamina-sign-sg.ibyteimg.com/.../苏晚.jpeg
```

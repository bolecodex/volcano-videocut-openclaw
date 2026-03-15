---
name: novel-07-shots-to-video
version: 1.0.0
description: 将分镜头的图片和音频合并成视频。读取 shots/*.yaml 分镜文件，自动下载图片和音频，使用 FFmpeg 合成视频片段并拼接成完整视频。当用户想要生成视频、合并音视频、制作分镜视频、将分镜转为视频时使用此 skill。
trigger: "FFmpeg合成|合成视频|merge video|生成视频|合并音视频"
tools: [filesystem, shell]
---

# 分镜头视频合成（FFmpeg 版）

将分镜 YAML 文件中的图片和音频资源合并成完整视频。

> **Remotion 增强版**：如需转场效果（fade/wipe/slide）、动态字幕动画、Ken Burns 多方向缩放等高级效果，请使用 `novel-07-remotion` skill。本 FFmpeg 版本适合快速合成、不需要动画效果的场景。

## 项目目录定位规则（必须首先执行）

> **本 skill 的所有读写操作都基于 `{项目目录}`，不是 workspace 根目录。**

`{项目目录}` 是 workspace 根目录下以剧本简称命名的子目录，由上游 skill 创建：

```
{workspace根目录}/
├── {剧本简称}/          ← 这就是 {项目目录}
│   ├── style.yaml
│   ├── shots/
│   ├── output/
│   └── ...
└── 剧本原文.md
```

### 如何定位

1. 用户指定了项目名 → 直接使用 `{workspace}/{项目名}/`
2. 用户未指定 → 列出 workspace 下的子目录，找到包含 `shots/` 和 `style.yaml` 的目录
3. **禁止**在 workspace 根目录下直接读写产物文件

---

## 前置要求

- FFmpeg 已安装（`brew install ffmpeg` 或系统已有）
- Python 3.8+

## 工作流程

```
任务进度：
- [ ] 步骤 1：读取分镜数据
- [ ] 步骤 2：选择场景
- [ ] 步骤 3：运行合成脚本
- [ ] 步骤 4：展示结果
```

---

## 步骤 1：读取分镜数据

读取项目的分镜索引文件：

```
{项目目录}/shots/_manifest.yaml
```

从中获取：
- `files`: 所有场景分镜文件列表
- 每个场景的镜头数量和状态

---

## 步骤 2：选择场景

检查每个场景的资源完整性：

```
场景资源检查：
1. SC_01_开篇悬念
   - 镜头数: 2
   - 图片: 2/2 ✅
   - 音频: 7/7 ✅
   
2. SC_02_西市日常
   - 镜头数: 5
   - 图片: 0/5 ❌ (缺少图片)
   - 音频: 15/15 ✅
```

**只有图片和音频都完整的场景才能生成视频。**

让用户选择：
- 单个场景编号
- `all` - 所有资源完整的场景

---

## 步骤 3：运行合成脚本

使用项目脚本 `scripts/merge_video.py` 执行合成：

```bash
python scripts/merge_video.py \
  --project "{项目目录}" \
  --scene "SC_01" \
  --output "{项目目录}/output/videos"
```

### 脚本参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--project` | 项目根目录 | `./杀猪匠的使命` |
| `--scene` | 场景ID或"all" | `SC_01` 或 `all` |
| `--output` | 输出目录 | `./output/videos` |
| `--fps` | 视频帧率 | `24` (默认) |
| `--subtitle` | 生成字幕 | `--subtitle` (可选) |
| `--transition` | 转场时长(秒) | `0.5` (默认无转场) |

### 合成逻辑

对每个镜头(shot)执行：

```
1. 下载图片 (image_url → temp/images/shot_xxx.png)
2. 下载该镜头所有音频 (lines[].audio_url → temp/audio/shot_xxx_line_xx.mp3)
3. 合并音频 → shot_xxx_audio.mp3
4. 计算音频时长 → duration
5. 图片 + 音频 → shot_xxx.mp4 (图片显示 duration 秒)
```

所有镜头片段合成后，按顺序拼接：

```
shot_001.mp4 + shot_002.mp4 + ... → SC_01_开篇悬念.mp4
```

### FFmpeg 核心命令

**合并单镜头音频：**
```bash
ffmpeg -i line_01.mp3 -i line_02.mp3 -i line_03.mp3 \
  -filter_complex "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]" \
  -map "[out]" shot_audio.mp3
```

**图片+音频生成视频：**
```bash
ffmpeg -loop 1 -i image.png -i shot_audio.mp3 \
  -c:v libx264 -tune stillimage -c:a aac \
  -t {duration} -pix_fmt yuv420p -shortest \
  shot.mp4
```

**拼接所有片段：**
```bash
# 创建 list.txt
file 'shot_001.mp4'
file 'shot_002.mp4'
...

ffmpeg -f concat -safe 0 -i list.txt -c copy scene.mp4
```

---

## 步骤 4：展示结果

合成完成后，展示结果：

```markdown
## 视频合成完成

### 场景: SC_01_开篇悬念
- 时长: 45秒
- 镜头数: 2
- 输出: output/videos/SC_01_开篇悬念.mp4

### 场景: SC_02_西市日常
- 时长: 2分15秒
- 镜头数: 5
- 输出: output/videos/SC_02_西市日常.mp4

### 完整视频
- 总时长: 3分00秒
- 输出: output/videos/杀猪匠的使命_完整版.mp4

---
✅ 视频已生成，可在 output/videos/ 目录查看
```

---

## 输出目录结构

```
{项目目录}/
├── shots/
│   ├── SC_01_开篇悬念.yaml
│   └── SC_02_西市日常.yaml
└── output/
    └── videos/
        ├── temp/                    # 临时文件（可删除）
        │   ├── images/
        │   ├── audio/
        │   └── clips/
        ├── SC_01_开篇悬念.mp4       # 单场景视频
        ├── SC_02_西市日常.mp4
        └── 杀猪匠的使命_完整版.mp4   # 合并后的完整视频
```

---

## 可选功能

### 字幕叠加

添加 `--subtitle` 参数时，从 `lines[].text` 生成 SRT 字幕并烧录到视频：

```bash
python scripts/merge_video.py --project . --scene SC_01 --subtitle
```

字幕样式：
- 字体: 思源黑体 / Noto Sans CJK
- 大小: 48px
- 位置: 底部居中
- 背景: 半透明黑底

### 转场效果

添加 `--transition 0.5` 参数时，镜头之间添加淡入淡出：

```bash
python scripts/merge_video.py --project . --scene SC_01 --transition 0.5
```

### Ken Burns 效果

添加 `--kenburns` 参数时，静态图片添加微缩放动画：

```bash
python scripts/merge_video.py --project . --scene SC_01 --kenburns
```

---

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 图片 URL 失效 | 跳过该镜头，提示用户重新生成图片 |
| 音频 URL 失效 | 跳过该镜头，提示用户重新生成音频 |
| FFmpeg 未安装 | 提示安装命令 |
| 音频下载超时 | 重试 3 次，仍失败则跳过 |

---

## 完整示例

### 示例：生成 SC_01 场景视频

```bash
# 1. 检查资源完整性
python scripts/merge_video.py --project ./杀猪匠的使命 --scene SC_01 --check-only

# 2. 生成视频（带字幕）
python scripts/merge_video.py --project ./杀猪匠的使命 --scene SC_01 --subtitle

# 3. 生成所有场景并合并
python scripts/merge_video.py --project ./杀猪匠的使命 --scene all --subtitle
```

### 示例：仅合并已有场景视频

如果场景视频已单独生成，可以只做合并：

```bash
python scripts/merge_video.py --project ./杀猪匠的使命 --merge-only
```

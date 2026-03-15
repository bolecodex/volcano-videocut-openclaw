---
name: novel-07-remotion
version: 1.0.0
description: 使用 Remotion 将分镜头的图片和音频合成为视频。支持镜头间转场（fade/wipe/slide）、Ken Burns 缩放动画、动态字幕叠加。读取 shots/*.yaml 分镜文件，输出高质量 MP4。当用户想要生成视频、合并音视频、制作分镜视频、使用 Remotion 合成视频时使用此 skill。
trigger: "Remotion|remotion合成|高级视频合成|转场视频|字幕视频"
tools: [filesystem, shell]
---

# Remotion 分镜视频合成

使用 Remotion（React 视频框架）将分镜 YAML 中的图片和音频合成为带转场、字幕、动画效果的高质量视频。

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

## 与 FFmpeg 版本的对比

| 特性 | FFmpeg 版 (novel-07-shots-to-video) | Remotion 版 (本 skill) |
|------|------------------------------------|-----------------------|
| 转场效果 | 未实现 | fade / wipe / slide |
| 字幕 | SRT 烧录，样式固定 | 动态渐入渐出 + 说话人标签 |
| Ken Burns | FFmpeg zoompan filter | React 动画，5 种方向变体 |
| 可扩展性 | 改 FFmpeg 命令 | 改 React 组件 |
| 依赖 | Python + FFmpeg | Node.js + FFmpeg |
| 速度 | 较快 | 较慢（逐帧渲染） |

> 如果只需快速合成、不需要动画效果，使用 FFmpeg 版本。需要转场/字幕动画等高级效果时使用本 Remotion 版本。

---

## 前置要求

- **Node.js >= 16**（推荐 18+）
- **FFmpeg** 已安装（Remotion 编码依赖）
- 首次使用需安装依赖

### 首次安装

```bash
cd /Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion/remotion-project
npm install
```

> `/Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion` 是本 skill 的文件夹路径，即 `.cursor/skills/novel-07-remotion/`。

---

## 工作流程

```
任务进度：
- [ ] 步骤 0：安装依赖（首次）
- [ ] 步骤 1：读取分镜数据
- [ ] 步骤 2：选择场景
- [ ] 步骤 3：数据预处理
- [ ] 步骤 4：渲染视频
- [ ] 步骤 5：展示结果
```

---

## 步骤 0：安装依赖（仅首次）

检查 `/Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion/remotion-project/node_modules` 是否存在。如不存在：

```bash
cd /Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion/remotion-project && npm install
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
   - 镜头数: 4
   - 图片: 4/4 ✅
   - 音频: 8/8 ✅
   
2. SC_02_西市日常
   - 镜头数: 5
   - 图片: 0/5 ❌ (缺少图片)
   - 音频: 15/15 ✅
```

**只有图片和音频都完整的场景才能生成视频。**

让用户选择：
- 单个场景编号（如 `SC_01`）
- `all` - 所有资源完整的场景

同时询问用户偏好（可使用默认值）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 转场类型 | `fade` | `fade` / `wipe` / `slide` / `none` |
| 转场时长 | `15` 帧 (0.5s) | 转场效果持续帧数 |
| Ken Burns | `true` | 图片缩放/平移动画 |
| 字幕 | `true` | 显示台词字幕 |
| 分辨率 | `1080x1920` | 竖屏 9:16 |
| 帧率 | `30` | FPS |

---

## 步骤 3：数据预处理

运行预处理脚本，下载资源并生成 Remotion 所需的 props 文件：

```bash
cd /Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion/remotion-project && npx tsx scripts/prepare-data.ts \
  --project "{项目目录}" \
  --scene "SC_01" \
  --output "{项目目录}/output/remotion" \
  --fps 30 \
  --width 1080 \
  --height 1920 \
  --transition "fade" \
  --transition-frames 15 \
  --kenburns true \
  --subtitles true
```

### 脚本功能

1. 读取 `shots/_manifest.yaml` 和场景 YAML
2. 检查资源完整性
3. 下载图片到 `output/remotion/public/images/`
4. 下载音频到 `output/remotion/public/audio/`
5. 用 ffprobe 计算每条音频时长
6. 生成 `output/remotion/props_SC_XX.json`（Remotion inputProps）
7. 生成 `output/remotion/scenes_summary.json`（场景摘要）

### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--project` | 项目根目录 | `./杀猪匠的使命` |
| `--scene` | 场景 ID 或 `all` | `SC_01` |
| `--output` | 输出目录 | `./output/remotion` |
| `--fps` | 帧率 | `30` |
| `--width` | 宽度 | `1080` |
| `--height` | 高度 | `1920` |
| `--transition` | 转场类型 | `fade` / `wipe` / `slide` / `none` |
| `--transition-frames` | 转场帧数 | `15` |
| `--kenburns` | Ken Burns 效果 | `true` / `false` |
| `--subtitles` | 字幕显示 | `true` / `false` |

---

## 步骤 4：渲染视频

使用 Remotion SSR API 渲染视频：

```bash
cd /Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion/remotion-project && npx tsx scripts/render.ts \
  --project "{项目目录}" \
  --output "{项目目录}/output/remotion" \
  --scene "SC_01"
```

### 渲染流程

1. 打包 Remotion 项目（`@remotion/bundler`）
2. 读取 props JSON
3. 选择合成 → 计算总帧数
4. 逐帧渲染并编码为 H.264 MP4
5. 多场景时自动用 FFmpeg 拼接完整视频

### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--project` | 项目根目录 | `./杀猪匠的使命` |
| `--output` | 输出目录（需与 prepare-data 相同） | `./output/remotion` |
| `--scene` | 场景 ID 或 `all` | `SC_01` |
| `--remotion-dir` | Remotion 项目路径（通常不需指定） | 自动检测 |

---

## 步骤 5：展示结果

渲染完成后，展示结果：

```markdown
## Remotion 视频合成完成

### 场景: SC_01_开篇悬念
- 时长: 45秒
- 镜头数: 4
- 转场: fade (0.5s)
- 字幕: ✅ 已启用
- Ken Burns: ✅ 已启用
- 输出: output/remotion/videos/SC_01_开篇悬念.mp4

### 完整视频
- 总时长: 3分00秒
- 输出: output/remotion/videos/杀猪匠的使命_完整版.mp4

---
✅ 视频已生成，可在 output/remotion/videos/ 目录查看
```

---

## 输出目录结构

```
{项目目录}/
├── shots/
│   ├── _manifest.yaml
│   ├── SC_01_开篇悬念.yaml
│   └── ...
└── output/
    └── remotion/
        ├── public/                          # 下载的资源
        │   ├── images/
        │   │   ├── SC_01_001.png
        │   │   └── ...
        │   └── audio/
        │       ├── SC_01_001_line_00.mp3
        │       └── ...
        ├── props_SC_01.json                 # Remotion 参数
        ├── scenes_summary.json              # 场景摘要
        └── videos/
            ├── SC_01_开篇悬念.mp4           # 单场景视频
            └── 杀猪匠的使命_完整版.mp4       # 完整视频
```

---

## 视频效果说明

### 转场效果

| 类型 | 说明 |
|------|------|
| `fade` | 淡入淡出（默认），镜头间平滑过渡 |
| `wipe` | 擦除效果，新镜头从一侧覆盖旧镜头 |
| `slide` | 滑动效果，带弹性动画 |
| `none` | 无转场，硬切 |

### Ken Burns 效果

每个镜头自动分配一种 Ken Burns 动画（基于镜头 ID 确定性选择）：

| 方向 | 说明 |
|------|------|
| `zoom-in` | 从全景缓慢推近 |
| `zoom-out` | 从近景缓慢拉远 |
| `pan-left` | 从右向左平移 |
| `pan-right` | 从左向右平移 |
| `pan-up` | 从下向上平移 |

### 字幕系统

- 每条台词按音频时长精确定位
- 带淡入淡出动画（6 帧渐变）
- 非旁白台词显示说话人标签
- 半透明黑底圆角卡片样式
- 支持配置：字号、字体、颜色、位置（底部/居中/顶部）

---

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 图片 URL 失效 | 跳过该镜头，提示用户重新生成图片 |
| 音频 URL 失效 | 跳过该镜头，提示用户重新生成音频 |
| Node.js 未安装 | 提示安装 Node.js |
| FFmpeg 未安装 | 提示安装 FFmpeg |
| npm install 未执行 | 提示先安装依赖 |
| 渲染超时 | 检查资源是否过大，建议降低分辨率 |

---

## 完整示例

### 示例：生成 SC_01 场景视频（带转场和字幕）

```bash
# 1. 首次安装依赖
cd /Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion/remotion-project && npm install

# 2. 预处理数据
npx tsx scripts/prepare-data.ts \
  --project ./杀猪匠的使命 \
  --scene SC_01 \
  --transition fade

# 3. 渲染视频
npx tsx scripts/render.ts \
  --project ./杀猪匠的使命 \
  --scene SC_01

# 4. 查看输出
open ./杀猪匠的使命/output/remotion/videos/SC_01_开篇悬念.mp4
```

### 示例：生成全部场景（无转场，纯硬切）

```bash
npx tsx scripts/prepare-data.ts \
  --project ./杀猪匠的使命 \
  --scene all \
  --transition none \
  --kenburns false

npx tsx scripts/render.ts \
  --project ./杀猪匠的使命 \
  --scene all
```

### 示例：横屏 16:9 视频

```bash
npx tsx scripts/prepare-data.ts \
  --project ./杀猪匠的使命 \
  --scene SC_01 \
  --width 1920 \
  --height 1080

npx tsx scripts/render.ts \
  --project ./杀猪匠的使命 \
  --scene SC_01
```

---

## 自定义扩展

Remotion 项目位于 `/Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion/remotion-project/`，可自行修改 React 组件来扩展效果：

| 文件 | 用途 |
|------|------|
| `src/compositions/SceneVideo.tsx` | 场景编排、转场逻辑 |
| `src/components/ShotSequence.tsx` | 单镜头合成（图片+音频+字幕） |
| `src/components/ImageLayer.tsx` | 图片层、Ken Burns 动画 |
| `src/components/SubtitleOverlay.tsx` | 字幕样式和动画 |
| `src/components/AudioSequence.tsx` | 音频时序编排 |
| `src/types.ts` | 数据类型定义 |

### Studio 预览

可以启动 Remotion Studio 在浏览器中实时预览效果：

```bash
cd /Users/m007/codes/long_video_skills/skills-openclaw/novel-07-remotion/remotion-project && npx remotion studio
```

预览时需要先运行 prepare-data 生成 public 目录中的资源。

# 短剧剪辑助手 - 前端使用说明

Electron + React 桌面应用，用于选择多集短剧视频和剪辑要求，一键生成投流素材。

## 前置要求

- Node.js 18+
- Python 3.x + 项目 `.venv`（含 `openai`、`python-dotenv`）
- FFmpeg
- 已配置 `.env`（ARK_API_KEY 等）

## 安装与运行

```bash
# 安装依赖
npm install

# 开发模式：先启动 React，再启动 Electron
npm run electron:dev

# 或分步运行
npm start          # 终端1：启动 React (localhost:3000)
npm run electron   # 终端2：启动 Electron（加载 build 时需先 npm run build）
```

开发模式下，Electron 会加载 `http://localhost:3000`。

## 打包

```bash
npm run electron:build
```

输出在 `dist/` 目录。

## 使用流程

1. **选择视频**：选择包含短剧分集的文件夹（如 `05.mp4`、`06.mp4`）
2. **剪辑要求**：选择预设或输入自定义要求
   - 冲突开场版
   - 前置爽点版
   - 萌娃引流版
   - 情感共鸣版
   - 自定义
3. **分析视频**：调用豆包 Seed 2.0 分析高光片段
4. **选择片段组合**：选择集数和推荐组合版本
5. **生成剪辑**：使用 FFmpeg 切割合并，输出到 `video/output/` 或指定目录

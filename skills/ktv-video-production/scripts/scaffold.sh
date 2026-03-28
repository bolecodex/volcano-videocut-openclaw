#!/usr/bin/env bash
# scaffold.sh v3 — 视频模式 + 音频模式 + 千问 ASR 自动生成歌词
set -e

PROJECT="ktv-video-production-project"
mkdir -p "$PROJECT"/{public,scripts,src/{components,data,utils,preview}}

# ===================== package.json =====================
cat > "$PROJECT/package.json" << 'EOF'
{
  "name": "ktv-video-production-project",
  "version": "3.0.0",
  "private": true,
  "scripts": {
    "start": "npx remotion studio",
    "render": "npx remotion render KtvLyrics out/ktv-output.mp4",
    "preview": "vite --config vite.config.ts",
    "parse-lrc": "node scripts/parse-lrc.mjs"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "remotion": "^4.0.0",
    "@remotion/player": "^4.0.0",
    "@remotion/cli": "^4.0.0",
    "@remotion/web-renderer": "^4.0.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.0.0"
  }
}
EOF

# ===================== tsconfig.json =====================
cat > "$PROJECT/tsconfig.json" << 'EOF'
{
  "compilerOptions": {
    "target": "ES2022", "module": "ESNext", "moduleResolution": "bundler",
    "jsx": "react-jsx", "strict": true, "esModuleInterop": true,
    "skipLibCheck": true, "resolveJsonModule": true, "outDir": "dist"
  },
  "include": ["src/**/*"]
}
EOF

# ===================== remotion.config.ts =====================
cat > "$PROJECT/remotion.config.ts" << 'EOF'
import { Config } from "@remotion/cli/config";
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
EOF

# ===================== vite.config.ts =====================
cat > "$PROJECT/vite.config.ts" << 'EOF'
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  root: "src/preview",
  publicDir: "../../public",
  build: { outDir: "../../dist-preview" },
  server: { port: 3000, open: true },
});
EOF

# ===================== src/config.ts =====================
cat > "$PROJECT/src/config.ts" << 'EOF'
// ===== 全局配置 =====

/** 模式："video"（视频底部叠加歌词）或 "audio"（全屏滚动歌词） */
export const MODE: "video" | "audio" = "video";

/** 媒体文件名（放在 public/ 目录下） */
export const MEDIA_SRC = "media.mp4";

/**
 * 原始媒体总时长（秒）。
 * ⚠️ 必须设置！用于保证输出视频时长与原视频/音频一致。
 * 获取方式：ffprobe -v error -show_entries format=duration -of csv=p=0 media.mp4
 */
export const TOTAL_DURATION_SEC = 0;

/** 视频分辨率 */
export const VIDEO_WIDTH = 1920;
export const VIDEO_HEIGHT = 1080;

/** 帧率 */
export const FPS = 30;

/** 高亮颜色（已唱过的文字）— 亮绿 */
export const ACTIVE_COLOR = "#00ff88";

/** 未唱到的文字颜色 */
export const INACTIVE_COLOR = "rgba(255, 255, 255, 0.3)";

/** 歌词字号 — 视频模式下当前行 */
export const LYRIC_FONT_SIZE_CURRENT = 64;

/** 歌词字号 — 视频模式下下一行 / 音频模式普通行 */
export const LYRIC_FONT_SIZE_NEXT = 48;

/** 歌词字号 — 音频模式当前行（更大） */
export const LYRIC_FONT_SIZE_AUDIO_CURRENT = 72;

/** 歌词字体 */
export const LYRIC_FONT_FAMILY = '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif';

/** 底部歌词区域高度（视频模式，像素） */
export const LYRICS_AREA_HEIGHT = 220;

/** 底部蒙层透明度（视频模式） */
export const OVERLAY_OPACITY = 0.65;

/** 颜色轮换列表 — 鲜艳色系 */
export const COLOR_PALETTE = [
  "#00ff88",  // 亮绿
  "#ff3d7f",  // 玫红
  "#ffcc00",  // 金黄
  "#00cfff",  // 天蓝
  "#ff6b35",  // 橙色
  "#c471f5",  // 紫色
];
EOF
cat > "$PROJECT/src/index.ts" << 'EOF'
import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";
registerRoot(RemotionRoot);
EOF

# ===================== src/Root.tsx =====================
cat > "$PROJECT/src/Root.tsx" << 'EOF'
import React from "react";
import { Composition } from "remotion";
import { KtvComposition } from "./components/KtvComposition";
import { VIDEO_WIDTH, VIDEO_HEIGHT, FPS, TOTAL_DURATION_SEC } from "./config";
import lyricsData from "./data/lyrics-data.json";

/**
 * 视频总帧数：
 * - 如果设置了 TOTAL_DURATION_SEC > 0，以原始媒体时长为准（确保输出视频时长对齐原视频）
 * - 否则 fallback 到歌词最后一行结束时间 + 3 秒
 */
const lastLine = lyricsData[lyricsData.length - 1];
const lyricsEndFrames = lastLine ? lastLine.lineEnd + FPS * 3 : FPS * 10;
const totalFrames = TOTAL_DURATION_SEC > 0
  ? Math.round(TOTAL_DURATION_SEC * FPS)
  : lyricsEndFrames;

export const RemotionRoot: React.FC = () => (
  <Composition
    id="KtvLyrics"
    component={KtvComposition}
    durationInFrames={totalFrames}
    fps={FPS}
    width={VIDEO_WIDTH}
    height={VIDEO_HEIGHT}
    defaultProps={{ lyricsData }}
  />
);
EOF
cat > "$PROJECT/src/components/LyricWord.tsx" << 'EOF'
import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { ACTIVE_COLOR, INACTIVE_COLOR } from "../config";

interface Props {
  text: string;
  startFrame: number;
  endFrame: number;
  activeColor?: string;
  inactiveColor?: string;
  fontSize?: number;
}

export const LyricWord: React.FC<Props> = ({
  text, startFrame, endFrame,
  activeColor = ACTIVE_COLOR,
  inactiveColor = INACTIVE_COLOR,
}) => {
  const frame = useCurrentFrame();
  const fill = interpolate(frame, [startFrame, endFrame], [0, 100], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <span style={{
      color: "transparent",
      backgroundImage: `linear-gradient(to right, ${activeColor} ${fill}%, ${inactiveColor} ${fill}%)`,
      WebkitBackgroundClip: "text",
      backgroundClip: "text",
      filter: fill > 0 && fill < 100
        ? `drop-shadow(0 0 8px ${activeColor}90)`
        : fill >= 100
          ? `drop-shadow(0 0 4px ${activeColor}50)`
          : "none",
    }}>
      {text}
    </span>
  );
};
EOF

# ===================== src/components/LyricLine.tsx =====================
cat > "$PROJECT/src/components/LyricLine.tsx" << 'EOF'
import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { LyricWord } from "./LyricWord";
import { LYRIC_FONT_FAMILY } from "../config";

export interface WordTiming { text: string; start: number; end: number; }

interface Props {
  words: WordTiming[];
  lineStart: number;
  lineEnd: number;
  activeColor?: string;
  fontSize?: number;
  opacity?: number;
}

export const LyricLine: React.FC<Props> = ({
  words, lineStart, lineEnd, activeColor, fontSize = 64, opacity,
}) => {
  const frame = useCurrentFrame();

  const autoOpacity = opacity ?? interpolate(
    frame,
    [lineStart - 10, lineStart, lineEnd, lineEnd + 15],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div style={{
      opacity: autoOpacity,
      fontSize,
      fontWeight: 800,
      fontFamily: LYRIC_FONT_FAMILY,
      letterSpacing: 3,
      textAlign: "center",
      textShadow: "0 2px 12px rgba(255,255,255,0.9), 0 0 6px rgba(255,255,255,0.7)",
      whiteSpace: "nowrap",
      lineHeight: 1.5,
    }}>
      {words.map((w, i) => (
        <LyricWord key={i} text={w.text} startFrame={w.start} endFrame={w.end} activeColor={activeColor} />
      ))}
    </div>
  );
};
EOF

# ===================== src/components/VideoOverlay.tsx =====================
cat > "$PROJECT/src/components/VideoOverlay.tsx" << 'EOF'
/**
 * 视频模式：歌词叠加在视频底部
 * 显示当前行（大字高亮填充）+ 下一行（小字半透明预览）
 */
import React from "react";
import { useCurrentFrame } from "remotion";
import { LyricLine, WordTiming } from "./LyricLine";
import {
  LYRICS_AREA_HEIGHT, OVERLAY_OPACITY, COLOR_PALETTE,
  LYRIC_FONT_SIZE_CURRENT, LYRIC_FONT_SIZE_NEXT,
} from "../config";

interface LineData { lineStart: number; lineEnd: number; words: WordTiming[]; }
interface Props { lyricsData: LineData[]; }

export const VideoOverlay: React.FC<Props> = ({ lyricsData }) => {
  const frame = useCurrentFrame();

  const currentIdx = lyricsData.findIndex(
    (l) => frame >= l.lineStart - 10 && frame <= l.lineEnd
  );
  const nextIdx = currentIdx >= 0 && currentIdx < lyricsData.length - 1 ? currentIdx + 1 : -1;

  const currentLine = currentIdx >= 0 ? lyricsData[currentIdx] : null;
  const nextLine = nextIdx >= 0 ? lyricsData[nextIdx] : null;

  if (!currentLine && !nextLine) return null;

  return (
    <div style={{
      position: "absolute", bottom: 0, left: 0, right: 0,
      height: LYRICS_AREA_HEIGHT,
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      gap: 14,
      padding: "0 60px",
    }}>
      {currentLine && (
        <LyricLine
          words={currentLine.words}
          lineStart={currentLine.lineStart}
          lineEnd={currentLine.lineEnd}
          activeColor={COLOR_PALETTE[currentIdx % COLOR_PALETTE.length]}
          fontSize={LYRIC_FONT_SIZE_CURRENT}
        />
      )}
      {nextLine && (
        <LyricLine
          words={nextLine.words}
          lineStart={nextLine.lineStart}
          lineEnd={nextLine.lineEnd}
          activeColor={COLOR_PALETTE[nextIdx % COLOR_PALETTE.length]}
          fontSize={LYRIC_FONT_SIZE_NEXT}
          opacity={0.45}
        />
      )}
    </div>
  );
};
EOF

# ===================== src/components/AudioScrollLyrics.tsx =====================
cat > "$PROJECT/src/components/AudioScrollLyrics.tsx" << 'EOF'
/**
 * 音频模式：全屏滚动歌词
 * 当前行居中放大高亮，已唱行上方变暗缩小，未唱行下方半透明
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";
import { LyricLine, WordTiming } from "./LyricLine";
import {
  COLOR_PALETTE, LYRIC_FONT_SIZE_AUDIO_CURRENT, LYRIC_FONT_SIZE_NEXT,
  VIDEO_HEIGHT,
} from "../config";

interface LineData { lineStart: number; lineEnd: number; words: WordTiming[]; }
interface Props { lyricsData: LineData[]; }

const LINE_HEIGHT = 100; // 每行歌词的占位高度
const CENTER_Y = 0.45;   // 当前行在屏幕的垂直位置（0~1）

export const AudioScrollLyrics: React.FC<Props> = ({ lyricsData }) => {
  const frame = useCurrentFrame();

  // 找到当前行
  let currentIdx = lyricsData.findIndex(
    (l) => frame >= l.lineStart && frame <= l.lineEnd
  );
  // 如果在两行之间的间隙，取上一个已完成的行
  if (currentIdx < 0) {
    for (let i = lyricsData.length - 1; i >= 0; i--) {
      if (frame > lyricsData[i].lineEnd) { currentIdx = i; break; }
    }
  }
  if (currentIdx < 0) currentIdx = 0;

  // 计算滚动偏移：让当前行处于屏幕 CENTER_Y 位置
  const targetOffset = currentIdx * LINE_HEIGHT;
  const scrollY = VIDEO_HEIGHT * CENTER_Y - targetOffset;

  return (
    <AbsoluteFill style={{
      background: "linear-gradient(180deg, #0a0020 0%, #1a0a3e 40%, #0d0025 100%)",
    }}>
      {/* 顶部渐隐遮罩 */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 200,
        background: "linear-gradient(to bottom, #0a0020 0%, transparent 100%)",
        zIndex: 2,
      }} />
      {/* 底部渐隐遮罩 */}
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0, height: 200,
        background: "linear-gradient(to top, #0d0025 0%, transparent 100%)",
        zIndex: 2,
      }} />

      {/* 歌词滚动容器 */}
      <div style={{
        position: "absolute", left: 0, right: 0,
        top: scrollY,
        transition: "top 0.3s ease-out",
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "0 80px",
      }}>
        {lyricsData.map((line, i) => {
          const isCurrent = i === currentIdx && frame >= line.lineStart && frame <= line.lineEnd;
          const isPast = frame > line.lineEnd;
          const isFuture = frame < line.lineStart;

          let opacity = 0.3;
          let fontSize = LYRIC_FONT_SIZE_NEXT;

          if (isCurrent) {
            opacity = 1;
            fontSize = LYRIC_FONT_SIZE_AUDIO_CURRENT;
          } else if (isPast) {
            // 越远越暗
            const distance = currentIdx - i;
            opacity = Math.max(0.15, 0.5 - distance * 0.1);
            fontSize = LYRIC_FONT_SIZE_NEXT;
          } else if (isFuture) {
            const distance = i - currentIdx;
            opacity = Math.max(0.15, 0.45 - distance * 0.08);
            fontSize = LYRIC_FONT_SIZE_NEXT;
          }

          return (
            <div key={i} style={{
              height: LINE_HEIGHT,
              display: "flex", alignItems: "center", justifyContent: "center",
              transform: isCurrent ? "scale(1.05)" : "scale(0.95)",
            }}>
              <LyricLine
                words={line.words}
                lineStart={line.lineStart}
                lineEnd={line.lineEnd}
                activeColor={isCurrent ? COLOR_PALETTE[i % COLOR_PALETTE.length] : undefined}
                fontSize={fontSize}
                opacity={opacity}
              />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
EOF

# ===================== src/components/ProgressBar.tsx =====================
cat > "$PROJECT/src/components/ProgressBar.tsx" << 'EOF'
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { ACTIVE_COLOR } from "../config";

export const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames], [0, 100], { extrapolateRight: "clamp" });

  return (
    <div style={{
      position: "absolute", bottom: 0, left: 0, right: 0,
      height: 4, background: "rgba(255,255,255,0.08)", zIndex: 10,
    }}>
      <div style={{
        height: "100%",
        background: `linear-gradient(to right, ${ACTIVE_COLOR}, #ff3d7f, #ffcc00)`,
        width: `${progress}%`,
        boxShadow: `0 0 8px ${ACTIVE_COLOR}60`,
      }} />
    </div>
  );
};
EOF

# ===================== src/components/KtvComposition.tsx =====================
cat > "$PROJECT/src/components/KtvComposition.tsx" << 'EOF'
import React from "react";
import { AbsoluteFill, OffthreadVideo, Audio, staticFile } from "remotion";
import { VideoOverlay } from "./VideoOverlay";
import { AudioScrollLyrics } from "./AudioScrollLyrics";
import { ProgressBar } from "./ProgressBar";
import { MODE, MEDIA_SRC } from "../config";
import { WordTiming } from "./LyricLine";

interface LineData { lineStart: number; lineEnd: number; words: WordTiming[]; }
interface Props { lyricsData: LineData[]; }

export const KtvComposition: React.FC<Props> = ({ lyricsData }) => {
  return (
    <AbsoluteFill>
      {MODE === "video" ? (
        <>
          {/* 视频模式：视频铺底 + 底部歌词叠加 */}
          <AbsoluteFill>
            <OffthreadVideo
              src={staticFile(MEDIA_SRC)}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </AbsoluteFill>
          <VideoOverlay lyricsData={lyricsData} />
        </>
      ) : (
        <>
          {/* 音频模式：全屏滚动歌词 + 音频播放 */}
          <Audio src={staticFile(MEDIA_SRC)} />
          <AudioScrollLyrics lyricsData={lyricsData} />
        </>
      )}
      <ProgressBar />
    </AbsoluteFill>
  );
};
EOF

# ===================== src/utils/parseLrc.ts =====================
cat > "$PROJECT/src/utils/parseLrc.ts" << 'EOF'
export interface WordTiming { text: string; start: number; end: number; }
export interface LineTiming { lineStart: number; lineEnd: number; words: WordTiming[]; }

function timeToFrame(ts: string, fps: number): number {
  const m = ts.match(/(\d+):(\d+)\.(\d+)/);
  if (!m) return 0;
  return Math.round((parseInt(m[1]) * 60 + parseInt(m[2]) + parseInt(m[3].padEnd(2, "0").slice(0, 2)) / 100) * fps);
}

export function parseStandardLrc(lrc: string, fps = 30): LineTiming[] {
  const lines = lrc.split("\n").filter(l => /^\[\d+:\d+\.\d+\]/.test(l.trim()));
  const parsed = lines.map(l => { const m = l.match(/^\[(\d+:\d+\.\d+)\](.*)/); return { time: timeToFrame(m![1], fps), text: m![2].trim() }; });
  const result: LineTiming[] = [];
  for (let i = 0; i < parsed.length; i++) {
    const { time: ls, text } = parsed[i];
    const le = i < parsed.length - 1 ? parsed[i + 1].time : ls + fps * 4;
    if (!text) continue;
    const chars = text.split(""), dur = (le - ls) / chars.length;
    result.push({ lineStart: ls, lineEnd: le, words: chars.map((c, j) => ({ text: c, start: Math.round(ls + j * dur), end: Math.round(ls + (j + 1) * dur) })) });
  }
  return result;
}

export function parseEnhancedLrc(lrc: string, fps = 30): LineTiming[] {
  const lines = lrc.split("\n").filter(l => /^\[\d+:\d+\.\d+\]/.test(l.trim()));
  const result: LineTiming[] = [];
  for (const line of lines) {
    const lm = line.match(/^\[(\d+:\d+\.\d+)\](.*)/); if (!lm) continue;
    const ls = timeToFrame(lm[1], fps), wp = /<(\d+:\d+\.\d+)>([^<]+)/g;
    const words: WordTiming[] = []; let m;
    while ((m = wp.exec(lm[2])) !== null) words.push({ text: m[2], start: timeToFrame(m[1], fps), end: 0 });
    for (let i = 0; i < words.length; i++) words[i].end = i < words.length - 1 ? words[i + 1].start : words[i].start + Math.round(fps * 0.5);
    result.push({ lineStart: ls, lineEnd: words.length ? words[words.length - 1].end : ls, words });
  }
  return result;
}

export function parseLrc(lrc: string, fps = 30): LineTiming[] {
  return /<\d+:\d+\.\d+>/.test(lrc) ? parseEnhancedLrc(lrc, fps) : parseStandardLrc(lrc, fps);
}
EOF

# ===================== scripts/parse-lrc.mjs =====================
cat > "$PROJECT/scripts/parse-lrc.mjs" << 'SCRIPT_EOF'
#!/usr/bin/env node
import { readFileSync } from "fs";
const [,, lrcFile, fpsArg] = process.argv;
if (!lrcFile) { console.error("用法: node scripts/parse-lrc.mjs <lrc-file> [fps]"); process.exit(1); }
const fps = parseInt(fpsArg) || 30;
const lrcText = readFileSync(lrcFile, "utf-8");

function t2f(ts) { const m = ts.match(/(\d+):(\d+)\.(\d+)/); if (!m) return 0; return Math.round((parseInt(m[1]) * 60 + parseInt(m[2]) + parseInt(m[3].padEnd(2, "0").slice(0, 2)) / 100) * fps); }

function parseStd(text) {
  const lines = text.split("\n").filter(l => /^\[\d+:\d+\.\d+\]/.test(l.trim()));
  const parsed = lines.map(l => { const m = l.match(/^\[(\d+:\d+\.\d+)\](.*)/); return { time: t2f(m[1]), text: m[2].trim() }; });
  const r = [];
  for (let i = 0; i < parsed.length; i++) {
    const { time: ls, text: lt } = parsed[i]; const le = i < parsed.length - 1 ? parsed[i + 1].time : ls + fps * 4;
    if (!lt) continue; const chars = lt.split(""), dur = (le - ls) / chars.length;
    r.push({ lineStart: ls, lineEnd: le, words: chars.map((c, j) => ({ text: c, start: Math.round(ls + j * dur), end: Math.round(ls + (j + 1) * dur) })) });
  }
  return r;
}

function parseEnh(text) {
  const lines = text.split("\n").filter(l => /^\[\d+:\d+\.\d+\]/.test(l.trim()));
  const r = [];
  for (const line of lines) {
    const lm = line.match(/^\[(\d+:\d+\.\d+)\](.*)/); if (!lm) continue;
    const ls = t2f(lm[1]), wp = /<(\d+:\d+\.\d+)>([^<]+)/g, words = []; let m;
    while ((m = wp.exec(lm[2])) !== null) words.push({ text: m[2], start: t2f(m[1]), end: 0 });
    for (let i = 0; i < words.length; i++) words[i].end = i < words.length - 1 ? words[i + 1].start : words[i].start + Math.round(fps * 0.5);
    r.push({ lineStart: ls, lineEnd: words.length ? words[words.length - 1].end : ls, words });
  }
  return r;
}

const data = /<\d+:\d+\.\d+>/.test(lrcText) ? parseEnh(lrcText) : parseStd(lrcText);
console.log(JSON.stringify(data, null, 2));
SCRIPT_EOF

# ===================== preview 文件 =====================
cat > "$PROJECT/src/preview/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>KTV 歌词预览</title>
  <style>* { margin:0; padding:0; box-sizing:border-box; } body { min-height:100vh; background:#0a0a1a; color:#fff; font-family:-apple-system,"PingFang SC",sans-serif; } #root { width:100%; min-height:100vh; }</style>
</head>
<body><div id="root"></div><script type="module" src="./main.tsx"></script></body>
</html>
EOF

cat > "$PROJECT/src/preview/main.tsx" << 'EOF'
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
createRoot(document.getElementById("root")!).render(<App />);
EOF

cat > "$PROJECT/src/preview/App.tsx" << 'EOF'
import React, { useRef } from "react";
import { Player, PlayerRef } from "@remotion/player";
import { KtvComposition } from "../components/KtvComposition";
import { VIDEO_WIDTH, VIDEO_HEIGHT, FPS, MODE, TOTAL_DURATION_SEC } from "../config";
import lyricsData from "../data/lyrics-data.json";

const lastLine = lyricsData[lyricsData.length - 1];
const lyricsEndFrames = lastLine ? lastLine.lineEnd + FPS * 3 : FPS * 10;
const totalFrames = TOTAL_DURATION_SEC > 0
  ? Math.round(TOTAL_DURATION_SEC * FPS)
  : lyricsEndFrames;

export const App: React.FC = () => {
  const playerRef = useRef<PlayerRef>(null);
  return (
    <div style={{ padding: 40, maxWidth: 1200, margin: "0 auto" }}>
      <h1 style={{ marginBottom: 8, fontSize: 28, fontWeight: 700 }}>KTV 歌词预览</h1>
      <p style={{ color: "#888", marginBottom: 24, fontSize: 14 }}>
        模式：{MODE === "video" ? "视频底部叠加" : "全屏滚动歌词"} | 时长：{(totalFrames / FPS).toFixed(1)}s
      </p>
      <div style={{ borderRadius: 12, overflow: "hidden", boxShadow: "0 8px 32px rgba(0,0,0,0.4)", marginBottom: 24 }}>
        <Player ref={playerRef} component={KtvComposition} inputProps={{ lyricsData }} durationInFrames={totalFrames} fps={FPS} compositionWidth={VIDEO_WIDTH} compositionHeight={VIDEO_HEIGHT} style={{ width: "100%" }} controls autoPlay={false} loop clickToPlay />
      </div>
      <p style={{ color: "#666", fontSize: 13 }}>CLI 导出：<code style={{ color: "#00ff88" }}>npm run render</code></p>
    </div>
  );
};
EOF
# ===================== 默认歌词数据 =====================
cat > "$PROJECT/src/data/lyrics-data.json" << 'EOF'
[
  {"lineStart":0,"lineEnd":90,"words":[{"text":"示","start":0,"end":11},{"text":"例","start":11,"end":22},{"text":"歌","start":22,"end":33},{"text":"词","start":33,"end":45},{"text":"请","start":45,"end":56},{"text":"运","start":56,"end":67},{"text":"行","start":67,"end":78},{"text":"A","start":78,"end":82},{"text":"S","start":82,"end":86},{"text":"R","start":86,"end":90}]},
  {"lineStart":90,"lineEnd":180,"words":[{"text":"自","start":90,"end":105},{"text":"动","start":105,"end":120},{"text":"识","start":120,"end":135},{"text":"别","start":135,"end":150},{"text":"生","start":150,"end":160},{"text":"成","start":160,"end":170},{"text":"歌","start":170,"end":175},{"text":"词","start":175,"end":180}]}
]
EOF



echo "✅ 项目 $PROJECT 创建完成"
echo "   模式：视频(底部叠加) + 音频(全屏滚动)"
echo "   ⚠️  请设置 src/config.ts 中的 TOTAL_DURATION_SEC 以对齐原始媒体时长"
echo ""
find "$PROJECT" -type f | sort

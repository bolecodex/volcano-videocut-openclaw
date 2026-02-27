#!/usr/bin/env npx tsx
/**
 * 数据预处理脚本
 * 读取 shots/*.yaml -> 下载图片/音频到 public/ -> 计算帧数 -> 输出 inputProps.json
 */

import * as fs from "fs";
import * as path from "path";
import * as https from "https";
import * as http from "http";
import { execSync } from "child_process";
import * as yaml from "js-yaml";

interface RawLine {
  speaker: string;
  text: string;
  emotion?: string;
  audio_url?: string;
  audio_status?: string;
}

interface RawShot {
  id: string;
  title: string;
  shot_type?: string;
  image_url?: string;
  image_status?: string;
  mood?: string;
  lighting?: string;
  lines: RawLine[];
}

interface RawScene {
  scene_id: string;
  scene_name: string;
  shots: RawShot[];
}

interface ManifestEntry {
  file: string;
  scene_id: string;
  scene_name: string;
}

interface PrepareOptions {
  projectDir: string;
  sceneId: string;
  outputDir: string;
  fps: number;
  width: number;
  height: number;
  transitionType: "fade" | "wipe" | "slide" | "none";
  transitionDurationInFrames: number;
  enableKenBurns: boolean;
  enableSubtitles: boolean;
}

function log(msg: string, level = "INFO") {
  const ts = new Date().toLocaleTimeString();
  console.log(`[${ts}] [${level}] ${msg}`);
}

function downloadFile(url: string, dest: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (fs.existsSync(dest)) {
      log(`  已存在，跳过: ${path.basename(dest)}`);
      resolve();
      return;
    }

    const dir = path.dirname(dest);
    fs.mkdirSync(dir, { recursive: true });

    const protocol = url.startsWith("https") ? https : http;
    const file = fs.createWriteStream(dest);

    const request = (targetUrl: string, redirectCount = 0) => {
      if (redirectCount > 5) {
        reject(new Error("Too many redirects"));
        return;
      }
      protocol
        .get(targetUrl, (response) => {
          if (
            response.statusCode &&
            response.statusCode >= 300 &&
            response.statusCode < 400 &&
            response.headers.location
          ) {
            request(response.headers.location, redirectCount + 1);
            return;
          }
          if (response.statusCode !== 200) {
            reject(new Error(`HTTP ${response.statusCode} for ${targetUrl}`));
            return;
          }
          response.pipe(file);
          file.on("finish", () => {
            file.close();
            resolve();
          });
        })
        .on("error", (err) => {
          fs.unlink(dest, () => {});
          reject(err);
        });
    };
    request(url);
  });
}

function getAudioDuration(filePath: string): number {
  try {
    const result = execSync(
      `ffprobe -v quiet -show_entries format=duration -of csv=p=0 "${filePath}"`,
      { encoding: "utf-8" }
    );
    return parseFloat(result.trim()) || 0;
  } catch {
    log(`  无法获取音频时长: ${filePath}`, "WARN");
    return 2.0;
  }
}

function checkSceneResources(scene: RawScene): {
  ready: boolean;
  imagesReady: number;
  totalShots: number;
  audioReady: number;
  totalAudio: number;
} {
  let imagesReady = 0;
  let audioReady = 0;
  let totalAudio = 0;

  for (const shot of scene.shots) {
    if (shot.image_url && shot.image_status === "completed") {
      imagesReady++;
    }
    for (const line of shot.lines || []) {
      totalAudio++;
      if (line.audio_url && line.audio_status === "completed") {
        audioReady++;
      }
    }
  }

  return {
    ready: imagesReady === scene.shots.length && audioReady === totalAudio,
    imagesReady,
    totalShots: scene.shots.length,
    audioReady,
    totalAudio,
  };
}

async function prepareScene(opts: PrepareOptions) {
  const { projectDir, sceneId, fps } = opts;
  const shotsDir = path.join(projectDir, "shots");
  const publicDir = path.join(opts.outputDir, "public");

  fs.mkdirSync(path.join(publicDir, "images"), { recursive: true });
  fs.mkdirSync(path.join(publicDir, "audio"), { recursive: true });

  const manifestPath = path.join(shotsDir, "_manifest.yaml");
  if (!fs.existsSync(manifestPath)) {
    log(`找不到 manifest: ${manifestPath}`, "ERROR");
    process.exit(1);
  }

  const manifest = yaml.load(
    fs.readFileSync(manifestPath, "utf-8")
  ) as { files: ManifestEntry[] };

  let sceneEntries: ManifestEntry[];
  if (sceneId === "all") {
    sceneEntries = manifest.files;
  } else {
    sceneEntries = manifest.files.filter(
      (f) => f.scene_id === sceneId
    );
    if (sceneEntries.length === 0) {
      log(`未找到场景: ${sceneId}`, "ERROR");
      log("可用场景:");
      for (const f of manifest.files) {
        log(`  ${f.scene_id} - ${f.scene_name}`);
      }
      process.exit(1);
    }
  }

  const allSceneProps = [];

  for (const entry of sceneEntries) {
    const scenePath = path.join(shotsDir, entry.file);
    if (!fs.existsSync(scenePath)) {
      log(`场景文件不存在: ${scenePath}`, "WARN");
      continue;
    }

    const scene = yaml.load(
      fs.readFileSync(scenePath, "utf-8")
    ) as RawScene;

    const status = checkSceneResources(scene);
    log(
      `场景 ${scene.scene_id} - ${scene.scene_name}: ` +
        `图片 ${status.imagesReady}/${status.totalShots}, ` +
        `音频 ${status.audioReady}/${status.totalAudio} ` +
        `${status.ready ? "✅" : "❌"}`
    );

    if (!status.ready) {
      log(`  跳过资源不完整的场景`, "WARN");
      continue;
    }

    const preparedShots = [];

    for (const shot of scene.shots) {
      log(`  处理镜头: ${shot.id}`);

      const imageExt = (shot.image_url || "").split(".").pop()?.split("?")[0] || "png";
      const imageDest = path.join(
        publicDir,
        "images",
        `${shot.id}.${imageExt}`
      );
      const imageSrc = `images/${shot.id}.${imageExt}`;

      try {
        await downloadFile(shot.image_url!, imageDest);
        log(`  ✓ 图片下载完成`);
      } catch (err) {
        log(
          `  图片下载失败: ${(err as Error).message}`,
          "ERROR"
        );
        continue;
      }

      const preparedLines = [];
      let totalDuration = 0;

      for (let i = 0; i < (shot.lines || []).length; i++) {
        const line = shot.lines[i];
        const audioExt = (line.audio_url || "").split(".").pop()?.split("?")[0] || "mp3";
        const audioDest = path.join(
          publicDir,
          "audio",
          `${shot.id}_line_${String(i).padStart(2, "0")}.${audioExt}`
        );
        const audioSrc = `audio/${shot.id}_line_${String(i).padStart(2, "0")}.${audioExt}`;

        try {
          await downloadFile(line.audio_url!, audioDest);
          const duration = getAudioDuration(audioDest);
          totalDuration += duration;

          preparedLines.push({
            speaker: line.speaker,
            text: line.text,
            emotion: line.emotion,
            audioSrc,
            durationInSeconds: duration,
          });
          log(`    ✓ 音频 ${i}: ${duration.toFixed(1)}s`);
        } catch (err) {
          log(
            `    音频下载失败: ${(err as Error).message}`,
            "ERROR"
          );
        }
      }

      if (preparedLines.length === 0) {
        log(`  无有效音频，跳过镜头 ${shot.id}`, "WARN");
        continue;
      }

      const paddedDuration = totalDuration + 0.5;
      const durationInFrames = Math.ceil(paddedDuration * fps);

      preparedShots.push({
        id: shot.id,
        title: shot.title,
        shotType: shot.shot_type,
        imageSrc,
        lines: preparedLines,
        totalDurationInSeconds: totalDuration,
        durationInFrames,
        mood: shot.mood,
        lighting: shot.lighting,
      });

      log(
        `  ✓ 镜头 ${shot.id}: ${totalDuration.toFixed(1)}s, ${durationInFrames} 帧`
      );
    }

    if (preparedShots.length === 0) {
      log(`  场景无有效镜头，跳过`, "WARN");
      continue;
    }

    const sceneProps = {
      sceneId: scene.scene_id,
      sceneName: scene.scene_name,
      shots: preparedShots,
      fps: opts.fps,
      width: opts.width,
      height: opts.height,
      transitionDurationInFrames: opts.transitionDurationInFrames,
      transitionType: opts.transitionType,
      enableKenBurns: opts.enableKenBurns,
      enableSubtitles: opts.enableSubtitles,
      subtitleStyle: {
        fontSize: 42,
        fontFamily: "Noto Sans SC, sans-serif",
        color: "#FFFFFF",
        backgroundColor: "rgba(0, 0, 0, 0.6)",
        position: "bottom" as const,
      },
    };

    const propsPath = path.join(
      opts.outputDir,
      `props_${scene.scene_id}.json`
    );
    fs.writeFileSync(propsPath, JSON.stringify(sceneProps, null, 2));
    log(`✓ 已写入: ${propsPath}`);
    allSceneProps.push({ sceneId: scene.scene_id, sceneName: scene.scene_name, propsPath });
  }

  const summaryPath = path.join(opts.outputDir, "scenes_summary.json");
  fs.writeFileSync(summaryPath, JSON.stringify(allSceneProps, null, 2));
  log(`\n✓ 预处理完成，共 ${allSceneProps.length} 个场景`);
  log(`  场景摘要: ${summaryPath}`);
}

// --- CLI ---
const args = process.argv.slice(2);
function getArg(name: string, defaultVal: string): string {
  const idx = args.indexOf(`--${name}`);
  if (idx >= 0 && idx + 1 < args.length) return args[idx + 1];
  return defaultVal;
}

const projectDir = path.resolve(getArg("project", "."));
const sceneId = getArg("scene", "all");
const outputDir = path.resolve(
  getArg("output", path.join(projectDir, "output", "remotion"))
);
const fps = parseInt(getArg("fps", "30"), 10);
const width = parseInt(getArg("width", "1080"), 10);
const height = parseInt(getArg("height", "1920"), 10);
const transitionType = getArg("transition", "fade") as PrepareOptions["transitionType"];
const transitionFrames = parseInt(getArg("transition-frames", "15"), 10);
const kenburns = getArg("kenburns", "true") === "true";
const subtitles = getArg("subtitles", "true") === "true";

log("=== Remotion 数据预处理 ===");
log(`项目目录: ${projectDir}`);
log(`场景: ${sceneId}`);
log(`输出: ${outputDir}`);
log(`视频参数: ${width}x${height} @ ${fps}fps`);
log(`转场: ${transitionType} (${transitionFrames} 帧)`);
log(`Ken Burns: ${kenburns}, 字幕: ${subtitles}`);
log("");

prepareScene({
  projectDir,
  sceneId,
  outputDir,
  fps,
  width,
  height,
  transitionType,
  transitionDurationInFrames: transitionFrames,
  enableKenBurns: kenburns,
  enableSubtitles: subtitles,
}).catch((err) => {
  log(`预处理失败: ${err.message}`, "ERROR");
  process.exit(1);
});

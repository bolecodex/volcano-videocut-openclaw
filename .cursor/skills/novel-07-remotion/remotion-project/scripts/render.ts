#!/usr/bin/env npx tsx
/**
 * Remotion SSR 渲染脚本
 * 读取 prepare-data 生成的 props JSON，使用 Remotion API 渲染为 MP4
 */

import * as fs from "fs";
import * as path from "path";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

interface SceneSummary {
  sceneId: string;
  sceneName: string;
  propsPath: string;
}

function log(msg: string, level = "INFO") {
  const ts = new Date().toLocaleTimeString();
  console.log(`[${ts}] [${level}] ${msg}`);
}

async function renderScene(
  bundleLocation: string,
  propsPath: string,
  outputPath: string,
  publicDir: string
) {
  const inputProps = JSON.parse(fs.readFileSync(propsPath, "utf-8"));

  log(`  选择合成: SceneVideo`);
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "SceneVideo",
    inputProps,
  });

  log(`  渲染: ${composition.durationInFrames} 帧, ${composition.width}x${composition.height}`);

  const startTime = Date.now();
  let lastProgress = 0;

  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outputPath,
    inputProps,
    chromiumOptions: {
      enableMultiProcessOnLinux: true,
    },
    onProgress: ({ progress }) => {
      const pct = Math.floor(progress * 100);
      if (pct >= lastProgress + 10) {
        lastProgress = pct;
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        log(`  进度: ${pct}% (${elapsed}s)`);
      }
    },
  });

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const fileSize = (fs.statSync(outputPath).size / 1024 / 1024).toFixed(1);
  log(`  ✓ 渲染完成: ${outputPath} (${fileSize}MB, ${elapsed}s)`);
}

async function concatVideos(
  videoPaths: string[],
  outputPath: string
) {
  if (videoPaths.length === 0) return;
  if (videoPaths.length === 1) {
    fs.copyFileSync(videoPaths[0], outputPath);
    return;
  }

  const { execSync } = await import("child_process");
  const listFile = path.join(path.dirname(outputPath), "_concat_list.txt");
  const listContent = videoPaths
    .map((p) => `file '${path.resolve(p)}'`)
    .join("\n");
  fs.writeFileSync(listFile, listContent);

  execSync(
    `ffmpeg -y -f concat -safe 0 -i "${listFile}" -c copy "${outputPath}"`,
    { stdio: "pipe" }
  );

  fs.unlinkSync(listFile);
  log(`✓ 合并完成: ${outputPath}`);
}

async function main() {
  const args = process.argv.slice(2);
  function getArg(name: string, defaultVal: string): string {
    const idx = args.indexOf(`--${name}`);
    if (idx >= 0 && idx + 1 < args.length) return args[idx + 1];
    return defaultVal;
  }

  const projectDir = path.resolve(getArg("project", "."));
  const remotionDir = path.resolve(getArg("remotion-dir", __dirname + "/.."));
  const outputDir = path.resolve(
    getArg("output", path.join(projectDir, "output", "remotion"))
  );
  const scene = getArg("scene", "all");
  const videosDir = path.join(outputDir, "videos");

  fs.mkdirSync(videosDir, { recursive: true });

  log("=== Remotion 视频渲染 ===");
  log(`项目目录: ${projectDir}`);
  log(`Remotion 项目: ${remotionDir}`);
  log(`输出目录: ${videosDir}`);

  // --- Step 1: Bundle ---
  log("\n步骤 1: 打包 Remotion 项目...");
  const entryPoint = path.join(remotionDir, "src", "index.ts");

  const publicDir = path.join(outputDir, "public");
  if (!fs.existsSync(publicDir)) {
    log("找不到 public 目录，请先运行 prepare-data 脚本", "ERROR");
    process.exit(1);
  }

  const bundleLocation = await bundle({
    entryPoint,
    publicDir,
  });
  log(`✓ 打包完成: ${bundleLocation}`);

  // --- Step 2: Find props files ---
  const summaryPath = path.join(outputDir, "scenes_summary.json");
  let scenes: SceneSummary[];

  if (fs.existsSync(summaryPath)) {
    scenes = JSON.parse(fs.readFileSync(summaryPath, "utf-8"));
  } else {
    const propsFiles = fs
      .readdirSync(outputDir)
      .filter((f) => f.startsWith("props_") && f.endsWith(".json"));
    scenes = propsFiles.map((f) => ({
      sceneId: f.replace("props_", "").replace(".json", ""),
      sceneName: "",
      propsPath: path.join(outputDir, f),
    }));
  }

  if (scene !== "all") {
    scenes = scenes.filter((s) => s.sceneId === scene);
  }

  if (scenes.length === 0) {
    log("没有找到可渲染的场景", "ERROR");
    process.exit(1);
  }

  log(`\n找到 ${scenes.length} 个场景待渲染`);

  // --- Step 3: Render each scene ---
  const renderedVideos: string[] = [];
  const results: Array<{
    sceneId: string;
    sceneName: string;
    success: boolean;
    outputPath?: string;
    error?: string;
  }> = [];

  for (const s of scenes) {
    const outputPath = path.join(
      videosDir,
      `${s.sceneId}_${s.sceneName || "scene"}.mp4`
    );
    log(`\n渲染场景: ${s.sceneId} - ${s.sceneName}`);

    try {
      await renderScene(bundleLocation, s.propsPath, outputPath, publicDir);
      renderedVideos.push(outputPath);
      results.push({
        sceneId: s.sceneId,
        sceneName: s.sceneName,
        success: true,
        outputPath,
      });
    } catch (err) {
      const errMsg = (err as Error).message;
      log(`  渲染失败: ${errMsg}`, "ERROR");
      results.push({
        sceneId: s.sceneId,
        sceneName: s.sceneName,
        success: false,
        error: errMsg,
      });
    }
  }

  // --- Step 4: Concat if multiple scenes ---
  if (renderedVideos.length > 1) {
    const projectName = path.basename(projectDir);
    const finalPath = path.join(videosDir, `${projectName}_完整版.mp4`);
    log("\n合并所有场景...");
    try {
      await concatVideos(renderedVideos, finalPath);
    } catch (err) {
      log(`合并失败: ${(err as Error).message}`, "ERROR");
    }
  }

  // --- Summary ---
  console.log("\n" + "=".repeat(50));
  console.log("渲染结果");
  console.log("=".repeat(50));
  for (const r of results) {
    if (r.success) {
      console.log(`✅ ${r.sceneId} - ${r.sceneName}: ${r.outputPath}`);
    } else {
      console.log(`❌ ${r.sceneId} - ${r.sceneName}: ${r.error}`);
    }
  }
  console.log("=".repeat(50));
}

main().catch((err) => {
  log(`渲染失败: ${err.message}`, "ERROR");
  console.error(err);
  process.exit(1);
});

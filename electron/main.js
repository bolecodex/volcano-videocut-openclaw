const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const { getGateway } = require('./gateway-client');
const { SkillsManager } = require('./skills-manager');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const SCRIPTS_DIR = path.join(PROJECT_ROOT, 'scripts');
const OUTPUT_DIR = path.join(PROJECT_ROOT, 'video', 'output');
const TEMPLATES_DIR = path.join(PROJECT_ROOT, 'scripts', 'prompts', 'templates');
const SKILLS_DIR = path.join(PROJECT_ROOT, 'skills');
const ENV_PATH = path.join(PROJECT_ROOT, '.env');

const ENV_KEYS = [
  'ARK_API_KEY',
  'ARK_BASE_URL',
  'ARK_MODEL_NAME',
  'SEEDANCE_MODEL',
  'SEEDANCE_API_KEY',
  'ARK_TTS_ENDPOINT',
  'ARK_TTS_MODEL',
];

const skillsManager = new SkillsManager(SKILLS_DIR);

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 1100,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(PROJECT_ROOT, 'build', 'index.html'));
  }

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
app.on('activate', () => { if (!mainWindow) createWindow(); });

function getPythonPath() {
  const venv = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
  if (fs.existsSync(venv)) return venv;
  return 'python3';
}

function runPython(script, args, onStdout, onStderr) {
  return new Promise((resolve, reject) => {
    const py = getPythonPath();
    const proc = spawn(py, [path.join(SCRIPTS_DIR, script), ...args], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });
    let stdout = '';
    let stderr = '';
    proc.stdout?.on('data', (d) => {
      const s = d.toString();
      stdout += s;
      onStdout?.(s);
    });
    proc.stderr?.on('data', (d) => {
      const s = d.toString();
      stderr += s;
      onStderr?.(s);
    });
    proc.on('close', (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(stderr || stdout || `Exit code ${code}`));
    });
    proc.on('error', reject);
  });
}

// ── Prompt template handlers ──

ipcMain.handle('list-prompt-templates', async () => {
  try {
    const indexPath = path.join(TEMPLATES_DIR, 'index.json');
    const data = fs.readFileSync(indexPath, 'utf-8');
    return JSON.parse(data);
  } catch {
    return [];
  }
});

ipcMain.handle('read-prompt-template', async (_, templateId) => {
  try {
    const indexPath = path.join(TEMPLATES_DIR, 'index.json');
    const templates = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
    const tpl = templates.find((t) => t.id === templateId);
    if (!tpl) return null;
    const filePath = path.join(TEMPLATES_DIR, tpl.file);
    return fs.readFileSync(filePath, 'utf-8');
  } catch {
    return null;
  }
});

// ── Settings (.env) ──
function parseEnvFile(content) {
  const obj = {};
  for (const key of ENV_KEYS) obj[key] = '';
  if (!content) return obj;
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    if (ENV_KEYS.includes(key)) {
      const val = trimmed.slice(eq + 1).trim();
      obj[key] = val.replace(/^["']|["']$/g, '');
    }
  }
  return obj;
}

function stringifyEnvConfig(obj) {
  const comments = {
    ARK_API_KEY: '# 火山引擎方舟 API Key（视频分析、OpenClaw、Seedance 等）',
    ARK_BASE_URL: '# 方舟 API 地址（可选）',
    ARK_MODEL_NAME: '# 多模态/对话模型接入点（可选）',
    SEEDANCE_MODEL: '# Seedance 2.0 推理接入点 ID（形如 ep-xxxx）',
    SEEDANCE_API_KEY: '# 可选：Seedance 专用 Key，不填则用 ARK_API_KEY',
    ARK_TTS_ENDPOINT: '# 可选：语音合成接入点',
    ARK_TTS_MODEL: '# 可选：TTS 模型 ID',
  };
  let out = '# 复制为 .env 后填写真实值（.env 勿提交到 Git）\n\n';
  for (const key of ENV_KEYS) {
    if (comments[key]) out += comments[key] + '\n';
    const val = (obj[key] || '').trim();
    out += `${key}=${val ? val : ''}\n`;
    if (['ARK_API_KEY', 'SEEDANCE_MODEL'].includes(key)) out += '\n';
  }
  return out;
}

ipcMain.handle('get-env-config', async () => {
  try {
    const content = fs.existsSync(ENV_PATH) ? fs.readFileSync(ENV_PATH, 'utf-8') : '';
    return parseEnvFile(content);
  } catch {
    return ENV_KEYS.reduce((o, k) => ({ ...o, [k]: '' }), {});
  }
});

ipcMain.handle('set-env-config', async (_, config) => {
  try {
    const obj = { ...parseEnvFile(fs.existsSync(ENV_PATH) ? fs.readFileSync(ENV_PATH, 'utf-8') : ''), ...config };
    fs.writeFileSync(ENV_PATH, stringifyEnvConfig(obj), 'utf-8');
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

// ── File dialog handlers ──

ipcMain.handle('select-video-dir', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: '选择短剧视频文件夹',
  });
  if (canceled || !filePaths?.length) return null;
  return filePaths[0];
});

ipcMain.handle('select-output-dir', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: '选择输出文件夹',
  });
  if (canceled || !filePaths?.length) return null;
  return filePaths[0];
});

// ── Analyze handler ──

ipcMain.handle('analyze-videos', async (_, { videoDir, outputDir, fullPromptText, outputName, singleEpisode }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = [videoDir, '-o', outDir];

  if (fullPromptText) {
    const tempPrompt = path.join(PROJECT_ROOT, 'scripts', 'prompts', '_temp_custom_prompt.txt');
    fs.writeFileSync(tempPrompt, fullPromptText, 'utf-8');
    args.push('--prompt', tempPrompt);
  }

  if (outputName) args.push('--name', outputName);
  if (singleEpisode) args.push('--single');

  const sendLog = (text) => mainWindow?.webContents?.send('analyze-log', text);

  try {
    await runPython('analyze_video.py', args, sendLog, sendLog);
    const files = fs.readdirSync(outDir).filter((f) => f.startsWith('highlights_') && f.endsWith('.json'));
    return { success: true, outputDir: outDir, highlightFiles: files.sort() };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

// ── Cut handler ──

ipcMain.handle('cut-video', async (_, { highlightsJson, highlightsFile, sourceVideoDir, outputDir, outputName }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const jsonPath = highlightsFile ? path.join(highlightsJson, highlightsFile) : highlightsJson;
  const args = [jsonPath, sourceVideoDir, '-o', outDir];
  if (outputName) args.push('-n', outputName);

  const sendLog = (text) => mainWindow?.webContents?.send('cut-log', text);

  try {
    await runPython('ffmpeg_cut.py', args, sendLog, sendLog);
    const files = fs.readdirSync(outDir).filter((f) => f.startsWith('promo_') && f.endsWith('.mp4'));
    const base = outputName || path.basename(jsonPath, '.json').replace('highlights_', '');
    const match = files.find((f) => f.includes(base));
    return { success: true, outputDir: outDir, outputFile: match || files[files.length - 1] };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

// ── Utility handlers ──

ipcMain.handle('get-highlight-data', async (_, outputDir, fileName) => {
  const filePath = path.join(outputDir, fileName);
  const data = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(data);
});

const VIDEO_EXT = ['.mp4', '.mov', '.mpeg', '.webm', '.avi'];
ipcMain.handle('resolve-source-video', async (_, videoDir, episode) => {
  for (const ext of VIDEO_EXT) {
    const p = path.join(videoDir, episode + ext);
    if (fs.existsSync(p)) return p;
  }
  return path.join(videoDir, episode + '.mp4');
});

ipcMain.handle('open-output-folder', async (_, dirPath) => {
  shell.openPath(dirPath);
});

ipcMain.handle('list-video-files', async (_, dirPath) => {
  try {
    if (!dirPath || !fs.existsSync(dirPath)) return [];
    return fs.readdirSync(dirPath)
      .filter((f) => VIDEO_EXT.includes(path.extname(f).toLowerCase()))
      .sort();
  } catch {
    return [];
  }
});

ipcMain.handle('list-output-files', async (_, dirPath) => {
  try {
    if (!dirPath || !fs.existsSync(dirPath)) return [];
    const all = fs.readdirSync(dirPath);
    return {
      highlights: all.filter((f) => f.startsWith('highlights_') && f.endsWith('.json')).sort(),
      promos: all.filter((f) => f.endsWith('.mp4') && f.startsWith('promo_')).sort(),
    };
  } catch {
    return { highlights: [], promos: [] };
  }
});

const MENTION_IGNORE_DIRS = new Set([
  'node_modules', '.git', 'build', 'dist', '.venv', '__pycache__', '.cursor',
  'mcps', 'terminals',
]);
const MENTION_SKIP_TOP = new Set(['skills']); // 技能由 list-skills 提供，避免重复

function classifyMentionAsset(relPosix, ext) {
  const lower = relPosix.toLowerCase();
  const e = ext.toLowerCase();
  if (['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'].includes(e)) return 'audio';
  if (['.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'].includes(e)) return 'video';
  if (
    lower.includes('/characters/') || lower.includes('/角色') || lower.includes('character_card')
    || lower.includes('角色卡') || lower.includes('/char/')
  ) return 'character';
  if (
    lower.includes('/scenes/') || lower.includes('/场景') || lower.includes('scene_bible')
    || lower.includes('场景库')
  ) return 'scene';
  if (
    lower.includes('分镜') || lower.includes('shot_list') || lower.includes('storyboard')
    || lower.includes('/shots/') || lower.includes('shotlist') || lower.includes('highlights_')
  ) return 'storyboard';
  if (['.md', '.json', '.txt', '.yaml', '.yml', '.csv'].includes(e)) return 'file';
  return null;
}

/** 扫描工程目录，供 @ 引用：音频/视频/剧本资产/分镜 JSON 等 */
ipcMain.handle('list-workspace-mention-assets', async () => {
  const perCat = { audio: 0, video: 0, character: 0, scene: 0, storyboard: 0, file: 0 };
  const maxPer = 120;
  const maxTotal = 500;
  const maxDepth = 8;
  const out = [];

  function walk(dir, depth, topLevelName) {
    if (depth > maxDepth || out.length >= maxTotal) return;
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const ent of entries) {
      if (ent.name.startsWith('.')) continue;
      if (MENTION_IGNORE_DIRS.has(ent.name)) continue;
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        if (depth === 0 && MENTION_SKIP_TOP.has(ent.name)) continue;
        walk(full, depth + 1, depth === 0 ? ent.name : topLevelName);
        continue;
      }
      const rel = path.relative(PROJECT_ROOT, full).split(path.sep).join('/');
      const ext = path.extname(ent.name);
      const cat = classifyMentionAsset(rel, ext);
      if (!cat || perCat[cat] >= maxPer) continue;
      perCat[cat] += 1;
      out.push({
        category: cat,
        id: rel,
        label: ent.name,
        desc: rel,
        absPath: full,
      });
    }
  }

  try {
    walk(PROJECT_ROOT, 0, '');
  } catch {
    return [];
  }
  return out;
});

// ── Skills handlers ──

ipcMain.handle('list-skills', async () => {
  try {
    return skillsManager.listSkills();
  } catch (err) {
    return [];
  }
});

ipcMain.handle('get-skill-detail', async (_, skillName) => {
  try {
    return skillsManager.getSkillDetail(skillName);
  } catch {
    return null;
  }
});

ipcMain.handle('import-skill', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: '选择 Skill 文件夹（必须包含 SKILL.md）',
  });
  if (canceled || !filePaths?.length) return null;

  try {
    const result = skillsManager.importSkill(filePaths[0]);
    return { success: true, ...result };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle('import-skill-from-url', async (_, url) => {
  try {
    const result = await skillsManager.importSkillFromUrl(url);
    return { success: true, ...result };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle('create-skill', async (_, skillData) => {
  try {
    const { skillId, ...data } = skillData;
    const result = skillsManager.createSkill(skillId, data);
    return { success: true, ...result };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle('delete-skill', async (_, skillName) => {
  try {
    skillsManager.deleteSkill(skillName);
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

// ── Gateway / Chat handlers ──

let gatewayInstance = null;

function ensureGateway() {
  if (!gatewayInstance) {
    gatewayInstance = getGateway();
  }
  return gatewayInstance;
}

ipcMain.handle('gateway-status', async () => {
  try {
    const gw = ensureGateway();
    return { connected: gw.isConnected };
  } catch {
    return { connected: false };
  }
});

ipcMain.handle('chat-send', async (event, { message, sessionKey, extraSystemPrompt }) => {
  const gw = ensureGateway();

  if (!gw.isConnected) {
    mainWindow?.webContents?.send('chat-stream', { type: 'error', error: 'Gateway not connected. Is OpenClaw running?' });
    mainWindow?.webContents?.send('chat-stream', { type: 'done' });
    return { error: 'not connected' };
  }

  try {
    const handle = await gw.sendPrompt(message, { sessionKey, extraSystemPrompt });

    if (handle.error) {
      mainWindow?.webContents?.send('chat-stream', { type: 'error', error: handle.error });
      mainWindow?.webContents?.send('chat-stream', { type: 'done' });
      return { error: handle.error };
    }

    (async () => {
      while (true) {
        if (handle.eventQueue.length > 0) {
          const evt = handle.eventQueue.shift();
          mainWindow?.webContents?.send('chat-stream', evt);
          if (evt.type === 'done' || evt.type === 'error') break;
          continue;
        }
        await handle.waitForEvent();
      }
    })();

    return { runId: handle.runId };
  } catch (err) {
    mainWindow?.webContents?.send('chat-stream', { type: 'error', error: err.message });
    mainWindow?.webContents?.send('chat-stream', { type: 'done' });
    return { error: err.message };
  }
});

ipcMain.handle('chat-list-sessions', async () => {
  try {
    const gw = ensureGateway();
    return await gw.listSessions();
  } catch {
    return [];
  }
});

ipcMain.handle('chat-delete-session', async (_, sessionKey) => {
  try {
    const gw = ensureGateway();
    return await gw.deleteSession(sessionKey);
  } catch {
    return false;
  }
});

// ── Post-processing handlers (S-Level) ──

ipcMain.handle('run-asr', async (_, { videoDir, outputDir }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = [videoDir, '-o', outDir];
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('asr_extract.py', args, sendLog, sendLog);
    return { success: true, outputDir: outDir };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-scene-detect', async (_, { videoDir, outputDir, threshold }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = [videoDir, '-o', outDir];
  if (threshold) args.push('-t', String(threshold));
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('scene_detect.py', args, sendLog, sendLog);
    return { success: true, outputDir: outDir };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-burn-subtitle', async (_, { videoPath, subtitlePath, outputPath, style }) => {
  const args = [videoPath, subtitlePath];
  if (outputPath) args.push('-o', outputPath);
  if (style) args.push('-s', style);
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('burn_subtitle.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-bgm-mix', async (_, { videoPath, bgmPath, outputPath, bgmVolume, noDucking }) => {
  const args = [videoPath, bgmPath];
  if (outputPath) args.push('-o', outputPath);
  if (bgmVolume != null) args.push('--bgm-volume', String(bgmVolume));
  if (noDucking) args.push('--no-ducking');
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('bgm_mix.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-platform-export', async (_, { videoPath, outputDir, platforms }) => {
  const args = [videoPath];
  if (outputDir) args.push('-o', outputDir);
  if (platforms?.length) args.push('-p', ...platforms);
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('platform_export.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-gen-cover', async (_, { videoPath, outputDir }) => {
  const args = [videoPath];
  if (outputDir) args.push('-o', outputDir);
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('gen_cover.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-quality-score', async (_, { videoPath, outputDir }) => {
  const args = [videoPath];
  if (outputDir) args.push('-o', outputDir);
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('score_quality.py', args, sendLog, sendLog);
    const stem = path.basename(videoPath, path.extname(videoPath));
    const scorePath = path.join(outputDir || OUTPUT_DIR, `score_${stem}.json`);
    if (fs.existsSync(scorePath)) {
      return { success: true, score: JSON.parse(fs.readFileSync(scorePath, 'utf-8')) };
    }
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-video-compress', async (_, { videoPath, outputPath, maxSizeMb, maxDuration }) => {
  const args = [videoPath];
  if (outputPath) args.push('-o', outputPath);
  if (maxSizeMb) args.push('--max-size-mb', String(maxSizeMb));
  if (maxDuration) args.push('--max-duration', String(maxDuration));
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('video_compress.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-video-resize', async (_, { videoPath, width, height, outputPath, method }) => {
  const args = [videoPath, String(width), String(height)];
  if (outputPath) args.push('-o', outputPath);
  if (method) args.push('-m', method);
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('video_resize.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-add-watermark', async (_, { videoPath, outputPath, title, disclaimer, position, fontsize, fontcolor, alpha }) => {
  const args = [videoPath];
  if (outputPath) args.push('-o', outputPath);
  if (title) args.push('--title', title);
  if (disclaimer) args.push('--disclaimer', disclaimer);
  if (position) args.push('--position', position);
  if (fontsize) args.push('--fontsize', String(fontsize));
  if (fontcolor) args.push('--fontcolor', fontcolor);
  if (alpha != null) args.push('--alpha', String(alpha));
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('add_watermark.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-video-censor', async (_, { videoPath, outputPath, subtitlePath }) => {
  const args = [videoPath];
  if (outputPath) args.push('-o', outputPath);
  if (subtitlePath) args.push('--subtitle', subtitlePath);
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('video_censor.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-remove-freeze-zoom', async (_, { videoPath, outputPath, tailSeconds, forceCut }) => {
  const args = [videoPath];
  if (outputPath) args.push('-o', outputPath);
  if (tailSeconds) args.push('--tail', String(tailSeconds));
  if (forceCut != null) args.push('--force', String(forceCut));
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('remove_freeze_zoom.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-ai-narration', async (_, { videoPath, outputPath, voiceId, speed }) => {
  const args = [videoPath];
  if (outputPath) args.push('-o', outputPath);
  if (voiceId) args.push('--voice', voiceId);
  if (speed != null) args.push('--speed', String(speed));
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('ai_narration.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-bgm-auto-match', async (_, { videoPath, outputPath, bgmDir, noAi }) => {
  const args = [videoPath];
  if (outputPath) args.push('-o', outputPath);
  if (bgmDir) args.push('--bgm-dir', bgmDir);
  if (noAi) args.push('--no-ai');
  const sendLog = (text) => mainWindow?.webContents?.send('postprocess-log', text);
  try {
    await runPython('bgm_auto_match.py', args, sendLog, sendLog);
    return { success: true };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

// ── Seedance 2.0 skill handlers ──

ipcMain.handle('run-seedance-replicate', async (_, { reference, outputDir, prompt, style, images, duration, ratio, resolution, fast }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = [reference, '-o', outDir];
  if (prompt) args.push('-p', prompt);
  if (style) args.push('-s', style);
  if (images?.length) args.push('-i', ...images);
  if (duration) args.push('-d', String(duration));
  if (ratio) args.push('-r', ratio);
  if (resolution) args.push('--resolution', resolution);
  if (fast) args.push('--fast');
  const sendLog = (text) => mainWindow?.webContents?.send('seedance-log', text);
  try {
    await runPython('seedance_replicate.py', args, sendLog, sendLog);
    return { success: true, outputDir: outDir };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-seedance-hook', async (_, { outputDir, style, prompt, firstFrame, sourceVideo, duration, ratio, resolution, fast, noAudio }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = ['-o', outDir];
  if (style) args.push('-s', style);
  if (prompt) args.push('-p', prompt);
  if (firstFrame) args.push('-f', firstFrame);
  if (sourceVideo) args.push('-v', sourceVideo);
  if (duration) args.push('-d', String(duration));
  if (ratio) args.push('-r', ratio);
  if (resolution) args.push('--resolution', resolution);
  if (fast) args.push('--fast');
  if (noAudio) args.push('--no-audio');
  const sendLog = (text) => mainWindow?.webContents?.send('seedance-log', text);
  try {
    await runPython('seedance_hook.py', args, sendLog, sendLog);
    return { success: true, outputDir: outDir };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-seedance-extend', async (_, { video, outputDir, prompt, tail, duration, chain, ratio, resolution, fast }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = [video, '-o', outDir];
  if (prompt) args.push('-p', prompt);
  if (tail) args.push('-t', String(tail));
  if (duration) args.push('-d', String(duration));
  if (chain) args.push('-c', String(chain));
  if (ratio) args.push('-r', ratio);
  if (resolution) args.push('--resolution', resolution);
  if (fast) args.push('--fast');
  const sendLog = (text) => mainWindow?.webContents?.send('seedance-log', text);
  try {
    await runPython('seedance_extend.py', args, sendLog, sendLog);
    return { success: true, outputDir: outDir };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-seedance-restyle', async (_, { video, outputDir, prompt, style, image, duration, ratio, resolution, fast }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = [video, '-o', outDir];
  if (prompt) args.push('-p', prompt);
  if (style) args.push('-s', style);
  if (image) args.push('-i', image);
  if (duration) args.push('-d', String(duration));
  if (ratio) args.push('-r', ratio);
  if (resolution) args.push('--resolution', resolution);
  if (fast) args.push('--fast');
  const sendLog = (text) => mainWindow?.webContents?.send('seedance-log', text);
  try {
    await runPython('seedance_restyle.py', args, sendLog, sendLog);
    return { success: true, outputDir: outDir };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-seedance-trending', async (_, { outputDir, theme, prompts, count, duration, ratio, resolution, fast, webSearch, searchQuery }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = ['-o', outDir];
  if (theme) args.push('-t', theme);
  if (prompts?.length) args.push('-p', ...prompts);
  if (count) args.push('-c', String(count));
  if (duration) args.push('-d', String(duration));
  if (ratio) args.push('-r', ratio);
  if (resolution) args.push('--resolution', resolution);
  if (fast) args.push('--fast');
  if (webSearch) args.push('--web-search');
  if (searchQuery) args.push('--search-query', searchQuery);
  const sendLog = (text) => mainWindow?.webContents?.send('seedance-log', text);
  try {
    await runPython('seedance_trending.py', args, sendLog, sendLog);
    return { success: true, outputDir: outDir };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('run-seedance-reframe', async (_, { video, outputDir, targetRatio, prompt, duration, resolution, fast }) => {
  const outDir = outputDir || OUTPUT_DIR;
  const args = [video, '-o', outDir];
  if (targetRatio) args.push('-r', targetRatio);
  if (prompt) args.push('-p', prompt);
  if (duration) args.push('-d', String(duration));
  if (resolution) args.push('--resolution', resolution);
  if (fast) args.push('--fast');
  const sendLog = (text) => mainWindow?.webContents?.send('seedance-log', text);
  try {
    await runPython('seedance_reframe.py', args, sendLog, sendLog);
    return { success: true, outputDir: outDir };
  } catch (err) {
    sendLog?.(err.message);
    return { success: false, error: err.message };
  }
});

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

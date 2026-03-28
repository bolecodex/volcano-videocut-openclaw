const { contextBridge, ipcRenderer } = require('electron');

function onChannel(channel, cb) {
  const handler = (_, data) => cb(data);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
}

contextBridge.exposeInMainWorld('electronAPI', {
  // Prompt templates
  listPromptTemplates: () => ipcRenderer.invoke('list-prompt-templates'),
  readPromptTemplate: (id) => ipcRenderer.invoke('read-prompt-template', id),

  // Settings (env config)
  getEnvConfig: () => ipcRenderer.invoke('get-env-config'),
  setEnvConfig: (config) => ipcRenderer.invoke('set-env-config', config),

  // File dialogs
  selectVideoDir: () => ipcRenderer.invoke('select-video-dir'),
  selectOutputDir: () => ipcRenderer.invoke('select-output-dir'),

  // Video processing
  analyzeVideos: (opts) => ipcRenderer.invoke('analyze-videos', opts),
  cutVideo: (opts) => ipcRenderer.invoke('cut-video', opts),
  getHighlightData: (outputDir, fileName) => ipcRenderer.invoke('get-highlight-data', outputDir, fileName),
  resolveSourceVideo: (dir, ep) => ipcRenderer.invoke('resolve-source-video', dir, ep),
  openOutputFolder: (path) => ipcRenderer.invoke('open-output-folder', path),
  listVideoFiles: (dir) => ipcRenderer.invoke('list-video-files', dir),
  listOutputFiles: (dir) => ipcRenderer.invoke('list-output-files', dir),
  listWorkspaceMentionAssets: () => ipcRenderer.invoke('list-workspace-mention-assets'),

  // Log listeners
  onAnalyzeLog: (cb) => onChannel('analyze-log', cb),
  onCutLog: (cb) => onChannel('cut-log', cb),

  // Skills
  listSkills: () => ipcRenderer.invoke('list-skills'),
  getSkillDetail: (name) => ipcRenderer.invoke('get-skill-detail', name),
  importSkill: () => ipcRenderer.invoke('import-skill'),
  importSkillFromUrl: (url) => ipcRenderer.invoke('import-skill-from-url', url),
  createSkill: (skillData) => ipcRenderer.invoke('create-skill', skillData),
  deleteSkill: (name) => ipcRenderer.invoke('delete-skill', name),

  // Gateway
  getGatewayStatus: () => ipcRenderer.invoke('gateway-status'),

  // Chat
  chatSend: (opts) => ipcRenderer.invoke('chat-send', opts),
  chatStop: () => ipcRenderer.invoke('chat-stop'),
  chatListSessions: () => ipcRenderer.invoke('chat-list-sessions'),
  chatDeleteSession: (key) => ipcRenderer.invoke('chat-delete-session', key),
  onChatStream: (cb) => onChannel('chat-stream', cb),

  // Post-processing (S-Level)
  runAsr: (opts) => ipcRenderer.invoke('run-asr', opts),
  runSceneDetect: (opts) => ipcRenderer.invoke('run-scene-detect', opts),
  runBurnSubtitle: (opts) => ipcRenderer.invoke('run-burn-subtitle', opts),
  runBgmMix: (opts) => ipcRenderer.invoke('run-bgm-mix', opts),
  runPlatformExport: (opts) => ipcRenderer.invoke('run-platform-export', opts),
  runGenCover: (opts) => ipcRenderer.invoke('run-gen-cover', opts),
  runQualityScore: (opts) => ipcRenderer.invoke('run-quality-score', opts),
  runVideoCompress: (opts) => ipcRenderer.invoke('run-video-compress', opts),
  runVideoResize: (opts) => ipcRenderer.invoke('run-video-resize', opts),
  runAddWatermark: (opts) => ipcRenderer.invoke('run-add-watermark', opts),
  runVideoCensor: (opts) => ipcRenderer.invoke('run-video-censor', opts),
  runRemoveFreezeZoom: (opts) => ipcRenderer.invoke('run-remove-freeze-zoom', opts),
  runAiNarration: (opts) => ipcRenderer.invoke('run-ai-narration', opts),
  runBgmAutoMatch: (opts) => ipcRenderer.invoke('run-bgm-auto-match', opts),
  onPostprocessLog: (cb) => onChannel('postprocess-log', cb),

  // Seedance 2.0 skills
  runSeedanceReplicate: (opts) => ipcRenderer.invoke('run-seedance-replicate', opts),
  runSeedanceHook: (opts) => ipcRenderer.invoke('run-seedance-hook', opts),
  runSeedanceExtend: (opts) => ipcRenderer.invoke('run-seedance-extend', opts),
  runSeedanceRestyle: (opts) => ipcRenderer.invoke('run-seedance-restyle', opts),
  runSeedanceTrending: (opts) => ipcRenderer.invoke('run-seedance-trending', opts),
  runSeedanceReframe: (opts) => ipcRenderer.invoke('run-seedance-reframe', opts),
  onSeedanceLog: (cb) => onChannel('seedance-log', cb),
});

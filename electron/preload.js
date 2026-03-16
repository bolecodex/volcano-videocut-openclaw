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

  // Log listeners
  onAnalyzeLog: (cb) => onChannel('analyze-log', cb),
  onCutLog: (cb) => onChannel('cut-log', cb),

  // Skills
  listSkills: () => ipcRenderer.invoke('list-skills'),
  getSkillDetail: (name) => ipcRenderer.invoke('get-skill-detail', name),
  importSkill: () => ipcRenderer.invoke('import-skill'),
  deleteSkill: (name) => ipcRenderer.invoke('delete-skill', name),

  // Gateway
  getGatewayStatus: () => ipcRenderer.invoke('gateway-status'),

  // Chat
  chatSend: (opts) => ipcRenderer.invoke('chat-send', opts),
  chatListSessions: () => ipcRenderer.invoke('chat-list-sessions'),
  chatDeleteSession: (key) => ipcRenderer.invoke('chat-delete-session', key),
  onChatStream: (cb) => onChannel('chat-stream', cb),
});

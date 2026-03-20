import React, { useState, useEffect, useCallback, useRef } from 'react';
import ChatPanel from './components/ChatPanel';
import SkillList from './components/SkillList';
import SkillDetail from './components/SkillDetail';

const ICON_MAP = {
  scissors: '✂️', zap: '⚡', heart: '💕', eye: '🔍', home: '🏠', shield: '🛡️',
  fire: '🔥', sparkles: '✨', baby: '👶',
};

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function parseHMS(hms) {
  if (!hms) return 0;
  const parts = hms.split(':').map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] || 0;
}

function App() {
  const api = window.electronAPI;

  // Layout state
  const [skillsCollapsed, setSkillsCollapsed] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState(null);
  const [mainView, setMainView] = useState('editor'); // 'editor' | 'skill'

  const [editorContext, setEditorContext] = useState({ videoDir: '', outputDir: '' });

  const handleSelectSkill = (skillId) => {
    setSelectedSkill(skillId);
    setMainView('skill');
  };

  const handleBackToEditor = () => {
    setSelectedSkill(null);
    setMainView('editor');
  };

  const handleSkillDeleted = () => {
    setSelectedSkill(null);
    setMainView('editor');
  };

  if (!api) {
    return (
      <div className="app-fallback">
        <p>请在 Electron 环境中运行此应用</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1>短剧剪辑助手</h1>
          <span className="header-badge">OpenClaw Studio</span>
        </div>
        <div className="header-right">
          {!skillsCollapsed ? null : (
            <button className="btn btn-ghost" onClick={() => setSkillsCollapsed(false)}>
              🧩 Skills
            </button>
          )}
          {mainView === 'skill' && (
            <button className="btn btn-ghost" onClick={handleBackToEditor}>
              ← 返回剪辑
            </button>
          )}
          {!chatCollapsed ? null : (
            <button className="btn btn-ghost" onClick={() => setChatCollapsed(false)}>
              💬 Agent
            </button>
          )}
        </div>
      </header>

      <div className="layout-three-col">
        <SkillList
          collapsed={skillsCollapsed}
          onToggle={() => setSkillsCollapsed(!skillsCollapsed)}
          onSelectSkill={handleSelectSkill}
          selectedSkill={selectedSkill}
        />

        <div className="main-content">
          {mainView === 'skill' && selectedSkill ? (
            <SkillDetail
              skillName={selectedSkill}
              onClose={handleBackToEditor}
              onDeleted={handleSkillDeleted}
            />
          ) : (
            <VideoEditorView onContextChange={(ctx) => { setEditorContext(ctx); }} />
          )}
        </div>

        <ChatPanel
          collapsed={chatCollapsed}
          onToggle={() => setChatCollapsed(!chatCollapsed)}
          editorContext={editorContext}
        />
      </div>
    </div>
  );
}

// ── Video Editor View (original UI) ──

function VideoEditorView({ onContextChange }) {
  const api = window.electronAPI;

  const [videoDir, setVideoDir] = useState('');
  const [outputDir, setOutputDir] = useState('');
  const [outputName, setOutputName] = useState('');
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('default');
  const [templateContent, setTemplateContent] = useState('');
  const [customRequirements, setCustomRequirements] = useState('');
  const [showPromptPreview, setShowPromptPreview] = useState(false);
  const [editablePrompt, setEditablePrompt] = useState('');
  const [isPromptEditing, setIsPromptEditing] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeLog, setAnalyzeLog] = useState('');
  const [highlightFiles, setHighlightFiles] = useState([]);
  const [highlightData, setHighlightData] = useState(null);
  const [selectedFile, setSelectedFile] = useState('');
  const [outputDirPath, setOutputDirPath] = useState('');
  const [cutting, setCutting] = useState(false);
  const [cutLog, setCutLog] = useState('');
  const [outputFile, setOutputFile] = useState('');
  const [rightTab, setRightTab] = useState('prompt');
  const [postprocessLog, setPostprocessLog] = useState('');
  const [postprocessing, setPostprocessing] = useState('');
  const [qualityScore, setQualityScore] = useState(null);
  const [exportPlatforms, setExportPlatforms] = useState(['douyin', 'toutiao']);
  const [seedanceLog, setSeedanceLog] = useState('');
  const [seedanceRunning, setSeedanceRunning] = useState('');
  const [seedanceHookStyle, setSeedanceHookStyle] = useState('suspense_zoom');
  const [seedanceRestylePreset, setSeedanceRestylePreset] = useState('night_scene');
  const [seedanceTrendingTheme, setSeedanceTrendingTheme] = useState('drama_highlight');
  const [seedanceRatio, setSeedanceRatio] = useState('9:16');
  const [seedanceReframeTarget, setSeedanceReframeTarget] = useState('9:16');
  const [seedanceFast, setSeedanceFast] = useState(false);
  const [seedancePrompt, setSeedancePrompt] = useState('');
  const logEndRef = useRef(null);

  useEffect(() => {
    onContextChange?.({
      videoDir,
      outputDir: outputDirPath || outputDir,
      templates,
      selectedTemplate,
      customRequirements,
    });
  }, [videoDir, outputDir, outputDirPath, templates, selectedTemplate, customRequirements]);

  useEffect(() => {
    if (!api) return;
    api.listPromptTemplates().then((list) => {
      if (list?.length) setTemplates(list);
    });
  }, []);

  useEffect(() => {
    if (!api || !selectedTemplate) return;
    api.readPromptTemplate(selectedTemplate).then((content) => {
      if (content) setTemplateContent(content);
    });
  }, [selectedTemplate]);

  const assembledPrompt = useCallback(() => {
    if (isPromptEditing && editablePrompt) return editablePrompt;
    let prompt = templateContent;
    if (customRequirements.trim()) {
      prompt += `\n\n## 用户额外剪辑要求\n${customRequirements.trim()}`;
    }
    return prompt;
  }, [templateContent, customRequirements, isPromptEditing, editablePrompt]);

  useEffect(() => {
    if (!isPromptEditing) {
      let prompt = templateContent;
      if (customRequirements.trim()) {
        prompt += `\n\n## 用户额外剪辑要求\n${customRequirements.trim()}`;
      }
      setEditablePrompt(prompt);
    }
  }, [templateContent, customRequirements, isPromptEditing]);

  useEffect(() => {
    if (!api?.onAnalyzeLog) return;
    return api.onAnalyzeLog((text) => setAnalyzeLog((p) => p + text));
  }, []);

  useEffect(() => {
    if (!api?.onCutLog) return;
    return api.onCutLog((text) => setCutLog((p) => p + text));
  }, []);

  useEffect(() => {
    if (!api?.onPostprocessLog) return;
    return api.onPostprocessLog((text) => setPostprocessLog((p) => p + text));
  }, []);

  useEffect(() => {
    if (!api?.onSeedanceLog) return;
    return api.onSeedanceLog((text) => setSeedanceLog((p) => p + text));
  }, []);

  useEffect(() => {
    if (!selectedFile || !outputDirPath || !api) return;
    api.getHighlightData(outputDirPath, selectedFile)
      .then(setHighlightData)
      .catch(() => setHighlightData(null));
  }, [selectedFile, outputDirPath]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [analyzeLog, cutLog]);

  const handleSelectVideoDir = async () => {
    const dir = await api.selectVideoDir();
    if (dir) setVideoDir(dir);
  };

  const handleSelectOutputDir = async () => {
    const dir = await api.selectOutputDir();
    if (dir) setOutputDir(dir);
  };

  const handleAnalyze = async () => {
    if (!videoDir) return;
    setAnalyzing(true);
    setAnalyzeLog('');
    setHighlightData(null);
    setHighlightFiles([]);
    setOutputFile('');
    setRightTab('log');

    const result = await api.analyzeVideos({
      videoDir,
      outputDir: outputDir || undefined,
      fullPromptText: assembledPrompt(),
      outputName: outputName || undefined,
    });

    setAnalyzing(false);
    if (result?.success) {
      setHighlightFiles(result.highlightFiles || []);
      setOutputDirPath(result.outputDir);
      if (result.highlightFiles?.length) {
        setSelectedFile(result.highlightFiles[0]);
        setRightTab('results');
      }
    } else {
      setAnalyzeLog((p) => p + '\n[错误] ' + (result?.error || '分析失败'));
    }
  };

  const handleCut = async () => {
    if (!selectedFile || !outputDirPath || !videoDir) return;
    setCutting(true);
    setCutLog('');
    setOutputFile('');
    setRightTab('log');

    const result = await api.cutVideo({
      highlightsJson: outputDirPath,
      highlightsFile: selectedFile,
      sourceVideoDir: videoDir,
      outputDir: outputDirPath || undefined,
      outputName: outputName || undefined,
    });

    setCutting(false);
    if (result?.success) {
      setOutputFile(result.outputFile);
      setRightTab('results');
    } else {
      setCutLog((p) => p + '\n[错误] ' + (result?.error || '剪辑失败'));
    }
  };

  const handleOpenOutput = () => {
    if (outputDirPath) api.openOutputFolder(outputDirPath);
  };

  const handlePostprocess = async (action) => {
    if (!outputDirPath && !videoDir) return;
    setPostprocessing(action);
    setPostprocessLog('');
    setRightTab('log');

    try {
      let result;
      switch (action) {
        case 'asr':
          result = await api.runAsr({ videoDir, outputDir: outputDirPath || undefined });
          break;
        case 'scene':
          result = await api.runSceneDetect({ videoDir, outputDir: outputDirPath || undefined });
          break;
        case 'subtitle':
          if (outputFile) {
            const videoPath = `${outputDirPath}/${outputFile}`;
            const srtFile = `asr_${outputFile.replace('promo_', '').replace('.mp4', '')}.srt`;
            const srtPath = `${outputDirPath}/${srtFile}`;
            result = await api.runBurnSubtitle({ videoPath, subtitlePath: srtPath });
          }
          break;
        case 'cover':
          if (outputFile) {
            result = await api.runGenCover({ videoPath: `${outputDirPath}/${outputFile}`, outputDir: outputDirPath });
          }
          break;
        case 'score':
          if (outputFile) {
            result = await api.runQualityScore({ videoPath: `${outputDirPath}/${outputFile}`, outputDir: outputDirPath });
            if (result?.score) setQualityScore(result.score);
          }
          break;
        case 'export':
          if (outputFile) {
            result = await api.runPlatformExport({
              videoPath: `${outputDirPath}/${outputFile}`,
              outputDir: outputDirPath ? `${outputDirPath}/exports` : undefined,
              platforms: exportPlatforms,
            });
          }
          break;
        default:
          break;
      }
      if (result && !result.success) {
        setPostprocessLog((p) => p + `\n[错误] ${result.error}`);
      }
    } catch (err) {
      setPostprocessLog((p) => p + `\n[错误] ${err.message}`);
    }
    setPostprocessing('');
  };

  const handleSeedance = async (action) => {
    setSeedanceRunning(action);
    setSeedanceLog('');
    setRightTab('seedance');

    const outDir = outputDirPath || outputDir || 'video/output';
    const commonOpts = {
      outputDir: outDir,
      ratio: seedanceRatio,
      resolution: '720p',
      fast: seedanceFast,
    };

    try {
      let result;
      switch (action) {
        case 'replicate':
          if (outputFile) {
            result = await api.runSeedanceReplicate({
              ...commonOpts,
              reference: `${outputDirPath}/${outputFile}`,
              prompt: seedancePrompt || undefined,
            });
          }
          break;
        case 'hook':
          result = await api.runSeedanceHook({
            ...commonOpts,
            style: seedanceHookStyle,
            prompt: seedancePrompt || undefined,
            sourceVideo: outputFile ? `${outputDirPath}/${outputFile}` : undefined,
            duration: 5,
          });
          break;
        case 'extend':
          if (outputFile) {
            result = await api.runSeedanceExtend({
              ...commonOpts,
              video: `${outputDirPath}/${outputFile}`,
              prompt: seedancePrompt || undefined,
              duration: 8,
              chain: 1,
            });
          }
          break;
        case 'restyle':
          if (outputFile) {
            result = await api.runSeedanceRestyle({
              ...commonOpts,
              video: `${outputDirPath}/${outputFile}`,
              style: seedanceRestylePreset,
              prompt: seedancePrompt || undefined,
            });
          }
          break;
        case 'trending':
          result = await api.runSeedanceTrending({
            ...commonOpts,
            theme: seedanceTrendingTheme,
            count: 4,
            duration: 5,
          });
          break;
        case 'reframe':
          if (outputFile) {
            result = await api.runSeedanceReframe({
              ...commonOpts,
              video: `${outputDirPath}/${outputFile}`,
              targetRatio: seedanceReframeTarget,
              prompt: seedancePrompt || undefined,
              duration: 8,
            });
          }
          break;
        default:
          break;
      }
      if (result && !result.success) {
        setSeedanceLog((p) => p + `\n[错误] ${result.error}`);
      }
    } catch (err) {
      setSeedanceLog((p) => p + `\n[错误] ${err.message}`);
    }
    setSeedanceRunning('');
  };

  return (
    <div className="editor-layout">
      <div className="panel-left">
        {/* -- Source & Output compact bar -- */}
        <div className="compact-section">
          <div className="compact-section-title">
            <span className="card-step">1</span>
            <span>素材</span>
          </div>
          <div className="compact-fields">
            <div className="field-row">
              <input type="text" readOnly value={videoDir} placeholder="选择视频文件夹" className="input input-sm" />
              <button onClick={handleSelectVideoDir} className="btn btn-secondary btn-sm">选择</button>
            </div>
            <div className="field-row-pair">
              <input type="text" readOnly value={outputDir} placeholder="输出目录（可选）" className="input input-sm" />
              <button onClick={handleSelectOutputDir} className="btn btn-secondary btn-sm">选择</button>
              <input
                type="text"
                value={outputName}
                onChange={(e) => setOutputName(e.target.value)}
                placeholder="输出名称（可选）"
                className="input input-sm"
              />
            </div>
          </div>
        </div>

        {/* -- Template selection -- */}
        <div className="compact-section compact-section-grow">
          <div className="compact-section-title">
            <span className="card-step">2</span>
            <span>剪辑模板</span>
            <button
              className="btn btn-ghost btn-xs"
              onClick={() => { setShowPromptPreview(!showPromptPreview); setRightTab('prompt'); }}
            >
              {showPromptPreview ? '收起' : '查看提示词'}
            </button>
          </div>
          <div className="template-grid-compact">
            {templates.map((tpl) => (
              <button
                key={tpl.id}
                className={`tpl-chip ${selectedTemplate === tpl.id ? 'active' : ''}`}
                onClick={() => { setSelectedTemplate(tpl.id); setIsPromptEditing(false); }}
                title={tpl.description}
              >
                <span className="tpl-chip-icon">{ICON_MAP[tpl.icon] || '📝'}</span>
                <span className="tpl-chip-name">{tpl.name}</span>
              </button>
            ))}
          </div>
          <textarea
            value={customRequirements}
            onChange={(e) => { setCustomRequirements(e.target.value); setIsPromptEditing(false); }}
            placeholder="额外剪辑要求（可选）：如删除片尾亮光、开头从第3集冲突开始..."
            className="textarea textarea-sm"
            rows={2}
          />
        </div>

        {/* -- Action bar -- */}
        <div className="compact-action-bar">
          <button
            onClick={handleAnalyze}
            disabled={!videoDir || analyzing}
            className="btn btn-primary"
          >
            {analyzing && <span className="spinner" />}
            {analyzing ? '分析中...' : '开始分析'}
          </button>

          {highlightFiles.length > 0 && (
            <>
              <button
                onClick={handleCut}
                disabled={cutting || !selectedFile}
                className="btn btn-accent"
              >
                {cutting && <span className="spinner" />}
                {cutting ? '剪辑中...' : '开始剪辑'}
              </button>
              {outputDirPath && (
                <button onClick={handleOpenOutput} className="btn btn-secondary btn-sm">
                  打开输出
                </button>
              )}
            </>
          )}
          {outputFile && (
            <span className="output-inline">🎬 <strong>{outputFile}</strong></span>
          )}
        </div>
      </div>

      <div className="panel-right">
        <div className="tab-bar">
          <button className={`tab ${rightTab === 'prompt' ? 'active' : ''}`} onClick={() => setRightTab('prompt')}>
            提示词
          </button>
          <button className={`tab ${rightTab === 'results' ? 'active' : ''}`} onClick={() => setRightTab('results')}>
            分析结果
          </button>
          <button className={`tab ${rightTab === 'postprocess' ? 'active' : ''}`} onClick={() => setRightTab('postprocess')}>
            后期处理
            {postprocessing && <span className="tab-dot" />}
          </button>
          <button className={`tab ${rightTab === 'seedance' ? 'active' : ''}`} onClick={() => setRightTab('seedance')}>
            Seedance
            {seedanceRunning && <span className="tab-dot" />}
          </button>
          <button className={`tab ${rightTab === 'log' ? 'active' : ''}`} onClick={() => setRightTab('log')}>
            日志
            {(analyzing || cutting) && <span className="tab-dot" />}
          </button>
        </div>

        {rightTab === 'prompt' && (
          <div className="tab-content">
            <div className="prompt-toolbar">
              <span className="prompt-label">
                当前模板：{templates.find((t) => t.id === selectedTemplate)?.name || selectedTemplate}
              </span>
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={isPromptEditing}
                  onChange={(e) => setIsPromptEditing(e.target.checked)}
                />
                <span>编辑模式</span>
              </label>
            </div>
            {isPromptEditing ? (
              <textarea
                className="prompt-editor"
                value={editablePrompt}
                onChange={(e) => setEditablePrompt(e.target.value)}
              />
            ) : (
              <div className="prompt-viewer">
                <PromptRenderer text={assembledPrompt()} />
              </div>
            )}
          </div>
        )}

        {rightTab === 'results' && (
          <div className="tab-content">
            {highlightFiles.length > 0 && (
              <div className="results-file-bar">
                <select value={selectedFile} onChange={(e) => setSelectedFile(e.target.value)} className="select">
                  {highlightFiles.map((f) => (
                    <option key={f} value={f}>{f.replace('highlights_', '').replace('.json', '')}</option>
                  ))}
                </select>
              </div>
            )}
            {highlightData ? (
              <ResultsViewer data={highlightData} />
            ) : (
              <div className="empty-state">
                <span className="empty-icon">📊</span>
                <p>分析完成后将在此展示结果</p>
              </div>
            )}
          </div>
        )}

        {rightTab === 'postprocess' && (
          <div className="tab-content">
            <div className="postprocess-panel">
              <div className="pp-section">
                <h4 className="pp-title">预处理</h4>
                <div className="pp-actions">
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!videoDir || !!postprocessing}
                    onClick={() => handlePostprocess('asr')}
                  >
                    {postprocessing === 'asr' && <span className="spinner" />}
                    🎤 ASR 提取台词
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!videoDir || !!postprocessing}
                    onClick={() => handlePostprocess('scene')}
                  >
                    {postprocessing === 'scene' && <span className="spinner" />}
                    🎬 场景检测
                  </button>
                </div>
              </div>

              <div className="pp-section">
                <h4 className="pp-title">后期处理</h4>
                <div className="pp-actions">
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!outputFile || !!postprocessing}
                    onClick={() => handlePostprocess('subtitle')}
                  >
                    {postprocessing === 'subtitle' && <span className="spinner" />}
                    📝 烧录字幕
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!outputFile || !!postprocessing}
                    onClick={() => handlePostprocess('cover')}
                  >
                    {postprocessing === 'cover' && <span className="spinner" />}
                    🖼️ 生成封面
                  </button>
                </div>
              </div>

              <div className="pp-section">
                <h4 className="pp-title">质量 & 导出</h4>
                <div className="pp-actions">
                  <button
                    className="btn btn-accent btn-sm"
                    disabled={!outputFile || !!postprocessing}
                    onClick={() => handlePostprocess('score')}
                  >
                    {postprocessing === 'score' && <span className="spinner" />}
                    📊 AI 质量评分
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={!outputFile || !!postprocessing}
                    onClick={() => handlePostprocess('export')}
                  >
                    {postprocessing === 'export' && <span className="spinner" />}
                    📤 多平台导出
                  </button>
                </div>
                <div className="pp-export-platforms">
                  {[
                    { id: 'douyin', label: '抖音/快手' },
                    { id: 'toutiao', label: '头条' },
                    { id: 'wechat_video', label: '视频号' },
                    { id: 'moments', label: '朋友圈' },
                  ].map((p) => (
                    <label key={p.id} className="pp-platform-check">
                      <input
                        type="checkbox"
                        checked={exportPlatforms.includes(p.id)}
                        onChange={(e) => {
                          setExportPlatforms((prev) =>
                            e.target.checked ? [...prev, p.id] : prev.filter((x) => x !== p.id)
                          );
                        }}
                      />
                      <span>{p.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {qualityScore && (
                <div className="pp-section pp-score-card">
                  <h4 className="pp-title">
                    质量评分: {qualityScore.overall_score}/100
                    <span className={`pp-grade pp-grade-${(qualityScore.grade || 'C').toLowerCase()}`}>
                      {qualityScore.grade}
                    </span>
                  </h4>
                  <div className="pp-score-dims">
                    {Object.entries(qualityScore.scores || {}).map(([key, val]) => (
                      <div key={key} className="pp-score-dim">
                        <span className="pp-dim-label">{key.replace('_score', '').replace('_', ' ')}</span>
                        <div className="pp-dim-bar">
                          <div className="pp-dim-fill" style={{ width: `${val}%` }} />
                        </div>
                        <span className="pp-dim-val">{val}</span>
                      </div>
                    ))}
                  </div>
                  {qualityScore.suggestions?.length > 0 && (
                    <div className="pp-suggestions">
                      <strong>改进建议：</strong>
                      <ul>
                        {qualityScore.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {postprocessLog && (
                <pre className="log-view pp-log">{postprocessLog}</pre>
              )}
            </div>
          </div>
        )}

        {rightTab === 'seedance' && (
          <div className="tab-content">
            <div className="postprocess-panel seedance-panel">
              <div className="pp-section">
                <h4 className="pp-title">🎬 Seedance 2.0 AI视频生成</h4>
                <div className="seedance-config">
                  <div className="field-row">
                    <label className="seedance-label">画面比例</label>
                    <select className="select select-sm" value={seedanceRatio} onChange={(e) => setSeedanceRatio(e.target.value)}>
                      <option value="9:16">9:16 竖屏</option>
                      <option value="16:9">16:9 横屏</option>
                      <option value="1:1">1:1 方形</option>
                      <option value="adaptive">自适应</option>
                    </select>
                    <label className="toggle-label seedance-fast-toggle">
                      <input type="checkbox" checked={seedanceFast} onChange={(e) => setSeedanceFast(e.target.checked)} />
                      <span>快速模式</span>
                    </label>
                  </div>
                  <input
                    className="input input-sm"
                    value={seedancePrompt}
                    onChange={(e) => setSeedancePrompt(e.target.value)}
                    placeholder="自定义提示词（可选）"
                  />
                </div>
              </div>

              <div className="pp-section">
                <h4 className="pp-title">🔥 爆款复刻</h4>
                <p className="pp-desc">用剪辑好的视频作为参考，复刻其风格和运镜</p>
                <div className="pp-actions">
                  <button
                    className="btn btn-accent btn-sm"
                    disabled={!outputFile || !!seedanceRunning}
                    onClick={() => handleSeedance('replicate')}
                  >
                    {seedanceRunning === 'replicate' && <span className="spinner" />}
                    复刻视频风格
                  </button>
                </div>
              </div>

              <div className="pp-section">
                <h4 className="pp-title">🎣 开场钩子</h4>
                <p className="pp-desc">生成吸睛开场，提升3秒留存率</p>
                <div className="seedance-preset-row">
                  <select className="select select-sm" value={seedanceHookStyle} onChange={(e) => setSeedanceHookStyle(e.target.value)}>
                    <option value="suspense_zoom">悬疑推进</option>
                    <option value="explosion_reveal">爆炸揭示</option>
                    <option value="emotional_rain">情感雨景</option>
                    <option value="epic_slow_motion">史诗慢镜</option>
                    <option value="glitch_rewind">故障回放</option>
                    <option value="luxury_reveal">奢华揭幕</option>
                    <option value="mystery_approach">神秘逼近</option>
                  </select>
                  <button
                    className="btn btn-accent btn-sm"
                    disabled={!!seedanceRunning}
                    onClick={() => handleSeedance('hook')}
                  >
                    {seedanceRunning === 'hook' && <span className="spinner" />}
                    生成钩子
                  </button>
                </div>
              </div>

              <div className="pp-section">
                <h4 className="pp-title">⏩ 智能续写</h4>
                <p className="pp-desc">AI续写片段尾部，自动延长视频时长</p>
                <div className="pp-actions">
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!outputFile || !!seedanceRunning}
                    onClick={() => handleSeedance('extend')}
                  >
                    {seedanceRunning === 'extend' && <span className="spinner" />}
                    续写片段
                  </button>
                </div>
              </div>

              <div className="pp-section">
                <h4 className="pp-title">🎨 风格化编辑</h4>
                <p className="pp-desc">改变画面风格——夜景、雪景、赛博朋克…</p>
                <div className="seedance-preset-row">
                  <select className="select select-sm" value={seedanceRestylePreset} onChange={(e) => setSeedanceRestylePreset(e.target.value)}>
                    <option value="night_scene">夜景月光</option>
                    <option value="snow_effect">冬日飘雪</option>
                    <option value="rain_mood">雨夜霓虹</option>
                    <option value="golden_hour">黄金时刻</option>
                    <option value="luxury_upgrade">奢华质感</option>
                    <option value="cyberpunk">赛博朋克</option>
                    <option value="ancient_chinese">中国古风</option>
                    <option value="horror_tint">恐怖氛围</option>
                  </select>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!outputFile || !!seedanceRunning}
                    onClick={() => handleSeedance('restyle')}
                  >
                    {seedanceRunning === 'restyle' && <span className="spinner" />}
                    风格化
                  </button>
                </div>
              </div>

              <div className="pp-section">
                <h4 className="pp-title">📐 横竖屏比例转换</h4>
                <p className="pp-desc">横屏转竖屏、竖屏转横屏，AI 智能重构图</p>
                <div className="seedance-preset-row">
                  <select className="select select-sm" value={seedanceReframeTarget} onChange={(e) => setSeedanceReframeTarget(e.target.value)}>
                    <option value="9:16">横转竖 9:16</option>
                    <option value="16:9">竖转横 16:9</option>
                    <option value="1:1">转为方形 1:1</option>
                  </select>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!outputFile || !!seedanceRunning}
                    onClick={() => handleSeedance('reframe')}
                  >
                    {seedanceRunning === 'reframe' && <span className="spinner" />}
                    比例转换
                  </button>
                </div>
              </div>

              <div className="pp-section">
                <h4 className="pp-title">📈 热点素材批量生成</h4>
                <p className="pp-desc">一键批量生成4条主题短视频素材</p>
                <div className="seedance-preset-row">
                  <select className="select select-sm" value={seedanceTrendingTheme} onChange={(e) => setSeedanceTrendingTheme(e.target.value)}>
                    <option value="drama_highlight">戏剧高光</option>
                    <option value="visual_spectacle">视觉奇观</option>
                    <option value="product_tease">产品预告</option>
                    <option value="emotion_hook">情感触动</option>
                    <option value="action_energy">高能动作</option>
                  </select>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={!!seedanceRunning}
                    onClick={() => handleSeedance('trending')}
                  >
                    {seedanceRunning === 'trending' && <span className="spinner" />}
                    批量生成 (×4)
                  </button>
                </div>
              </div>

              {seedanceLog && (
                <pre className="log-view pp-log">{seedanceLog}</pre>
              )}
            </div>
          </div>
        )}

        {rightTab === 'log' && (
          <div className="tab-content">
            <pre className="log-view">
              {analyzeLog || cutLog || '等待操作...'}
              <span ref={logEndRef} />
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ──

function PromptRenderer({ text }) {
  if (!text) return <div className="empty-state"><p>加载中...</p></div>;

  const lines = text.split('\n');
  return (
    <div className="prompt-lines">
      {lines.map((line, i) => {
        let cls = 'prompt-line';
        if (line.startsWith('## ')) cls += ' prompt-h2';
        else if (line.startsWith('### ')) cls += ' prompt-h3';
        else if (line.startsWith('- **') || line.startsWith('- ')) cls += ' prompt-list';
        else if (line.startsWith('```')) cls += ' prompt-code';
        else if (line.includes('必须删除') || line.includes('应该删除') || line.includes('违规')) cls += ' prompt-remove';
        else if (line.includes('保留') || line.includes('segments_to_keep')) cls += ' prompt-keep';
        return <div key={i} className={cls}>{line || '\u00A0'}</div>;
      })}
    </div>
  );
}

function ResultsViewer({ data }) {
  const { drama_name, summary, episodes, hook, segments_to_keep, segments_to_remove, final_structure, total_source_duration_seconds, versions } = data;
  const keepDur = (segments_to_keep || []).reduce((s, seg) => s + (seg.duration_seconds || 0), 0);
  const hookDur = hook?.enabled ? (parseHMS(hook.source_end) - parseHMS(hook.source_start)) : 0;
  const totalKeep = keepDur + hookDur;
  const ratio = total_source_duration_seconds ? Math.round((totalKeep / total_source_duration_seconds) * 100) : 0;

  return (
    <div className="results">
      <div className="result-card summary-card">
        <h3>{drama_name || '未命名短剧'}</h3>
        <p className="summary-text">{summary}</p>
        <div className="stat-row">
          <div className="stat">
            <span className="stat-value">{episodes?.length || 0}</span>
            <span className="stat-label">集数</span>
          </div>
          <div className="stat">
            <span className="stat-value">{formatTime(totalKeep)}</span>
            <span className="stat-label">保留时长</span>
          </div>
          <div className="stat">
            <span className="stat-value">{formatTime(total_source_duration_seconds || 0)}</span>
            <span className="stat-label">原片总时长</span>
          </div>
          <div className="stat">
            <span className="stat-value">{ratio}%</span>
            <span className="stat-label">保留率</span>
          </div>
        </div>
      </div>

      {hook?.enabled && (
        <div className="result-card hook-card">
          <div className="hook-badge">钩子</div>
          <div className="hook-info">
            <span className="hook-source">{hook.source_file}</span>
            <span className="hook-time">{hook.source_start} → {hook.source_end}</span>
          </div>
          <p className="hook-reason">{hook.reason}</p>
          <span className="hook-reuse">在原始位置重复出现 ({hook.reuse_at})</span>
        </div>
      )}

      <div className="result-card">
        <h4>片段时间轴</h4>
        <SegmentTimeline
          episodes={episodes || []}
          keeps={segments_to_keep || []}
          removes={segments_to_remove || []}
          totalDuration={total_source_duration_seconds}
        />
      </div>

      <div className="result-card">
        <h4>保留片段 ({segments_to_keep?.length || 0})</h4>
        <div className="segment-list">
          {(segments_to_keep || []).map((seg) => (
            <div key={seg.id} className="segment-item keep">
              <div className="segment-header">
                <span className="segment-id">#{seg.id}</span>
                <span className="segment-source">{seg.source_file}</span>
                <span className="segment-time">{seg.start_time} → {seg.end_time}</span>
                <span className="segment-dur">{seg.duration_seconds}s</span>
              </div>
              <p className="segment-content">{seg.content}</p>
            </div>
          ))}
        </div>
      </div>

      {segments_to_remove?.length > 0 && (
        <div className="result-card">
          <h4>删除片段 ({segments_to_remove.length})</h4>
          <div className="segment-list">
            {segments_to_remove.map((seg, i) => (
              <div key={i} className="segment-item remove">
                <div className="segment-header">
                  <span className="segment-source">{seg.source_file}</span>
                  <span className="segment-time">{seg.start_time} → {seg.end_time}</span>
                </div>
                <p className="segment-reason">{seg.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {final_structure && (
        <div className="result-card">
          <h4>最终结构</h4>
          <p className="structure-desc">{final_structure.description}</p>
          <div className="structure-order">
            {(final_structure.segment_order || []).map((item, i) => (
              <span key={i} className={`order-chip ${item.type}`}>
                {item.type === 'hook' ? '🎯 钩子' : `#${item.id}`}
              </span>
            ))}
          </div>
          <span className="structure-dur">
            预计时长：{formatTime(final_structure.estimated_duration_seconds || 0)}
          </span>
        </div>
      )}

      {versions?.length > 0 && (
        <div className="result-card">
          <h4>多版本方案 ({versions.length})</h4>
          <div className="versions-list">
            {versions.map((ver, i) => {
              const vName = ver.name || ver.type || `版本${i + 1}`;
              const vSegs = ver.segments_to_keep?.length || 0;
              const vDur = ver.final_structure?.estimated_duration_seconds || 0;
              return (
                <div key={i} className="version-card">
                  <div className="version-header">
                    <span className="version-name">{vName}</span>
                    <span className="version-stats">{vSegs} 段 · {formatTime(vDur)}</span>
                  </div>
                  {ver.final_structure?.description && (
                    <p className="version-desc">{ver.final_structure.description}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function SegmentTimeline({ episodes, keeps, removes }) {
  if (!episodes?.length) return null;

  const epMap = {};
  episodes.forEach((ep) => { epMap[ep] = { keeps: [], removes: [] }; });
  keeps.forEach((seg) => {
    if (epMap[seg.source_file]) epMap[seg.source_file].keeps.push(seg);
  });
  removes.forEach((seg) => {
    if (epMap[seg.source_file]) epMap[seg.source_file].removes.push(seg);
  });

  return (
    <div className="timeline">
      {episodes.map((ep) => {
        const epKeeps = epMap[ep]?.keeps || [];
        const epRemoves = epMap[ep]?.removes || [];
        const allSegs = [
          ...epKeeps.map((s) => ({ ...s, type: 'keep', startSec: parseHMS(s.start_time), endSec: parseHMS(s.end_time) })),
          ...epRemoves.map((s) => ({ ...s, type: 'remove', startSec: parseHMS(s.start_time), endSec: parseHMS(s.end_time) })),
        ].sort((a, b) => a.startSec - b.startSec);

        const maxSec = allSegs.length ? Math.max(...allSegs.map((s) => s.endSec)) : 120;

        return (
          <div key={ep} className="timeline-row">
            <span className="timeline-label" title={ep}>{ep.replace(/\.(mp4|mov|avi|webm)$/i, '')}</span>
            <div className="timeline-bar">
              {allSegs.map((seg, i) => {
                const left = (seg.startSec / maxSec) * 100;
                const width = ((seg.endSec - seg.startSec) / maxSec) * 100;
                return (
                  <div
                    key={i}
                    className={`timeline-seg ${seg.type}`}
                    style={{ left: `${left}%`, width: `${Math.max(width, 0.5)}%` }}
                    title={`${seg.start_time || ''} → ${seg.end_time || ''} (${seg.type === 'keep' ? '保留' : '删除'})`}
                  />
                );
              })}
            </div>
          </div>
        );
      })}
      <div className="timeline-legend">
        <span className="legend-item"><span className="legend-dot keep" /> 保留</span>
        <span className="legend-item"><span className="legend-dot remove" /> 删除</span>
      </div>
    </div>
  );
}

export default App;

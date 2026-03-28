import React, { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/** 与参考 UI 一致：分栏类型 */
const MENTION_TABS = [
  { id: 'all', label: '全部', icon: '📋' },
  { id: 'file', label: '文件', icon: '📄' },
  { id: 'template', label: '模版', icon: '✂️' },
  { id: 'character', label: '角色', icon: '👥' },
  { id: 'scene', label: '场景', icon: '🪟' },
  { id: 'storyboard', label: '分镜', icon: '🎬' },
  { id: 'audio', label: '音频', icon: '🔊' },
  { id: 'video', label: '视频', icon: '🎥' },
  { id: 'skill', label: '技能', icon: '⚡' },
];

const MENTION_LIST_LIMIT = 100;
const CHAT_INPUT_MIN_PX = 92;
const CHAT_INPUT_MAX_PX = 280;

function joinPath(dir, file) {
  if (!dir || !file) return file || dir || '';
  const d = String(dir).replace(/[/\\]+$/, '');
  const sep = d.includes('\\') ? '\\' : '/';
  return `${d}${sep}${file}`;
}

function mentionIconForCategory(cat) {
  const t = MENTION_TABS.find((x) => x.id === cat);
  return t?.icon || '📎';
}

/** @ 可作为提及触发：行首，或前一个字符不是英文/数字/_（避免 email 里的 user@） */
function isMentionAt(textBeforeCursor, atIdx) {
  if (atIdx < 0) return false;
  if (atIdx === 0) return true;
  const prev = textBeforeCursor[atIdx - 1];
  return !/[a-zA-Z0-9_]/.test(prev);
}

function mergeProgressFocus(prev, next) {
  const o = { ...(prev && typeof prev === 'object' ? prev : {}) };
  if (!next || typeof next !== 'object') return o;
  for (const k of ['skill', 'video', 'phase', 'note']) {
    if (next[k] != null && String(next[k]).trim() !== '') o[k] = String(next[k]).trim();
  }
  return o;
}

function mentionFileBasename(label) {
  if (!label) return '';
  const s = String(label).replace(/\\/g, '/');
  return s.split('/').pop() || s;
}

/** 从用户 @ 引用得到初始「当前在处理什么」 */
function buildInitialProgressFocus(mentions) {
  const list = mentions || [];
  const skills = list.filter((m) => m.category === 'skill').map((m) => m.label);
  const templates = list.filter((m) => m.category === 'template').map((m) => m.label);
  const files = list.filter((m) => ['video', 'file'].includes(m.category)).map((m) => m.label);
  const basenames = files.map(mentionFileBasename).filter(Boolean);
  const skillText =
    skills.length === 0 ? '' : skills.length === 1 ? skills[0] : `将按顺序涉及：${skills.join(' → ')}`;
  const videoText =
    basenames.length === 0
      ? ''
      : basenames.length === 1
        ? basenames[0]
        : `${basenames.length} 个文件：${basenames.join('、')}`;
  return mergeProgressFocus(
    {},
    {
      ...(skillText ? { skill: skillText } : {}),
      ...(videoText ? { video: videoText } : {}),
      ...(templates.length ? { note: `剪辑模版：${templates.join('、')}` } : {}),
      phase: '已接收指令，等待 Agent 开始执行…',
    },
  );
}

/** 长时间无流式事件时写入日志：只陈述界面已掌握的进度，不用「可能」 */
function buildSilentProgressLine(waitedSec, assistantMsg) {
  const f = assistantMsg?.progressFocus && typeof assistantMsg.progressFocus === 'object'
    ? assistantMsg.progressFocus
    : {};
  const runningTools = (assistantMsg?.tools || [])
    .filter((t) => t.status === 'running')
    .map((t) => t.title || t.name)
    .filter(Boolean);

  const segments = [];
  if (f.skill) segments.push(`技能：${f.skill}`);
  if (f.video) segments.push(`素材：${f.video}`);
  if (f.phase) segments.push(`步骤：${f.phase}`);
  if (f.note) segments.push(`说明：${f.note}`);
  if (runningTools.length) segments.push(`运行中工具：${runningTools.join('、')}`);

  const head = `⏳ 已 ${waitedSec}s 无新的网关流式事件`;
  if (segments.length) {
    return `${head}。当前界面记录的进度 — ${segments.join(' · ')}。长任务（例如视频分析）会持续数十秒至数分钟无新日志，属正常；要中断请点「停止」。`;
  }
  return `${head}。当前尚未解析到技能/素材/工具行（请同时看上方「当前处理」）。长任务会持续较久无输出；要中断请点「停止」。`;
}

function ChatPanel({ collapsed, onToggle, editorContext }) {
  const api = window.electronAPI;
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [gatewayConnected, setGatewayConnected] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [sessionKey, setSessionKey] = useState('studio:videocut:default');
  const [showSessions, setShowSessions] = useState(false);
  const messagesEndRef = useRef(null);
  const streamBufferRef = useRef('');
  const thinkingBufferRef = useRef('');
  const lastStreamEventAtRef = useRef(0);
  const MAX_PROGRESS_LINES = 80;

  const capProgressLog = useCallback((log) => {
    if (!log || log.length <= MAX_PROGRESS_LINES) return log;
    return log.slice(-MAX_PROGRESS_LINES);
  }, []);

  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionTab, setMentionTab] = useState('all');
  const [mentionIdx, setMentionIdx] = useState(0);
  const [mentionItems, setMentionItems] = useState([]);
  const [mentions, setMentions] = useState([]);
  const mentionAnchorRef = useRef(null);
  const mentionOpenRef = useRef(false);
  const inputRef = useRef(null);
  const mentionCacheRef = useRef({ items: null, at: 0, ctxKey: '' });
  const MENTION_CACHE_MS = 25000;

  useEffect(() => {
    if (!api) return;
    const check = () => api.getGatewayStatus().then((s) => setGatewayConnected(s?.connected ?? false));
    check();
    const interval = setInterval(check, 5000);
    return () => clearInterval(interval);
  }, [api]);

  useEffect(() => {
    if (!api?.onChatStream) return;
    return api.onChatStream((evt) => {
      lastStreamEventAtRef.current = Date.now();
      switch (evt.type) {
        case 'progress':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming && evt.message) {
              const log = capProgressLog([...(last.progressLog || []), evt.message]);
              return [...prev.slice(0, -1), { ...last, progressLog: log }];
            }
            return prev;
          });
          break;

        case 'progress_detail':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming && evt.detail) {
              const progressFocus = mergeProgressFocus(last.progressFocus, evt.detail);
              return [...prev.slice(0, -1), { ...last, progressFocus }];
            }
            return prev;
          });
          break;

        case 'text':
          streamBufferRef.current += (evt.delta || evt.content || '');
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming) {
              return [...prev.slice(0, -1), { ...last, content: streamBufferRef.current }];
            }
            return prev;
          });
          break;

        case 'thinking':
          thinkingBufferRef.current += (evt.delta || evt.content || '');
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming) {
              return [...prev.slice(0, -1), { ...last, thinking: thinkingBufferRef.current }];
            }
            return prev;
          });
          break;

        case 'tool_start':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming) {
              const tools = [...(last.tools || []), { ...evt.toolCall, phase: 'running' }];
              return [...prev.slice(0, -1), { ...last, tools }];
            }
            return prev;
          });
          break;

        case 'tool_update':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming && last.tools?.length) {
              const tools = last.tools.map((t) =>
                t.id === evt.toolCall?.id ? { ...t, ...evt.toolCall } : t
              );
              return [...prev.slice(0, -1), { ...last, tools }];
            }
            return prev;
          });
          break;

        case 'tool_output': {
          const chunk = evt.content ?? '';
          if (!chunk) break;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role !== 'assistant' || !last.streaming) return prev;
            const tools = last.tools || [];
            if (!tools.length) return prev;
            const tid = evt.toolCall?.id;
            let targetId = tid;
            if (!tid || !tools.some((t) => t.id === tid)) {
              const running = [...tools].reverse().find((t) => t.status === 'running');
              if (running) targetId = running.id;
            }
            if (!targetId) return prev;
            const nextTools = tools.map((t) =>
              t.id === targetId ? { ...t, output: (t.output || '') + chunk } : t
            );
            return [...prev.slice(0, -1), { ...last, tools: nextTools }];
          });
          break;
        }

        case 'stopped':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming) {
              const log = capProgressLog([...(last.progressLog || []), '— 你已停止生成']);
              return [...prev.slice(0, -1), { ...last, streaming: false, stopped: true, progressLog: log }];
            }
            return prev;
          });
          setSending(false);
          break;

        case 'error':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming) {
              return [...prev.slice(0, -1), { ...last, streaming: false, error: evt.error }];
            }
            return [...prev, { role: 'system', content: evt.error }];
          });
          setSending(false);
          break;

        case 'done':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last.streaming) {
              return [...prev.slice(0, -1), { ...last, streaming: false }];
            }
            return prev;
          });
          setSending(false);
          break;

        default:
          break;
      }
    });
  }, [api, capProgressLog]);

  /** 长时间无流式事件：用 progressFocus + 运行中工具拼明确进度，避免模糊「可能」 */
  useEffect(() => {
    if (!sending) return;
    const tick = setInterval(() => {
      const silentMs = Date.now() - lastStreamEventAtRef.current;
      if (silentMs < 45000) return;
      lastStreamEventAtRef.current = Date.now();
      const waitedSec = Math.round(silentMs / 1000);
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role !== 'assistant' || !last.streaming) return prev;
        const line = buildSilentProgressLine(waitedSec, last);
        const log = capProgressLog([...(last.progressLog || []), line]);
        return [...prev.slice(0, -1), { ...last, progressLog: log }];
      });
    }, 12000);
    return () => clearInterval(tick);
  }, [sending, capProgressLog]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useLayoutEffect(() => {
    const ta = inputRef.current;
    if (!ta || sending) return;
    ta.style.height = '0px';
    const h = Math.max(CHAT_INPUT_MIN_PX, Math.min(ta.scrollHeight, CHAT_INPUT_MAX_PX));
    ta.style.height = `${h}px`;
  }, [input, sending, mentionOpen]);

  const loadMentionItems = useCallback(async () => {
    if (!api) return [];
    const now = Date.now();
    const ctx = editorContext || {};
    const ctxKey = `${ctx.videoDir || ''}|${ctx.outputDir || ''}|${(ctx.templates || []).length}`;
    const c = mentionCacheRef.current;
    if (c.items && now - c.at < MENTION_CACHE_MS && c.ctxKey === ctxKey) {
      return c.items;
    }

    const seen = new Set();
    const items = [];

    const push = (it) => {
      const key = `${it.category}:${it.id}`;
      if (seen.has(key)) return;
      seen.add(key);
      items.push({
        ...it,
        icon: it.icon || mentionIconForCategory(it.category),
      });
    };

    try {
      const skills = await api.listSkills();
      (skills || []).forEach((s) => {
        push({
          category: 'skill',
          id: s.id || s.name,
          label: s.name,
          desc: s.description?.slice(0, 56),
        });
      });
    } catch {}

    (ctx.templates || []).forEach((tpl) => {
      const isActive = tpl.id === ctx.selectedTemplate;
      push({
        category: 'template',
        id: `tpl:${tpl.id}`,
        label: tpl.name || tpl.id,
        desc: tpl.description?.slice(0, 56) || '剪辑提示模版',
        icon: isActive ? '✅' : '✂️',
      });
    });

    if (ctx.customRequirements?.trim()) {
      push({
        category: 'template',
        id: 'tpl:custom',
        label: '自定义要求',
        desc: ctx.customRequirements.slice(0, 56),
        icon: '📝',
      });
    }

    try {
      const assets = await api.listWorkspaceMentionAssets();
      (assets || []).forEach((a) => {
        push({
          category: a.category,
          id: a.id,
          label: a.label,
          desc: a.desc || a.id,
          absPath: a.absPath,
        });
      });
    } catch {}

    if (ctx.videoDir) {
      try {
        const files = await api.listVideoFiles(ctx.videoDir);
        (files || []).forEach((f) => {
          const abs = joinPath(ctx.videoDir, f);
          push({
            category: 'video',
            id: abs,
            label: f,
            desc: ctx.videoDir,
            absPath: abs,
          });
        });
      } catch {}
    }

    if (ctx.outputDir) {
      try {
        const result = await api.listOutputFiles(ctx.outputDir);
        (result?.highlights || []).forEach((f) => {
          const abs = joinPath(ctx.outputDir, f);
          push({
            category: 'storyboard',
            id: abs,
            label: f.replace('highlights_', '').replace('.json', ''),
            desc: '高光/分镜 JSON',
            absPath: abs,
          });
        });
        (result?.promos || []).forEach((f) => {
          const abs = joinPath(ctx.outputDir, f);
          push({
            category: 'video',
            id: abs,
            label: f,
            desc: '剪辑输出',
            absPath: abs,
          });
        });
      } catch {}
    }

    mentionCacheRef.current = { items, at: now, ctxKey };
    return items;
  }, [api, editorContext]);

  const filteredMentions = useMemo(() => {
    if (!mentionOpen) return [];
    const q = mentionQuery.toLowerCase().trim();
    let list = mentionItems.filter((item) => {
      if (!q) return true;
      return (
        item.label.toLowerCase().includes(q)
        || (item.desc && item.desc.toLowerCase().includes(q))
        || item.category.toLowerCase().includes(q)
        || item.id.toLowerCase().includes(q)
      );
    });
    if (mentionTab !== 'all') {
      list = list.filter((it) => it.category === mentionTab);
    }
    return list.slice(0, MENTION_LIST_LIMIT);
  }, [mentionOpen, mentionQuery, mentionItems, mentionTab]);

  useEffect(() => {
    if (mentionIdx >= filteredMentions.length) setMentionIdx(0);
  }, [filteredMentions, mentionIdx]);

  const closeMention = useCallback(() => {
    mentionOpenRef.current = false;
    setMentionOpen(false);
    setMentionQuery('');
    setMentionIdx(0);
    mentionAnchorRef.current = null;
  }, []);

  /** 根据光标同步 @ 面板：须立即打开 UI，避免 await 期间误关面板 */
  const syncMentionFromCursor = useCallback(
    (val, pos) => {
      const textBefore = val.slice(0, pos);
      const atIdx = textBefore.lastIndexOf('@');
      if (atIdx >= 0 && isMentionAt(textBefore, atIdx)) {
        const query = textBefore.slice(atIdx + 1);
        if (!query.includes(' ') && !query.includes('\n')) {
          mentionAnchorRef.current = atIdx;
          setMentionQuery(query);
          if (!mentionOpenRef.current) {
            mentionOpenRef.current = true;
            setMentionOpen(true);
            setMentionTab('all');
            setMentionIdx(0);
            loadMentionItems().then((items) => setMentionItems(items));
          }
          return;
        }
      }
      if (mentionOpenRef.current) closeMention();
    },
    [loadMentionItems, closeMention]
  );

  const insertMention = useCallback((item) => {
    const anchor = mentionAnchorRef.current;
    if (anchor == null) return;

    const before = input.slice(0, anchor);
    const afterAt = input.slice(anchor + 1);
    const queryLen = afterAt.match(/^[^\s\n]*/)?.[0]?.length ?? 0;
    const after = input.slice(anchor + 1 + queryLen);
    const tag = `@${item.label} `;
    setInput(before + tag + after);
    setMentions((prev) => [
      ...prev,
      {
        category: item.category,
        id: item.id,
        label: item.label,
        absPath: item.absPath,
      },
    ]);
    closeMention();

    setTimeout(() => {
      const el = inputRef.current;
      if (el) {
        const pos = before.length + tag.length;
        el.setSelectionRange(pos, pos);
        el.focus();
      }
    }, 0);
  }, [input, closeMention]);

  const handleInputChange = useCallback(
    (e) => {
      const val = e.target.value;
      const pos = e.target.selectionStart ?? val.length;
      setInput(val);
      syncMentionFromCursor(val, pos);
    },
    [syncMentionFromCursor]
  );

  const handleInputSelect = useCallback(
    (e) => {
      const val = e.target.value;
      const pos = e.target.selectionStart ?? val.length;
      syncMentionFromCursor(val, pos);
    },
    [syncMentionFromCursor]
  );

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending || !api) return;

    const mentionContext = mentions.length > 0
      ? '\n\n[引用上下文 — Agent 请结合以下路径/资源]\n'
        + mentions.map((m) => {
          const loc = m.absPath ? m.absPath : m.id;
          return `- [${m.category}] ${m.label} → ${loc}`;
        }).join('\n')
      : '';

    setInput('');
    setMentions([]);
    setSending(true);
    closeMention();
    streamBufferRef.current = '';
    thinkingBufferRef.current = '';
    lastStreamEventAtRef.current = Date.now();

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text, mentions: [...mentions] },
      {
        role: 'assistant',
        content: '',
        streaming: true,
        tools: [],
        thinking: '',
        progressFocus: buildInitialProgressFocus(mentions),
        progressLog: [
          '已发送至 OpenClaw Gateway。请查看上方「当前处理」中的技能与素材；视频分析等长任务常需数分钟才有下一条日志。',
        ],
      },
    ]);

    void api.chatSend({ message: text + mentionContext, sessionKey });
  }, [input, sending, sessionKey, api, mentions, closeMention]);

  const handleStop = useCallback(async () => {
    if (!api || !sending) return;
    try {
      await api.chatStop();
    } catch {
      /* 主进程仍会 abortLocal，忽略 */
    }
  }, [api, sending]);

  const handleInputKeyUp = useCallback(
    (e) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Backspace', 'Delete'].includes(e.key)) return;
      const el = inputRef.current;
      if (!el || !mentionOpenRef.current) return;
      requestAnimationFrame(() => {
        syncMentionFromCursor(el.value, el.selectionStart ?? 0);
      });
    },
    [syncMentionFromCursor]
  );

  const handleKeyDown = (e) => {
    if (mentionOpen) {
      if (e.key === 'ArrowDown' && filteredMentions.length > 0) {
        e.preventDefault();
        setMentionIdx((i) => (i + 1) % filteredMentions.length);
        return;
      }
      if (e.key === 'ArrowUp' && filteredMentions.length > 0) {
        e.preventDefault();
        setMentionIdx((i) => (i - 1 + filteredMentions.length) % filteredMentions.length);
        return;
      }
      if ((e.key === 'Enter' || e.key === 'Tab') && filteredMentions.length > 0) {
        e.preventDefault();
        insertMention(filteredMentions[mentionIdx]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        closeMention();
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (sending) return;
      handleSend();
    }
  };

  const loadSessions = async () => {
    if (!api) return;
    const list = await api.chatListSessions();
    setSessions(list || []);
    setShowSessions(true);
  };

  const handleNewSession = () => {
    const key = `studio:videocut:${Date.now()}`;
    setSessionKey(key);
    setMessages([]);
    setShowSessions(false);
  };

  const handleDeleteSession = async (key) => {
    if (!api) return;
    await api.chatDeleteSession(key);
    if (key === sessionKey) {
      setMessages([]);
    }
    loadSessions();
  };

  const tabCounts = useMemo(() => {
    const q = mentionQuery.toLowerCase().trim();
    const match = (item) => {
      if (!q) return true;
      return (
        item.label.toLowerCase().includes(q)
        || (item.desc && item.desc.toLowerCase().includes(q))
        || item.id.toLowerCase().includes(q)
      );
    };
    const base = mentionItems.filter(match);
    const counts = { all: base.length };
    MENTION_TABS.forEach((t) => {
      if (t.id === 'all') return;
      counts[t.id] = base.filter((it) => it.category === t.id).length;
    });
    return counts;
  }, [mentionItems, mentionQuery]);

  if (collapsed) {
    return (
      <div className="chat-collapsed" onClick={onToggle}>
        <span className="chat-collapsed-icon">💬</span>
        <span className="chat-collapsed-label">Agent</span>
      </div>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-header-left">
          <span className="chat-title">Agent</span>
          <span className={`gw-dot ${gatewayConnected ? 'connected' : 'disconnected'}`} />
        </div>
        <div className="chat-header-actions">
          <button className="btn-icon" onClick={handleNewSession} title="新会话">+</button>
          <button className="btn-icon" onClick={loadSessions} title="会话列表">☰</button>
          <button className="btn-icon" onClick={onToggle} title="收起">✕</button>
        </div>
      </div>

      {showSessions && (
        <div className="sessions-dropdown">
          <div className="sessions-header">
            <span>会话列表</span>
            <button className="btn-icon" onClick={() => setShowSessions(false)}>✕</button>
          </div>
          {sessions.length === 0 && (
            <div className="sessions-empty">暂无会话</div>
          )}
          {sessions.map((s) => (
            <div
              key={s.sessionKey}
              className={`session-item ${s.sessionKey === sessionKey ? 'active' : ''}`}
              onClick={() => { setSessionKey(s.sessionKey); setShowSessions(false); setMessages([]); }}
            >
              <span className="session-title">{s.title || s.sessionKey.split(':').pop()}</span>
              <button
                className="btn-icon-sm"
                onClick={(e) => { e.stopPropagation(); handleDeleteSession(s.sessionKey); }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon">💬</div>
            <p>与 Agent 对话</p>
            <p className="chat-empty-hint">输入 @ 引用技能、模版、素材路径</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        {!gatewayConnected && (
          <div className="chat-warning">
            Gateway 未连接 — 请确认 OpenClaw 正在运行
          </div>
        )}

        {mentions.length > 0 && (
          <div className="mention-tags">
            {mentions.map((m, i) => (
              <span key={i} className={`mention-tag mention-tag-${m.category}`}>
                <span className="mention-tag-icon">{mentionIconForCategory(m.category)}</span>
                <span className="mention-tag-text">{m.label}</span>
                <button type="button" className="mention-tag-remove" onClick={() => setMentions((prev) => prev.filter((_, j) => j !== i))}>×</button>
              </span>
            ))}
          </div>
        )}

        <div className="chat-input-wrapper">
          {mentionOpen && (
            <div className="mention-dropdown mention-dropdown-with-tabs">
              <div className="mention-tab-bar">
                {MENTION_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`mention-tab ${mentionTab === tab.id ? 'active' : ''}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      setMentionTab(tab.id);
                      setMentionIdx(0);
                    }}
                  >
                    <span className="mention-tab-icon">{tab.icon}</span>
                    <span className="mention-tab-label">{tab.label}</span>
                    {tab.id !== 'all' && tabCounts[tab.id] > 0 && (
                      <span className="mention-tab-badge">{tabCounts[tab.id] > 99 ? '99+' : tabCounts[tab.id]}</span>
                    )}
                  </button>
                ))}
              </div>
              <div className="mention-list-wrap">
                {filteredMentions.length === 0 ? (
                  <div className="mention-empty">
                    {mentionItems.length === 0
                      ? '正在加载或暂无可用资源…'
                      : '当前分类下无匹配项，试试其它分栏或修改筛选'}
                  </div>
                ) : (
                  filteredMentions.map((item, idx) => (
                    <div
                      key={`${item.category}:${item.id}`}
                      className={`mention-item ${idx === mentionIdx ? 'active' : ''}`}
                      onMouseEnter={() => setMentionIdx(idx)}
                      onMouseDown={(e) => { e.preventDefault(); insertMention(item); }}
                    >
                      <span className="mention-item-type">{MENTION_TABS.find((t) => t.id === item.category)?.label || item.category}</span>
                      <span className="mention-item-icon">{item.icon}</span>
                      <div className="mention-item-text">
                        <span className="mention-item-label">{item.label}</span>
                        {item.desc && <span className="mention-item-desc">{item.desc}</span>}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          <div className="chat-input-row">
            <textarea
              ref={inputRef}
              className="chat-input"
              value={input}
              onChange={handleInputChange}
              onSelect={handleInputSelect}
              onClick={handleInputSelect}
              onKeyDown={handleKeyDown}
              onKeyUp={handleInputKeyUp}
              placeholder={
                sending
                  ? '生成中… 可在此起草下一条（Enter 不会发送）；点右侧「停止」可中断并修改提示词后重发'
                  : '输入指令。@ 可选技能、模版、音视频与工程文件（任意位置）'
              }
              rows={4}
            />
            <div className="chat-input-actions">
              {sending ? (
                <button
                  type="button"
                  className="chat-stop-btn"
                  onClick={handleStop}
                  title="停止当前生成（类似 Cursor Stop）"
                >
                  停止
                </button>
              ) : (
                <button
                  type="button"
                  className="chat-send-btn"
                  onClick={handleSend}
                  disabled={!input.trim() || !gatewayConnected}
                  title="发送"
                >
                  ➤
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** 用户气泡内 @技能名 / @文件名 等高亮（与上方 chips 同类配色） */
function renderTextWithAtHighlights(text, mentions) {
  if (text == null || text === '') return null;
  const list = mentions || [];
  const nodes = [];
  let lastIdx = 0;
  let key = 0;
  const re = /@([^\s@]+)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIdx) {
      nodes.push(<span key={`txt-${key++}`}>{text.slice(lastIdx, m.index)}</span>);
    }
    const full = m[0];
    const label = m[1];
    const hit = list.find((x) => x.label === label);
    const cat = hit?.category && typeof hit.category === 'string' ? hit.category : 'unknown';
    nodes.push(
      <span
        key={`at-${key++}`}
        className={`chat-at-ref chat-at-${cat}`}
        title={hit?.absPath ? String(hit.absPath) : undefined}
      >
        {full}
      </span>
    );
    lastIdx = m.index + full.length;
  }
  if (lastIdx < text.length) {
    nodes.push(<span key={`txt-${key++}`}>{text.slice(lastIdx)}</span>);
  }
  if (nodes.length === 0) return text;
  return <>{nodes}</>;
}

function ChatMessage({ message }) {
  const { role, content, streaming, tools, thinking, error, progressLog, progressFocus, stopped } = message;
  const runningTools = (tools || []).filter((t) => t.status === 'running');
  const runningToolTitle = runningTools.length ? runningTools.map((t) => t.title).join('、') : '';
  const [showThinking, setShowThinking] = useState(false);
  const [expandedTools, setExpandedTools] = useState(new Set());

  const toggleTool = (id) => {
    setExpandedTools((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (role === 'system') {
    return (
      <div className="chat-msg system">
        <div className="chat-msg-content system-msg">{content}</div>
      </div>
    );
  }

  if (role === 'user') {
    return (
      <div className="chat-msg user">
        {message.mentions?.length > 0 && (
          <div className="msg-mentions">
            {message.mentions.map((m, i) => (
              <span key={i} className={`mention-inline mention-inline-${m.category}`}>
                {mentionIconForCategory(m.category)} {m.label}
              </span>
            ))}
          </div>
        )}
        <div className="chat-msg-content user-bubble">
          {renderTextWithAtHighlights(content, message.mentions)}
        </div>
      </div>
    );
  }

  const focus = progressFocus && typeof progressFocus === 'object' ? progressFocus : {};
  const hasFocus =
    !!(focus.skill || focus.video || focus.phase || focus.note || runningToolTitle);

  return (
    <div className="chat-msg assistant">
      {hasFocus && (
        <div className="chat-progress-focus" aria-live="polite">
          <div className="chat-progress-focus-title">当前处理</div>
          {focus.skill && (
            <div className="chat-progress-focus-row">
              <span className="chat-progress-focus-k">技能 / 流程</span>
              <span className="chat-progress-focus-v">{focus.skill}</span>
            </div>
          )}
          {focus.video && (
            <div className="chat-progress-focus-row">
              <span className="chat-progress-focus-k">视频 / 文件</span>
              <span className="chat-progress-focus-v">{focus.video}</span>
            </div>
          )}
          {focus.phase && (
            <div className="chat-progress-focus-row">
              <span className="chat-progress-focus-k">当前步骤</span>
              <span className="chat-progress-focus-v">{focus.phase}</span>
            </div>
          )}
          {runningToolTitle && (
            <div className="chat-progress-focus-row">
              <span className="chat-progress-focus-k">运行中工具</span>
              <span className="chat-progress-focus-v">{runningToolTitle}</span>
            </div>
          )}
          {focus.note && (
            <div className="chat-progress-focus-row chat-progress-focus-note">
              <span className="chat-progress-focus-k">备注</span>
              <span className="chat-progress-focus-v">{focus.note}</span>
            </div>
          )}
        </div>
      )}

      {progressLog?.length > 0 && (
        <div className="chat-progress-log" aria-live="polite">
          <div className="chat-progress-log-title">详细日志</div>
          {progressLog.map((line, i) => (
            <div key={i} className="chat-progress-line">{line}</div>
          ))}
        </div>
      )}

      {thinking && (
        <div className="thinking-block">
          <button type="button" className="thinking-toggle" onClick={() => setShowThinking(!showThinking)}>
            {showThinking ? '▾ ' : '▸ '}思考中...
          </button>
          {showThinking && <div className="thinking-content">{thinking}</div>}
        </div>
      )}

      {tools?.map((tool) => (
        <div key={tool.id} className={`tool-block ${tool.status}`}>
          <div className="tool-header" onClick={() => toggleTool(tool.id)}>
            <span className="tool-status-icon">
              {tool.status === 'running' ? '⟳' : tool.status === 'completed' ? '✓' : '✗'}
            </span>
            <span className="tool-name">{tool.title}</span>
            <span className="tool-expand">{expandedTools.has(tool.id) ? '▾' : '▸'}</span>
          </div>
          {expandedTools.has(tool.id) && (
            <div className="tool-detail">
              {tool.input && <pre className="tool-io">{tool.input}</pre>}
              {tool.output && <pre className="tool-io">{tool.output}</pre>}
            </div>
          )}
        </div>
      ))}

      {content && (
        <div className="chat-msg-content assistant-bubble">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}

      {streaming && !content && !thinking && !tools?.length && !(progressLog?.length) && (
        <div className="chat-msg-content assistant-bubble">
          <span className="typing-indicator">
            <span /><span /><span />
          </span>
        </div>
      )}

      {streaming && !content && progressLog?.length > 0 && (
        <div className="chat-msg-content assistant-bubble chat-inline-wait">
          <span className="typing-indicator typing-indicator-inline">
            <span /><span /><span />
          </span>
          <span className="chat-inline-wait-text">执行中</span>
        </div>
      )}

      {stopped && !error && (
        <div className="chat-stopped-hint">已停止</div>
      )}

      {error && (
        <div className="chat-error">{error}</div>
      )}
    </div>
  );
}

export default ChatPanel;

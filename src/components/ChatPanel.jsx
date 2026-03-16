import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MENTION_CATEGORIES = [
  { id: 'skill', label: '技能', icon: '🧩' },
  { id: 'template', label: '剪辑模板', icon: '✂️' },
  { id: 'input', label: '输入素材', icon: '📁' },
  { id: 'output', label: '剪辑素材', icon: '🎬' },
];

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

  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionIdx, setMentionIdx] = useState(0);
  const [mentionItems, setMentionItems] = useState([]);
  const [mentions, setMentions] = useState([]);
  const mentionAnchorRef = useRef(null);
  const inputRef = useRef(null);

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
      switch (evt.type) {
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
        case 'tool_output':
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
  }, [api]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load mention data sources
  const loadMentionItems = useCallback(async () => {
    if (!api) return [];
    const items = [];

    try {
      const skills = await api.listSkills();
      (skills || []).forEach((s) => {
        items.push({ category: 'skill', id: s.id || s.name, label: s.name, desc: s.description?.slice(0, 50), icon: '🧩' });
      });
    } catch {}

    const ctx = editorContext || {};

    (ctx.templates || []).forEach((tpl) => {
      const isActive = tpl.id === ctx.selectedTemplate;
      items.push({
        category: 'template',
        id: `tpl:${tpl.id}`,
        label: tpl.name,
        desc: tpl.description?.slice(0, 60),
        icon: isActive ? '✅' : '✂️',
      });
    });

    if (ctx.customRequirements?.trim()) {
      items.push({
        category: 'template',
        id: 'tpl:custom',
        label: '自定义要求',
        desc: ctx.customRequirements.slice(0, 60),
        icon: '📝',
      });
    }

    if (ctx.videoDir) {
      try {
        const files = await api.listVideoFiles(ctx.videoDir);
        (files || []).forEach((f) => {
          items.push({ category: 'input', id: f, label: f, desc: ctx.videoDir, icon: '📁' });
        });
      } catch {}
    }

    if (ctx.outputDir) {
      try {
        const result = await api.listOutputFiles(ctx.outputDir);
        (result?.highlights || []).forEach((f) => {
          items.push({ category: 'output', id: f, label: f.replace('highlights_', '').replace('.json', ''), desc: '分析结果', icon: '📊' });
        });
        (result?.promos || []).forEach((f) => {
          items.push({ category: 'output', id: f, label: f, desc: '剪辑输出', icon: '🎬' });
        });
      } catch {}
    }

    return items;
  }, [api, editorContext]);

  const filteredMentions = useMemo(() => {
    if (!mentionOpen) return [];
    const q = mentionQuery.toLowerCase();
    return mentionItems.filter((item) =>
      item.label.toLowerCase().includes(q) || item.category.includes(q)
    ).slice(0, 12);
  }, [mentionOpen, mentionQuery, mentionItems]);

  useEffect(() => {
    if (mentionIdx >= filteredMentions.length) setMentionIdx(0);
  }, [filteredMentions, mentionIdx]);

  const openMention = useCallback(async (cursorPos) => {
    mentionAnchorRef.current = cursorPos;
    const items = await loadMentionItems();
    setMentionItems(items);
    setMentionOpen(true);
    setMentionQuery('');
    setMentionIdx(0);
  }, [loadMentionItems]);

  const closeMention = useCallback(() => {
    setMentionOpen(false);
    setMentionQuery('');
    setMentionIdx(0);
    mentionAnchorRef.current = null;
  }, []);

  const insertMention = useCallback((item) => {
    const anchor = mentionAnchorRef.current;
    if (anchor == null) return;

    const before = input.slice(0, anchor);
    const after = input.slice(anchor + mentionQuery.length + 1);
    const tag = `@${item.label} `;
    setInput(before + tag + after);
    setMentions((prev) => [...prev, { category: item.category, id: item.id, label: item.label }]);
    closeMention();

    setTimeout(() => {
      const el = inputRef.current;
      if (el) {
        const pos = before.length + tag.length;
        el.setSelectionRange(pos, pos);
        el.focus();
      }
    }, 0);
  }, [input, mentionQuery, closeMention]);

  const handleInputChange = useCallback((e) => {
    const val = e.target.value;
    const pos = e.target.selectionStart;
    setInput(val);

    const textBeforeCursor = val.slice(0, pos);
    const atIdx = textBeforeCursor.lastIndexOf('@');

    if (atIdx >= 0) {
      const charBefore = atIdx > 0 ? textBeforeCursor[atIdx - 1] : ' ';
      if (charBefore === ' ' || charBefore === '\n' || atIdx === 0) {
        const query = textBeforeCursor.slice(atIdx + 1);
        if (!query.includes(' ') && !query.includes('\n')) {
          if (!mentionOpen) {
            openMention(atIdx);
          }
          setMentionQuery(query);
          return;
        }
      }
    }

    if (mentionOpen) closeMention();
  }, [mentionOpen, openMention, closeMention]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending || !api) return;

    const mentionContext = mentions.length > 0
      ? '\n\n[引用上下文] ' + mentions.map((m) => `@${m.category}:${m.id}`).join(', ')
      : '';

    setInput('');
    setMentions([]);
    setSending(true);
    closeMention();
    streamBufferRef.current = '';
    thinkingBufferRef.current = '';

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text, mentions: [...mentions] },
      { role: 'assistant', content: '', streaming: true, tools: [], thinking: '' },
    ]);

    await api.chatSend({ message: text + mentionContext, sessionKey });
  }, [input, sending, sessionKey, api, mentions, closeMention]);

  const handleKeyDown = (e) => {
    if (mentionOpen && filteredMentions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIdx((i) => (i + 1) % filteredMentions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIdx((i) => (i - 1 + filteredMentions.length) % filteredMentions.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
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
            <p className="chat-empty-hint">输入问题或指令开始</p>
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
                <span className="mention-tag-icon">
                  {m.category === 'skill' ? '🧩' : m.category === 'template' ? '✂️' : m.category === 'input' ? '📁' : '🎬'}
                </span>
                {m.label}
                <button className="mention-tag-remove" onClick={() => setMentions((prev) => prev.filter((_, j) => j !== i))}>×</button>
              </span>
            ))}
          </div>
        )}

        <div className="chat-input-wrapper">
          {mentionOpen && filteredMentions.length > 0 && (
            <div className="mention-dropdown">
              {MENTION_CATEGORIES.map((cat) => {
                const catItems = filteredMentions.filter((it) => it.category === cat.id);
                if (!catItems.length) return null;
                return (
                  <div key={cat.id} className="mention-group">
                    <div className="mention-group-label">{cat.icon} {cat.label}</div>
                    {catItems.map((item) => {
                      const globalIdx = filteredMentions.indexOf(item);
                      return (
                        <div
                          key={item.id}
                          className={`mention-item ${globalIdx === mentionIdx ? 'active' : ''}`}
                          onMouseEnter={() => setMentionIdx(globalIdx)}
                          onMouseDown={(e) => { e.preventDefault(); insertMention(item); }}
                        >
                          <span className="mention-item-icon">{item.icon}</span>
                          <div className="mention-item-text">
                            <span className="mention-item-label">{item.label}</span>
                            {item.desc && <span className="mention-item-desc">{item.desc}</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          )}

          <div className="chat-input-row">
            <textarea
              ref={inputRef}
              className="chat-input"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="输入指令... 使用 @ 引用技能或素材"
              rows={1}
              disabled={sending}
            />
            <button
              className="chat-send-btn"
              onClick={handleSend}
              disabled={sending || !input.trim() || !gatewayConnected}
            >
              {sending ? <span className="spinner" /> : '➤'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatMessage({ message }) {
  const { role, content, streaming, tools, thinking, error } = message;
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
                {m.category === 'skill' ? '🧩' : m.category === 'template' ? '✂️' : m.category === 'input' ? '📁' : '🎬'} {m.label}
              </span>
            ))}
          </div>
        )}
        <div className="chat-msg-content user-bubble">{content}</div>
      </div>
    );
  }

  return (
    <div className="chat-msg assistant">
      {thinking && (
        <div className="thinking-block">
          <button className="thinking-toggle" onClick={() => setShowThinking(!showThinking)}>
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

      {streaming && !content && !thinking && !tools?.length && (
        <div className="chat-msg-content assistant-bubble">
          <span className="typing-indicator">
            <span /><span /><span />
          </span>
        </div>
      )}

      {error && (
        <div className="chat-error">{error}</div>
      )}
    </div>
  );
}

export default ChatPanel;

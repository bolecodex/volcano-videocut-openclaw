import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Square, Trash2, X, ImageIcon, AtSign, Plus, List } from "lucide-react";
import { useSWRConfig } from "swr";
import { useChat } from "../../hooks/use-chat";
import { useProjectStore } from "../../stores/project-store";
import { useChatStore, type ChatSession } from "../../stores/chat-store";
import { useProjects } from "../../hooks/use-api";
import { useAgentContext } from "../../hooks/use-agent-context";
import { useMentions } from "../../hooks/use-mentions";
import { ChatMessage } from "./ChatMessage";
import { MentionDropdown } from "./MentionDropdown";
import { SessionList } from "./SessionList";
import { TokenBadge } from "./TokenBadge";
import {
  validateImage,
  fileToAttachment,
} from "../../lib/image-utils";
import { getQueryAfterAt, insertMention, parseMentions, stripMentionTokens } from "../../lib/mention-utils";
import type { ImageAttachment, MentionRef, MentionItem } from "../../lib/types";
import { TAB_LABELS } from "../../lib/ui-registry";

export function ChatPanel() {
  const [input, setInput] = useState("");
  const [images, setImages] = useState<ImageAttachment[]>([]);
  const [mentionRefs, setMentionRefs] = useState<MentionRef[]>([]);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [imageError, setImageError] = useState<string | null>(null);
  const [showSessions, setShowSessions] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const currentProject = useProjectStore((s) => s.currentProject);
  const { data: projects } = useProjects();
  const { mutate } = useSWRConfig();

  const agentContext = useAgentContext();
  const { search: searchMentions } = useMentions(currentProject);

  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const addSession = useChatStore((s) => s.addSession);
  const setSessions = useChatStore((s) => s.setSessions);
  const getActiveSession = useChatStore((s) => s.getActiveSession);
  const getProjectSessions = useChatStore((s) => s.getProjectSessions);

  const projectDir = projects?.find((p) => p.name === currentProject)?.path;
  const projectPath = projectDir ?? "";
  const sessions = getProjectSessions(projectPath);
  const activeSession = getActiveSession();

  const refreshAll = useCallback(() => {
    if (!currentProject) return;
    mutate(
      (key: string) =>
        typeof key === "string" && key.includes(currentProject),
      undefined,
      { revalidate: true },
    );
    mutate(`tree-${currentProject}`);
  }, [currentProject, mutate]);

  const { messages, isStreaming, sendMessage, stopStreaming, clearMessages } =
    useChat(refreshAll);

  useEffect(() => {
    if (!projectPath) return;
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(`/api/sessions?project=${encodeURIComponent(projectPath)}`);
        if (!res.ok || cancelled) return;
        const data = await res.json();
        if (cancelled) return;

        const loaded: ChatSession[] = (data.sessions ?? []).map((s: Record<string, unknown>) => ({
          id: (s.id as string) ?? "default",
          sessionKey: (s.sessionKey as string) ?? "",
          projectPath: (s.projectPath as string) ?? projectPath,
          title: (s.title as string) ?? null,
          createdAt: (s.createdAt as number) ?? Date.now(),
          updatedAt: (s.updatedAt as number) ?? Date.now(),
          messageCount: (s.messageCount as number) ?? 0,
          tokenUsage: (s.tokenUsage as ChatSession["tokenUsage"]) ?? { input: 0, output: 0, total: 0, context: 0 },
        }));

        setSessions(projectPath, loaded);

        if (loaded.length > 0) {
          const current = useChatStore.getState().activeSessionId;
          const hasActive = loaded.some((s) => s.id === current);
          if (!hasActive) {
            setActiveSession(loaded[0].id);
          }
        }
      } catch { /* ignore */ }
    })();

    return () => { cancelled = true; };
  }, [projectPath, setSessions, setActiveSession]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (imageError) {
      const t = setTimeout(() => setImageError(null), 3000);
      return () => clearTimeout(t);
    }
  }, [imageError]);

  const handleImageFiles = useCallback(async (files: File[]) => {
    for (const file of files) {
      const v = validateImage(file);
      if (!v.ok) {
        setImageError(v.error!);
        continue;
      }
      const att = await fileToAttachment(file);
      setImages((prev) => [...prev, att]);
    }
  }, []);

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      const items = e.clipboardData.items;
      const imgFiles: File[] = [];
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith("image/")) {
          const file = items[i].getAsFile();
          if (file) imgFiles.push(file);
        }
      }
      if (imgFiles.length > 0) {
        e.preventDefault();
        handleImageFiles(imgFiles);
      }
    },
    [handleImageFiles],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const imgFiles: File[] = [];
      const dt = e.dataTransfer;
      for (let i = 0; i < dt.files.length; i++) {
        if (dt.files[i].type.startsWith("image/")) {
          imgFiles.push(dt.files[i]);
        }
      }
      if (imgFiles.length > 0) {
        handleImageFiles(imgFiles);
      }
    },
    [handleImageFiles],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const val = e.target.value;
      setInput(val);

      const cursorPos = e.target.selectionStart ?? val.length;
      const { active, query } = getQueryAfterAt(val, cursorPos);
      setShowMentions(active);
      setMentionQuery(active ? query : "");
    },
    [],
  );

  const handleMentionSelect = useCallback(
    (item: MentionItem) => {
      const textarea = textareaRef.current;
      const cursorPos = textarea?.selectionStart ?? input.length;
      const ref: MentionRef = {
        type: item.type,
        id: item.id,
        label: item.label,
      };
      const result = insertMention(input, cursorPos, ref);
      setInput(result.text);
      setMentionRefs((prev) => [...prev, ref]);
      setShowMentions(false);
      setMentionQuery("");

      requestAnimationFrame(() => {
        if (textarea) {
          textarea.focus();
          textarea.setSelectionRange(result.cursorPos, result.cursorPos);
        }
      });
    },
    [input],
  );

  const handleCreateSession = useCallback(async () => {
    if (!projectPath) return;
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectPath }),
      });
      if (!res.ok) return;
      const data = await res.json();
      const session: ChatSession = {
        id: data.id,
        sessionKey: data.sessionKey,
        projectPath,
        title: null,
        createdAt: data.createdAt ?? Date.now(),
        updatedAt: data.updatedAt ?? Date.now(),
        messageCount: 0,
        tokenUsage: { input: 0, output: 0, total: 0, context: 0 },
      };
      addSession(session);
      setShowSessions(false);
    } catch { /* ignore */ }
  }, [projectPath, addSession]);

  const handleSessionSelect = useCallback((id: string) => {
    setActiveSession(id);
    setShowSessions(false);
  }, [setActiveSession]);

  function handleSend() {
    const text = input.trim();
    if (!text || isStreaming) return;

    const inlineMentions = parseMentions(text);
    const allMentions = [
      ...mentionRefs,
      ...inlineMentions.filter(
        (m) => !mentionRefs.some((r) => r.type === m.type && r.id === m.id),
      ),
    ];

    const displayText = stripMentionTokens(text);

    setInput("");
    setImages([]);
    setMentionRefs([]);

    if (!activeSessionId && projectPath) {
      fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectPath }),
      })
        .then((r) => r.json())
        .then((data) => {
          const session: ChatSession = {
            id: data.id,
            sessionKey: data.sessionKey,
            projectPath,
            title: null,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            messageCount: 0,
            tokenUsage: { input: 0, output: 0, total: 0, context: 0 },
          };
          addSession(session);
          sendMessage({
            text: displayText,
            projectDir,
            context: agentContext,
            attachments: images.length ? images : undefined,
            mentions: allMentions.length ? allMentions : undefined,
            sessionId: data.id,
          });
        })
        .catch(() => {
          sendMessage({
            text: displayText,
            projectDir,
            context: agentContext,
            attachments: images.length ? images : undefined,
            mentions: allMentions.length ? allMentions : undefined,
          });
        });
      return;
    }

    sendMessage({
      text: displayText,
      projectDir,
      context: agentContext,
      attachments: images.length ? images : undefined,
      mentions: allMentions.length ? allMentions : undefined,
      sessionId: activeSessionId,
    });
  }

  const removeImage = (id: string) => {
    setImages((prev) => prev.filter((img) => img.id !== id));
  };

  const contextBreadcrumb = agentContext
    ? [
        agentContext.project?.name,
        TAB_LABELS[agentContext.view.currentTab],
        agentContext.focus.characterName ||
          agentContext.focus.sceneName ||
          agentContext.focus.shotId,
      ]
        .filter(Boolean)
        .join(" > ")
    : null;

  const mentionResults = showMentions ? searchMentions(mentionQuery) : [];

  return (
    <div className="flex w-96 flex-col border-l border-white/[0.06] bg-surface-1">
      {/* Header */}
      <div className="relative flex items-center justify-between border-b border-white/[0.06] px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <button
            onClick={() => setShowSessions(!showSessions)}
            className={`rounded-md p-1 transition-colors ${
              showSessions
                ? "bg-white/10 text-white"
                : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
            }`}
            title="会话列表"
          >
            <List size={13} />
          </button>
          <span className="truncate text-xs font-medium text-gray-300">
            {activeSession?.title ||
              (currentProject ? currentProject : "Agent")}
          </span>
          <TokenBadge usage={activeSession?.tokenUsage ?? null} />
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={handleCreateSession}
            className="rounded-md p-1 text-gray-600 transition-colors hover:bg-white/5 hover:text-gray-300"
            title="新建对话"
          >
            <Plus size={13} />
          </button>
          <button
            onClick={clearMessages}
            className="rounded-md p-1 text-gray-600 transition-colors hover:bg-white/5 hover:text-gray-300"
            title="清空消息"
          >
            <Trash2 size={13} />
          </button>
        </div>

        {showSessions && (
          <SessionList
            sessions={sessions}
            activeId={activeSessionId}
            projectPath={projectPath}
            onSelect={handleSessionSelect}
            onCreate={handleCreateSession}
            onClose={() => setShowSessions(false)}
          />
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-3 overflow-auto px-3 py-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-2 pt-12 text-center">
            <div className="rounded-2xl bg-surface-2 p-3">
              <AtSign size={20} strokeWidth={1.5} className="text-gray-600" />
            </div>
            <p className="text-xs text-gray-500">
              {currentProject
                ? `当前项目: ${currentProject}`
                : "选择一个项目后开始对话"}
            </p>
            <p className="text-[11px] text-gray-600">
              发送消息开始对话...
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-white/[0.06] p-2.5">
        {contextBreadcrumb && (
          <div className="mb-2 flex items-center gap-1.5 px-1">
            <AtSign size={10} className="shrink-0 text-accent/60" />
            <span className="truncate text-[10px] text-gray-500">
              上下文: {contextBreadcrumb}
            </span>
          </div>
        )}

        {imageError && (
          <div className="mb-2 rounded-lg bg-red-500/10 px-2.5 py-1.5 text-[11px] text-red-400">
            {imageError}
          </div>
        )}

        {images.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5 px-1">
            {images.map((img) => (
              <div key={img.id} className="group relative">
                <img
                  src={img.dataUrl}
                  alt={img.name ?? "attachment"}
                  className="h-14 w-14 rounded-lg border border-white/10 object-cover"
                />
                <button
                  onClick={() => removeImage(img.id)}
                  className="absolute -right-1 -top-1 rounded-full bg-surface-1 p-0.5 text-gray-400 opacity-0 shadow-sm transition-opacity hover:text-white group-hover:opacity-100"
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div
          className="relative flex items-end gap-1.5 rounded-xl bg-surface-2 px-3 py-2.5 ring-1 ring-white/[0.06] transition-all focus-within:ring-accent/30"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          <MentionDropdown
            items={mentionResults}
            onSelect={handleMentionSelect}
            onClose={() => setShowMentions(false)}
            query={mentionQuery}
            visible={showMentions}
          />

          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onPaste={handlePaste}
            onKeyDown={(e) => {
              if (showMentions) return;
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={
              currentProject
                ? "输入指令... 输入 @ 引用数据"
                : "输入指令..."
            }
            rows={6}
            className="flex-1 resize-none bg-transparent text-sm leading-relaxed outline-none placeholder:text-gray-600"
          />

          <div className="flex shrink-0 items-center gap-0.5">
            <label className="cursor-pointer rounded-md p-1.5 text-gray-600 transition-colors hover:bg-white/5 hover:text-gray-400">
              <ImageIcon size={14} />
              <input
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []);
                  handleImageFiles(files);
                  e.target.value = "";
                }}
              />
            </label>

            {isStreaming ? (
              <button
                onClick={stopStreaming}
                className="rounded-md p-1.5 text-red-400 transition-colors hover:bg-white/5"
              >
                <Square size={16} />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="rounded-md p-1.5 text-accent transition-colors hover:bg-white/5 disabled:text-gray-700"
              >
                <Send size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

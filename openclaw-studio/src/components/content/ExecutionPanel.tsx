import { useRef, useEffect, useState } from "react";
import {
  Loader2,
  X,
  Minimize2,
  Maximize2,
  Square,
  Wrench,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  MessageSquare,
  Brain,
} from "lucide-react";
import { usePipelineStore, type ExecutionLog } from "../../stores/pipeline-store";

function formatTime(date: Date) {
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function ToolOutput({ output }: { output: string }) {
  const [expanded, setExpanded] = useState(false);
  const lines = output.split("\n");
  const isLong = lines.length > 4 || output.length > 300;

  if (!isLong) {
    return (
      <pre className="mt-1 whitespace-pre-wrap break-all rounded bg-surface-3/40 px-2 py-1 text-[11px] leading-relaxed text-gray-500">
        {output}
      </pre>
    );
  }

  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="mb-0.5 flex items-center gap-1 text-[10px] text-gray-600 hover:text-gray-400"
      >
        {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        {expanded ? "收起输出" : `展开输出 (${lines.length} 行)`}
      </button>
      {expanded && (
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-surface-3/40 px-2 py-1.5 text-[11px] leading-relaxed text-gray-500">
          {output}
        </pre>
      )}
    </div>
  );
}

function LogEntry({ log, index }: { log: ExecutionLog; index: number }) {
  const now = formatTime(new Date());

  if (log.type === "text" && log.content) {
    return (
      <div className="flex gap-2 py-0.5">
        <MessageSquare size={12} className="mt-0.5 shrink-0 text-gray-600" />
        <div className="min-w-0 flex-1">
          <span className="whitespace-pre-wrap break-words text-[12px] leading-relaxed text-gray-300">
            {log.content}
          </span>
        </div>
      </div>
    );
  }

  if (log.type === "thinking" && log.content) {
    return (
      <div className="flex gap-2 py-0.5">
        <Brain size={12} className="mt-0.5 shrink-0 text-violet-500/60" />
        <span className="text-[11px] italic leading-relaxed text-gray-500/80">
          {log.content}
        </span>
      </div>
    );
  }

  if (log.type === "tool_start" && log.toolCall) {
    return (
      <div className="flex gap-2 rounded-md bg-blue-500/5 px-2 py-1.5">
        <Loader2 size={12} className="mt-0.5 shrink-0 animate-spin text-blue-400" />
        <div className="min-w-0 flex-1">
          <span className="text-[12px] font-medium text-blue-400">
            {log.toolCall.title}
          </span>
          <span className="ml-2 text-[10px] text-blue-400/50">执行中...</span>
        </div>
      </div>
    );
  }

  if (log.type === "tool_update" && log.toolCall) {
    const isOk = log.toolCall.status === "completed";
    return (
      <div
        className={`flex gap-2 rounded-md px-2 py-1.5 ${
          isOk ? "bg-emerald-500/5" : "bg-red-500/5"
        }`}
      >
        {isOk ? (
          <CheckCircle2 size={12} className="mt-0.5 shrink-0 text-emerald-400" />
        ) : (
          <AlertTriangle size={12} className="mt-0.5 shrink-0 text-red-400" />
        )}
        <div className="min-w-0 flex-1">
          <span
            className={`text-[12px] font-medium ${
              isOk ? "text-emerald-400" : "text-red-400"
            }`}
          >
            {log.toolCall.title}
          </span>
          <span
            className={`ml-2 text-[10px] ${
              isOk ? "text-emerald-400/60" : "text-red-400/60"
            }`}
          >
            {isOk ? "完成" : "失败"}
          </span>
          {log.toolCall.output && <ToolOutput output={log.toolCall.output} />}
        </div>
      </div>
    );
  }

  if (log.type === "error") {
    return (
      <div className="flex gap-2 rounded-md bg-red-500/8 px-2 py-1.5">
        <AlertTriangle size={12} className="mt-0.5 shrink-0 text-red-400" />
        <span className="whitespace-pre-wrap break-words text-[12px] leading-relaxed text-red-400">
          {log.content}
        </span>
      </div>
    );
  }

  return null;
}

export function ExecutionPanel() {
  const {
    runningStep,
    executionLogs,
    executionMinimized,
    setExecutionMinimized,
    stopExecution,
    steps,
  } = usePipelineStore();

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [executionLogs.length]);

  if (!runningStep && executionLogs.length === 0) return null;

  const step = steps.find((s) => s.id === runningStep);
  const stepName = step?.name ?? runningStep ?? "任务";
  const isRunning = !!runningStep;
  const logCount = executionLogs.length;
  const toolCount = executionLogs.filter(
    (l) => l.type === "tool_start" || l.type === "tool_update",
  ).length;

  if (executionMinimized) {
    return (
      <div className="flex items-center gap-2.5 border-t border-white/5 bg-surface-2/80 px-4 py-2">
        {isRunning && (
          <Loader2 size={13} className="animate-spin text-accent" />
        )}
        <span
          className={`flex-1 text-xs ${isRunning ? "text-gray-300" : "text-gray-500"}`}
        >
          {isRunning ? `执行中: ${stepName}` : `已完成: ${stepName}`}
        </span>
        {logCount > 0 && (
          <span className="text-[10px] text-gray-600">
            {logCount} 条日志
          </span>
        )}
        <button
          onClick={() => setExecutionMinimized(false)}
          className="rounded p-1 text-gray-500 transition-colors hover:bg-white/5 hover:text-gray-300"
        >
          <Maximize2 size={13} />
        </button>
        {!isRunning && (
          <button
            onClick={() =>
              usePipelineStore.setState({ executionLogs: [] })
            }
            className="rounded p-1 text-gray-500 transition-colors hover:bg-white/5 hover:text-gray-300"
          >
            <X size={13} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex max-h-64 flex-col border-t border-white/8 bg-surface-1">
      {/* Header */}
      <div className="flex items-center gap-2.5 border-b border-white/5 px-4 py-2">
        {isRunning ? (
          <Loader2 size={13} className="animate-spin text-accent" />
        ) : (
          <CheckCircle2 size={13} className="text-emerald-400" />
        )}
        <span className="flex-1 text-xs font-medium text-gray-200">
          {isRunning ? `执行中: ${stepName}` : `已完成: ${stepName}`}
        </span>
        {toolCount > 0 && (
          <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-gray-500">
            {toolCount} 次工具调用
          </span>
        )}
        {isRunning && (
          <button
            onClick={stopExecution}
            className="flex items-center gap-1.5 rounded-md bg-red-500/15 px-2.5 py-1 text-[11px] font-medium text-red-400 transition-colors hover:bg-red-500/25"
          >
            <Square size={9} />
            停止
          </button>
        )}
        <button
          onClick={() => setExecutionMinimized(true)}
          className="rounded p-1 text-gray-500 transition-colors hover:bg-white/5 hover:text-gray-300"
        >
          <Minimize2 size={13} />
        </button>
        {!isRunning && (
          <button
            onClick={() =>
              usePipelineStore.setState({ executionLogs: [] })
            }
            className="rounded p-1 text-gray-500 transition-colors hover:bg-white/5 hover:text-gray-300"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {/* Log area */}
      <div ref={scrollRef} className="flex-1 overflow-auto px-4 py-2">
        <div className="flex flex-col gap-1">
          {executionLogs.map((log, i) => (
            <LogEntry key={i} log={log} index={i} />
          ))}
          {isRunning && executionLogs.length === 0 && (
            <div className="flex items-center gap-2 py-4 text-gray-600">
              <Loader2 size={14} className="animate-spin" />
              <span className="text-xs">等待 Agent 响应...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

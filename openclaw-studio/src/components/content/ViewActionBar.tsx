import { useEffect } from "react";
import { Play, Loader2, RotateCcw } from "lucide-react";
import { usePipelineStore } from "../../stores/pipeline-store";
import { useProjectStore } from "../../stores/project-store";

interface TabAction {
  label: string;
  stepId: string;
  action: string;
  requiresSelection?: boolean;
  variant?: "primary" | "secondary";
}

const TAB_ACTIONS: Record<string, TabAction[]> = {
  characters: [
    {
      label: "提取角色",
      stepId: "extract-characters",
      action: "run",
      variant: "primary",
    },
    {
      label: "全部出图",
      stepId: "extract-characters",
      action: "generate-images",
    },
    {
      label: "选中出图",
      stepId: "extract-characters",
      action: "regenerate-one",
      requiresSelection: true,
    },
  ],
  scenes: [
    {
      label: "切分场景",
      stepId: "script-to-scenes",
      action: "run",
      variant: "primary",
    },
  ],
  shots: [
    {
      label: "生成分镜",
      stepId: "scenes-to-storyboard",
      action: "run",
      variant: "primary",
    },
  ],
  images: [
    {
      label: "全部出图",
      stepId: "shots-to-images",
      action: "run-all",
      variant: "primary",
    },
    {
      label: "选中出图",
      stepId: "shots-to-images",
      action: "run-selected",
      requiresSelection: true,
    },
    { label: "重试失败", stepId: "shots-to-images", action: "retry-failed" },
  ],
  audio: [
    {
      label: "全部配音",
      stepId: "shots-to-audio",
      action: "run-all",
      variant: "primary",
    },
    {
      label: "选中配音",
      stepId: "shots-to-audio",
      action: "run-selected",
      requiresSelection: true,
    },
    { label: "重试失败", stepId: "shots-to-audio", action: "retry-failed" },
  ],
  video: [
    {
      label: "合成视频",
      stepId: "compose-video",
      action: "run",
      variant: "primary",
    },
  ],
};

export function ViewActionBar({
  project,
  tab,
}: {
  project: string;
  tab: string;
}) {
  const { steps, runningStep, runStep, fetchState } = usePipelineStore();
  const focusedItem = useProjectStore((s) => s.focusedItem);

  useEffect(() => {
    fetchState(project);
  }, [project, fetchState]);

  const actions = TAB_ACTIONS[tab];
  if (!actions?.length) return null;

  const getStepStatus = (stepId: string) =>
    steps.find((s) => s.id === stepId);

  return (
    <div className="flex items-center gap-1.5 border-b border-white/[0.06] bg-surface-1/30 px-4 py-2">
      {actions.map((action) => {
        const step = getStepStatus(action.stepId);
        const isRunning = runningStep === action.stepId;
        const canRun = step?.canRun !== false;
        const needsSelection = action.requiresSelection && !focusedItem;
        const disabled = isRunning || !canRun || needsSelection;

        return (
          <button
            key={`${action.stepId}-${action.action}`}
            onClick={() => {
              const selectedIds = focusedItem ? [focusedItem.id] : undefined;
              runStep(
                project,
                action.stepId,
                action.action,
                undefined,
                selectedIds,
              );
            }}
            disabled={disabled}
            title={needsSelection ? "请先选中一个对象" : undefined}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium transition-all disabled:opacity-30 ${
              action.variant === "primary"
                ? "bg-accent text-white shadow-sm shadow-accent/20 hover:bg-accent-hover hover:shadow-accent/30"
                : "bg-white/5 text-gray-400 hover:bg-white/8 hover:text-gray-300"
            }`}
          >
            {isRunning ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <Play size={11} />
            )}
            {action.label}
          </button>
        );
      })}

      {runningStep &&
        TAB_ACTIONS[tab]?.some((a) => a.stepId === runningStep) && (
          <span className="ml-auto flex items-center gap-1.5 text-[11px] text-accent">
            <Loader2 size={11} className="animate-spin" />
            执行中...
          </span>
        )}
    </div>
  );
}

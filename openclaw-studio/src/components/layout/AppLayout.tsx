import { FileExplorer } from "../explorer/FileExplorer";
import { ContentTabs } from "../content/ContentTabs";
import { ChatPanel } from "../chat/ChatPanel";
import { SkillList } from "../skills/SkillList";
import { SkillDetail } from "../skills/SkillDetail";
import { useProjectStore } from "../../stores/project-store";
import { useSkillsStore } from "../../stores/skills-store";
import { Wrench, FolderOpen } from "lucide-react";

export function AppLayout() {
  const { currentView, setCurrentView } = useProjectStore();
  const selectedSkill = useSkillsStore((s) => s.selectedSkill);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-0 text-gray-100">
      {/* Left Panel */}
      <div className="flex w-56 flex-col border-r border-white/[0.06] bg-surface-1">
        <div className="flex items-center gap-2 border-b border-white/[0.06] px-3 py-2.5">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-accent/20">
            <span className="text-[10px] font-bold text-accent">O</span>
          </div>
          <span className="text-xs font-bold tracking-wide text-white">
            OpenClaw Studio
          </span>
        </div>

        <div className="flex border-b border-white/[0.06]">
          <button
            onClick={() => setCurrentView("workspace")}
            className={`flex flex-1 items-center justify-center gap-1.5 px-3 py-2 text-xs transition-colors ${
              currentView === "workspace"
                ? "bg-white/5 text-white"
                : "text-gray-500 hover:bg-white/[0.03] hover:text-gray-300"
            }`}
          >
            <FolderOpen size={12} /> 项目
          </button>
          <button
            onClick={() => setCurrentView("skills")}
            className={`flex flex-1 items-center justify-center gap-1.5 px-3 py-2 text-xs transition-colors ${
              currentView === "skills"
                ? "bg-white/5 text-white"
                : "text-gray-500 hover:bg-white/[0.03] hover:text-gray-300"
            }`}
          >
            <Wrench size={12} /> Skills
          </button>
        </div>

        {currentView === "workspace" ? (
          <FileExplorer />
        ) : (
          <div className="flex-1 overflow-auto">
            <SkillList />
          </div>
        )}
      </div>

      {/* Middle Panel */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {currentView === "workspace" ? (
          <ContentTabs />
        ) : selectedSkill ? (
          <SkillDetail name={selectedSkill} />
        ) : (
          <div className="flex flex-1 items-center justify-center text-gray-600">
            <p className="text-sm">选择一个 Skill 查看详情</p>
          </div>
        )}
      </div>

      {/* Right Panel */}
      <ChatPanel />
    </div>
  );
}

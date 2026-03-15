import { Plus, FolderOpen, RefreshCw, FolderInput, Upload } from "lucide-react";
import { useState, useRef, useCallback } from "react";
import { useProjects, useFileTree, useWorkspaceRoot } from "../../hooks/use-api";
import { useProjectStore } from "../../stores/project-store";
import { FileTreeItem } from "./FileTreeItem";
import { FolderPickerModal } from "./FolderPickerModal";
import { api } from "../../lib/api-client";

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI__" in window;
}

async function openTauriFolderDialog(): Promise<string | null> {
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ directory: true, multiple: false });
    return typeof selected === "string" ? selected : null;
  } catch {
    return null;
  }
}

export function FileExplorer() {
  const { currentProject, setCurrentProject } = useProjectStore();
  const { data: rootData, mutate: mutateRoot } = useWorkspaceRoot();
  const { data: projects, mutate: refreshProjects } = useProjects();
  const { data: tree, mutate: refreshTree } = useFileTree(currentProject);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [pickerMode, setPickerMode] = useState<"open" | "create" | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [quickName, setQuickName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const uploadTargetRef = useRef<string | null>(null);

  const workspacePath = rootData?.path ?? "";

  async function handleCreateProject() {
    const name = newName.trim();
    if (!name) return;
    await api.workspace.createProject(name);
    setNewName("");
    setCreating(false);
    refreshProjects();
    setCurrentProject(name);
  }

  async function applyWorkspacePath(path: string, create: boolean) {
    try {
      await api.workspace.setRoot(path, create);
      mutateRoot();
      refreshProjects();
      refreshTree();
      setCurrentProject(null);
    } catch (err) {
      alert((err as Error).message);
    }
  }

  async function handleOpenWorkspace(mode: "open" | "create") {
    if (isTauri()) {
      const selected = await openTauriFolderDialog();
      if (selected) {
        await applyWorkspacePath(selected, mode === "create");
        return;
      }
    }
    setPickerMode(mode);
  }

  function inferProjectName(files: FileList | File[], folderName?: string): string | null {
    const preferred = folderName?.trim();
    if (preferred) return preferred;
    const first = Array.from(files)[0];
    if (!first?.name) return null;
    const base = first.name.replace(/\.[^/.]+$/, "").trim();
    return base || null;
  }

  const handleUpload = useCallback(
    async (files: FileList | null, folderName?: string) => {
      if (!files || files.length === 0) return;

      const pendingName = uploadTargetRef.current;
      uploadTargetRef.current = null;
      let target = currentProject;

      if (!target && pendingName) {
        try {
          await api.workspace.createProject(pendingName);
          target = pendingName;
          setCurrentProject(pendingName);
          setQuickName("");
        } catch (err) {
          setUploadMsg(`创建项目失败: ${(err as Error).message}`);
          return;
        }
      }

      if (!target) {
        const inferred = inferProjectName(files, folderName);
        if (inferred) {
          try {
            await api.workspace.createProject(inferred);
            target = inferred;
            setCurrentProject(inferred);
            setQuickName("");
          } catch (err) {
            setUploadMsg(`创建项目失败: ${(err as Error).message}`);
            return;
          }
        }
      }

      if (!target) return;

      setUploading(true);
      setUploadMsg(null);
      try {
        const result = await api.workspace.uploadNovel(target, files, folderName);
        const parts: string[] = [];
        if (result.saved.length) parts.push(`已保存 ${result.saved.length} 个文件`);
        if (result.skipped.length)
          parts.push(`跳过 ${result.skipped.length} 个非 txt 文件`);
        setUploadMsg(parts.join("，") || "无文件保存");
        refreshProjects();
        refreshTree();
      } catch (err) {
        setUploadMsg(`上传失败: ${(err as Error).message}`);
      } finally {
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
        if (folderInputRef.current) folderInputRef.current.value = "";
      }
    },
    [currentProject, refreshProjects, refreshTree, setCurrentProject],
  );

  function triggerQuickUpload(type: "file" | "folder") {
    const name = quickName.trim();
    uploadTargetRef.current = name || null;
    if (type === "file") {
      fileInputRef.current?.click();
    } else {
      folderInputRef.current?.click();
    }
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="border-b border-white/5 px-2 py-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
          工作空间
        </span>
        <div className="mt-1 truncate rounded bg-surface-2 px-2 py-1 text-[10px] text-gray-400" title={workspacePath}>
          {workspacePath || "未设置"}
        </div>
        <div className="mt-1 flex gap-1">
          <button
            onClick={() => handleOpenWorkspace("open")}
            className="flex items-center gap-0.5 rounded bg-surface-2 px-2 py-0.5 text-[10px] text-gray-400 hover:bg-white/10 hover:text-gray-300"
            title="打开已有目录"
          >
            <FolderInput size={10} /> 打开
          </button>
          <button
            onClick={() => handleOpenWorkspace("create")}
            className="flex items-center gap-0.5 rounded bg-surface-2 px-2 py-0.5 text-[10px] text-gray-400 hover:bg-white/10 hover:text-gray-300"
            title="新建工作空间目录"
          >
            <FolderOpen size={10} /> 新建
          </button>
        </div>
      </div>

      {pickerMode && (
        <FolderPickerModal
          mode={pickerMode}
          onSelect={async (path) => {
            setPickerMode(null);
            await applyWorkspacePath(path, pickerMode === "create");
          }}
          onCancel={() => setPickerMode(null)}
        />
      )}

      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
          项目
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => {
              refreshProjects();
              refreshTree();
            }}
            className="rounded p-0.5 text-gray-600 hover:bg-white/10 hover:text-gray-300"
            title="刷新"
          >
            <RefreshCw size={12} />
          </button>
          <button
            onClick={() => setCreating(true)}
            className="rounded p-0.5 text-gray-600 hover:bg-white/10 hover:text-gray-300"
            title="新建项目"
          >
            <Plus size={12} />
          </button>
        </div>
      </div>

      {creating && (
        <div className="px-2 pb-1">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreateProject();
              if (e.key === "Escape") setCreating(false);
            }}
            onBlur={() => {
              if (!newName.trim()) setCreating(false);
            }}
            placeholder="项目名称..."
            className="w-full rounded bg-surface-2 px-2 py-1 text-xs text-gray-200 outline-none ring-1 ring-accent/40 placeholder:text-gray-600"
          />
        </div>
      )}

      <div className="border-b border-white/5 px-2 pb-1">
        <select
          value={currentProject || ""}
          onChange={(e) => setCurrentProject(e.target.value || null)}
          className="w-full rounded bg-surface-2 px-2 py-1.5 text-xs text-gray-200 outline-none"
        >
          <option value="">选择项目...</option>
          {projects?.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".txt"
        multiple
        className="hidden"
        onChange={(e) => handleUpload(e.target.files)}
      />
      <input
        ref={folderInputRef}
        type="file"
        // @ts-expect-error webkitdirectory is non-standard
        webkitdirectory=""
        multiple
        className="hidden"
        onChange={(e) => {
          const files = e.target.files;
          if (!files || files.length === 0) return;
          const first = files[0];
          const rel = first.webkitRelativePath || first.name;
          const topFolder = rel.split("/")[0] || "source";
          handleUpload(files, topFolder);
        }}
      />

      {currentProject && (
        <div className="border-b border-white/5 px-2 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            上传小说
          </span>
          <div className="mt-1 flex gap-1">
            <button
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-0.5 rounded bg-surface-2 px-2 py-0.5 text-[10px] text-gray-400 hover:bg-white/10 hover:text-gray-300 disabled:opacity-40"
              title="上传 txt 文件"
            >
              <Upload size={10} /> 文件
            </button>
            <button
              disabled={uploading}
              onClick={() => folderInputRef.current?.click()}
              className="flex items-center gap-0.5 rounded bg-surface-2 px-2 py-0.5 text-[10px] text-gray-400 hover:bg-white/10 hover:text-gray-300 disabled:opacity-40"
              title="上传文件夹（仅提取 txt）"
            >
              <FolderOpen size={10} /> 文件夹
            </button>
          </div>
          {uploading && (
            <p className="mt-1 animate-pulse text-[10px] text-accent">
              上传中...
            </p>
          )}
          {uploadMsg && !uploading && (
            <p className="mt-1 text-[10px] text-gray-400">{uploadMsg}</p>
          )}
        </div>
      )}

      <div className="flex-1 overflow-auto px-1 py-1">
        {!currentProject && (
          <div className="flex flex-col gap-3 px-2 pt-4">
            <div className="rounded-lg border border-white/5 bg-surface-2 p-3">
              <p className="text-xs font-medium text-gray-300">
                {projects && projects.length > 0
                  ? "新建项目并上传小说"
                  : "开始你的第一个项目"}
              </p>
              <p className="mt-1 text-[10px] text-gray-500">
                输入项目名称，选择 txt 文件或文件夹上传
              </p>
              <input
                value={quickName}
                onChange={(e) => setQuickName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && quickName.trim()) {
                    triggerQuickUpload("file");
                  }
                }}
                placeholder="项目名称，如：我的小说"
                className="mt-2 w-full rounded bg-surface-1 px-2 py-1.5 text-xs text-gray-200 outline-none ring-1 ring-white/10 focus:ring-accent/50 placeholder:text-gray-600"
              />
              <div className="mt-2 flex gap-1.5">
                <button
                  disabled={uploading}
                  onClick={() => triggerQuickUpload("file")}
                  className="flex flex-1 items-center justify-center gap-1 rounded bg-accent/20 px-2 py-1.5 text-[11px] font-medium text-accent hover:bg-accent/30 disabled:opacity-40"
                >
                  <Upload size={12} /> 上传文件
                </button>
                <button
                  disabled={uploading}
                  onClick={() => triggerQuickUpload("folder")}
                  className="flex flex-1 items-center justify-center gap-1 rounded bg-white/5 px-2 py-1.5 text-[11px] text-gray-400 hover:bg-white/10 hover:text-gray-300 disabled:opacity-40"
                >
                  <FolderOpen size={12} /> 上传文件夹
                </button>
              </div>
              <button
                disabled={uploading || !quickName.trim()}
                onClick={async () => {
                  const name = quickName.trim();
                  if (!name) return;
                  await api.workspace.createProject(name);
                  setQuickName("");
                  refreshProjects();
                  setCurrentProject(name);
                }}
                className="mt-1.5 w-full text-center text-[10px] text-gray-500 hover:text-gray-400 disabled:opacity-40"
              >
                仅创建项目，稍后上传
              </button>
              {uploading && (
                <p className="mt-2 animate-pulse text-center text-[10px] text-accent">
                  上传中...
                </p>
              )}
              {uploadMsg && !uploading && (
                <p className="mt-2 text-center text-[10px] text-gray-400">
                  {uploadMsg}
                </p>
              )}
            </div>
            {projects && projects.length > 0 && (
              <p className="text-center text-[10px] text-gray-600">
                或从上方下拉框选择已有项目
              </p>
            )}
          </div>
        )}
        {currentProject && tree && (
          <div>
            {tree.map((entry) => (
              <FileTreeItem key={entry.path} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

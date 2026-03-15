import { useCharacters, useScenes, useShots } from "../../hooks/use-api";
import { useProjectStore } from "../../stores/project-store";
import { api } from "../../lib/api-client";
import { resolveImageSrc } from "../../lib/asset-resolver";
import { FallbackImage } from "../ui/FallbackImage";
import {
  Users,
  ChevronDown,
  ChevronRight,
  Copy,
  Pencil,
  Save,
  X,
  Film,
  Clapperboard,
  Check,
  Sparkles,
} from "lucide-react";
import { useState, useCallback } from "react";
import { useSWRConfig } from "swr";
import type { Character } from "../../lib/types";

const TYPE_COLORS: Record<string, string> = {
  主角: "bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/20",
  配角: "bg-blue-500/15 text-blue-400 ring-1 ring-blue-500/20",
  群演: "bg-gray-500/15 text-gray-400 ring-1 ring-gray-500/20",
  特殊: "bg-purple-500/15 text-purple-400 ring-1 ring-purple-500/20",
};

function TypeBadge({ type }: { type: string }) {
  return (
    <span
      className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${TYPE_COLORS[type] ?? "bg-white/10 text-gray-400"}`}
    >
      {type}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] text-gray-500 transition-colors hover:bg-white/5 hover:text-gray-300"
    >
      {copied ? <Check size={10} /> : <Copy size={10} />}
      {copied ? "已复制" : "复制"}
    </button>
  );
}

function CharacterDetail({
  char,
  project,
  relatedScenes,
  relatedShotCount,
  onNavigateScene,
}: {
  char: Character;
  project: string;
  relatedScenes: string[];
  relatedShotCount: number;
  onNavigateScene: (sceneId: string) => void;
}) {
  const { mutate } = useSWRConfig();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Partial<Character>>({});
  const [saving, setSaving] = useState(false);

  const startEdit = () => {
    setDraft({
      description: char.description,
      prompt: char.prompt,
      immutable_features: [...(char.immutable_features ?? [])],
    });
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setDraft({});
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.workspace.updateCharacter(project, char.id, draft);
      await mutate(`chars-${project}`);
      setEditing(false);
      setDraft({});
    } finally {
      setSaving(false);
    }
  };

  const src = resolveImageSrc(project, char.image_url, char.image_path);

  return (
    <div className="flex flex-col gap-4 border-t border-white/5 bg-gradient-to-b from-surface-1/80 to-surface-1/40 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-gray-500">
            {char.id}
          </span>
          <TypeBadge type={char.type} />
          {char.first_appearance && (
            <span className="text-[11px] text-gray-500">
              首次出场: {char.first_appearance}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {editing ? (
            <>
              <button
                onClick={cancel}
                className="flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] text-gray-400 transition-colors hover:bg-white/5"
              >
                <X size={11} /> 取消
              </button>
              <button
                onClick={save}
                disabled={saving}
                className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-[11px] text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
              >
                <Save size={11} /> {saving ? "..." : "保存"}
              </button>
            </>
          ) : (
            <button
              onClick={startEdit}
              className="flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] text-gray-500 transition-colors hover:bg-white/5 hover:text-gray-300"
            >
              <Pencil size={11} /> 编辑
            </button>
          )}
        </div>
      </div>

      <div className="flex gap-5">
        <div className="w-48 shrink-0 overflow-hidden rounded-xl">
          {src ? (
            <FallbackImage
              src={src}
              alt={char.name}
              className="w-full rounded-xl object-cover shadow-lg"
              fallbackClassName="flex h-64 w-full items-center justify-center rounded-xl bg-surface-3 text-gray-600"
              fallbackIcon={<Users size={40} strokeWidth={1} />}
            />
          ) : (
            <div className="flex h-64 items-center justify-center rounded-xl bg-surface-3 text-gray-600">
              <Users size={40} strokeWidth={1} />
            </div>
          )}
          {char.image_status && (
            <div className="mt-2 text-center">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] ${
                  char.image_status === "completed"
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "bg-gray-500/10 text-gray-500"
                }`}
              >
                {char.image_status === "completed" ? (
                  <>
                    <Sparkles size={9} /> 已生成
                  </>
                ) : (
                  char.image_status
                )}
              </span>
            </div>
          )}
        </div>

        <div className="flex flex-1 flex-col gap-4">
          <div>
            <div className="mb-1.5 text-[11px] font-medium text-gray-500">
              不可变特征
            </div>
            <div className="flex flex-wrap gap-1.5">
              {(editing
                ? draft.immutable_features
                : char.immutable_features
              )?.map((f, i) => (
                <span
                  key={i}
                  className="rounded-md bg-white/5 px-2.5 py-1 text-[11px] text-gray-400 ring-1 ring-white/5"
                >
                  {f}
                </span>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-1.5 text-[11px] font-medium text-gray-500">
              描述
            </div>
            {editing ? (
              <textarea
                value={draft.description ?? ""}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, description: e.target.value }))
                }
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-surface-3 px-3 py-2 text-xs leading-relaxed text-gray-200 outline-none transition-colors focus:border-accent/50"
              />
            ) : (
              <p className="text-xs leading-relaxed text-gray-400">
                {char.description}
              </p>
            )}
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[11px] font-medium text-gray-500">
                提示词
              </span>
              {!editing && char.prompt && <CopyButton text={char.prompt} />}
            </div>
            {editing ? (
              <textarea
                value={draft.prompt ?? ""}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, prompt: e.target.value }))
                }
                rows={4}
                className="w-full rounded-lg border border-white/10 bg-surface-3 px-3 py-2 font-mono text-[11px] leading-relaxed text-gray-200 outline-none transition-colors focus:border-accent/50"
              />
            ) : (
              <p className="rounded-lg bg-surface-3/50 px-3 py-2 font-mono text-[11px] leading-relaxed text-gray-500">
                {char.prompt}
              </p>
            )}
          </div>

          {(relatedScenes.length > 0 || relatedShotCount > 0) && (
            <div className="flex flex-wrap items-center gap-2.5 border-t border-white/5 pt-3">
              {relatedScenes.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <Film size={12} className="text-gray-600" />
                  <span className="text-[10px] text-gray-500">出场场景:</span>
                  {relatedScenes.map((sid) => (
                    <button
                      key={sid}
                      onClick={() => onNavigateScene(sid)}
                      className="rounded-md bg-white/5 px-2 py-0.5 font-mono text-[10px] text-gray-400 transition-colors hover:bg-accent/20 hover:text-accent"
                    >
                      {sid}
                    </button>
                  ))}
                </div>
              )}
              {relatedShotCount > 0 && (
                <div className="flex items-center gap-1.5">
                  <Clapperboard size={12} className="text-gray-600" />
                  <span className="text-[10px] text-gray-500">
                    关联分镜: {relatedShotCount} 个
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function CharacterView({ project }: { project: string }) {
  const { data: characters, isLoading } = useCharacters(project);
  const { data: scenesData } = useScenes(project);
  const { data: shotsData } = useShots(project);
  const setCurrentTab = useProjectStore((s) => s.setCurrentTab);
  const expandedId = useProjectStore((s) => s.getFocusedId("character"));
  const setExpandedId = (id: string | null) => {
    const store = useProjectStore.getState();
    if (id) store.setFocusedItem("character", id);
    else store.clearFocus();
  };
  const [typeFilter, setTypeFilter] = useState<string | null>(null);

  const scenes = scenesData?.scenes ?? [];
  const shotScenes = shotsData?.scenes ?? [];

  const getRelatedScenes = useCallback(
    (charName: string): string[] => {
      return scenes
        .filter((s) => s.main_characters?.includes(charName))
        .map((s) => s.id);
    },
    [scenes],
  );

  const getRelatedShotCount = useCallback(
    (charId: string): number => {
      let count = 0;
      for (const scene of shotScenes) {
        for (const shot of scene.shots) {
          if (shot.characters?.some((c) => c.ref === charId)) {
            count++;
          }
        }
      }
      return count;
    },
    [shotScenes],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-600">
        <span className="text-sm">加载中...</span>
      </div>
    );
  }

  if (!characters || characters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-gray-600">
        <div className="rounded-2xl bg-surface-2 p-4">
          <Users size={32} strokeWidth={1} />
        </div>
        <p className="text-sm font-medium text-gray-400">暂无角色数据</p>
        <p className="text-xs text-gray-600">
          在 Agent 中输入「提取角色」开始
        </p>
      </div>
    );
  }

  const types = [...new Set(characters.map((c) => c.type))];
  const filtered = typeFilter
    ? characters.filter((c) => c.type === typeFilter)
    : characters;

  return (
    <div className="flex flex-col gap-0">
      <div className="flex items-center gap-2.5 border-b border-white/5 px-4 py-2.5">
        <Users size={14} className="text-accent" />
        <span className="text-xs font-medium text-gray-300">
          角色资产 ({characters.length})
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => setTypeFilter(null)}
            className={`rounded-md px-2.5 py-1 text-[11px] transition-colors ${
              !typeFilter
                ? "bg-accent/15 text-accent"
                : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
            }`}
          >
            全部
          </button>
          {types.map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t === typeFilter ? null : t)}
              className={`rounded-md px-2.5 py-1 text-[11px] transition-colors ${
                typeFilter === t
                  ? "bg-accent/15 text-accent"
                  : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {filtered.map((char) => {
          const isSelected = expandedId === char.id;
          const src = resolveImageSrc(
            project,
            char.image_url,
            char.image_path,
          );

          return (
            <div
              key={char.id}
              className={`group flex flex-col overflow-hidden rounded-xl border transition-all duration-200 ${
                isSelected
                  ? "border-accent/30 bg-surface-2 shadow-lg shadow-accent/5"
                  : "border-white/5 bg-surface-2 hover:border-white/10 hover:shadow-md hover:shadow-black/20"
              }`}
            >
              <button
                onClick={() =>
                  setExpandedId(isSelected ? null : char.id)
                }
                data-character-id={char.id}
                className="flex flex-col text-left"
              >
                <div className="relative aspect-[3/4] w-full overflow-hidden bg-surface-3">
                  {src ? (
                    <FallbackImage
                      src={src}
                      alt={char.name}
                      className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                      fallbackClassName="flex h-full w-full items-center justify-center bg-surface-3 text-gray-600"
                      fallbackIcon={<Users size={32} strokeWidth={1} />}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-gray-600">
                      <Users size={32} strokeWidth={1} />
                    </div>
                  )}
                  {char.image_status === "completed" && (
                    <div className="absolute bottom-1.5 right-1.5 rounded-full bg-emerald-500/80 p-0.5">
                      <Check size={10} className="text-white" />
                    </div>
                  )}
                </div>
                <div className="flex flex-col gap-1.5 p-3">
                  <div className="flex items-center gap-1.5">
                    <h3 className="truncate text-sm font-medium text-white">
                      {char.name}
                    </h3>
                    <TypeBadge type={char.type} />
                    <span className="ml-auto shrink-0 text-gray-600 transition-colors group-hover:text-gray-400">
                      {isSelected ? (
                        <ChevronDown size={14} />
                      ) : (
                        <ChevronRight size={14} />
                      )}
                    </span>
                  </div>
                  <p className="line-clamp-2 text-[11px] leading-relaxed text-gray-500">
                    {char.description}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {char.immutable_features?.slice(0, 3).map((f, i) => (
                      <span
                        key={i}
                        className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-gray-500"
                      >
                        {f}
                      </span>
                    ))}
                    {(char.immutable_features?.length ?? 0) > 3 && (
                      <span className="text-[10px] text-gray-600">
                        +{(char.immutable_features?.length ?? 0) - 3}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            </div>
          );
        })}
      </div>

      {expandedId && (
        <div className="mx-4 mb-4 overflow-hidden rounded-xl border border-white/5 bg-surface-2">
          {(() => {
            const char = characters.find((c) => c.id === expandedId);
            if (!char) return null;
            return (
              <CharacterDetail
                char={char}
                project={project}
                relatedScenes={getRelatedScenes(char.name)}
                relatedShotCount={getRelatedShotCount(char.id)}
                onNavigateScene={() => setCurrentTab("scenes")}
              />
            );
          })()}
        </div>
      )}
    </div>
  );
}

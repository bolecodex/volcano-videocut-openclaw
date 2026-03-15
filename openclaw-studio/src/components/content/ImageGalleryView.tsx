import { useShots } from "../../hooks/use-api";
import { resolveImageSrc } from "../../lib/asset-resolver";
import { FallbackImage } from "../ui/FallbackImage";
import { Image as ImageIcon, Inbox, Maximize2, X, ImageOff } from "lucide-react";
import { useState } from "react";
import type { ShotInfo } from "../../lib/types";

interface ImageEntry {
  shotId: string;
  sceneId: string;
  sceneName: string;
  title: string;
  imageUrl: string;
  shotType: string;
  prompt: string;
}

function LightboxModal({
  entry,
  onClose,
}: {
  entry: ImageEntry;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] max-w-[90vw]"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute -right-3 -top-3 z-10 rounded-full bg-surface-2 p-1.5 text-gray-400 shadow-lg transition-colors hover:text-white"
        >
          <X size={16} />
        </button>
        <FallbackImage
          src={entry.imageUrl}
          alt={entry.title}
          className="max-h-[85vh] rounded-xl object-contain shadow-2xl"
          fallbackClassName="flex h-64 w-64 items-center justify-center rounded-xl bg-surface-2 text-gray-600"
          fallbackIcon={<ImageOff size={40} strokeWidth={1} />}
        />
        <div className="mt-3 text-center">
          <span className="font-mono text-xs text-accent">{entry.shotId}</span>
          <span className="mx-2 text-xs text-gray-600">·</span>
          <span className="text-xs text-gray-500">{entry.shotType}</span>
          <span className="mx-2 text-xs text-gray-600">·</span>
          <span className="text-xs text-gray-400">{entry.sceneName}</span>
        </div>
      </div>
    </div>
  );
}

export function ImageGalleryView({ project }: { project: string }) {
  const { data, isLoading } = useShots(project);
  const [lightbox, setLightbox] = useState<ImageEntry | null>(null);
  const [filter, setFilter] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-600">
        <span className="text-sm">加载中...</span>
      </div>
    );
  }

  const entries: ImageEntry[] = [];
  const sceneNames = new Set<string>();

  for (const scene of data?.scenes ?? []) {
    sceneNames.add(scene.sceneName);
    for (const shot of scene.shots as ShotInfo[]) {
      const resolved = resolveImageSrc(
        project,
        shot.image_url,
        shot.image_path,
        "shots/",
      );
      if (!resolved || shot.image_status === "pending") continue;
      entries.push({
        shotId: shot.id,
        sceneId: scene.sceneId,
        sceneName: scene.sceneName,
        title: shot.title?.replace(/\*\*/g, "") ?? shot.id,
        imageUrl: resolved,
        shotType: shot.shot_type ?? "",
        prompt: shot.prompt ?? "",
      });
    }
  }

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-gray-600">
        <div className="rounded-2xl bg-surface-2 p-4">
          <Inbox size={32} strokeWidth={1} />
        </div>
        <p className="text-sm font-medium text-gray-400">暂无图片</p>
        <p className="text-xs text-gray-600">
          在 Agent 中输入「生成配图」开始
        </p>
      </div>
    );
  }

  const filtered = filter
    ? entries.filter((e) => e.sceneName === filter)
    : entries;

  return (
    <div className="flex flex-col gap-0">
      <div className="flex items-center gap-2.5 border-b border-white/5 px-4 py-2.5">
        <ImageIcon size={14} className="text-accent" />
        <span className="text-xs font-medium text-gray-300">
          图片 ({entries.length})
        </span>
        <span className="text-[11px] text-gray-600">
          {sceneNames.size} 个场景
        </span>
      </div>

      {sceneNames.size > 1 && (
        <div className="flex flex-wrap gap-1 border-b border-white/5 px-4 py-2">
          <button
            onClick={() => setFilter(null)}
            className={`rounded-md px-2.5 py-1 text-[11px] transition-colors ${
              !filter
                ? "bg-accent/15 text-accent"
                : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
            }`}
          >
            全部
          </button>
          {[...sceneNames].map((name) => (
            <button
              key={name}
              onClick={() => setFilter(filter === name ? null : name)}
              className={`rounded-md px-2.5 py-1 text-[11px] transition-colors ${
                filter === name
                  ? "bg-accent/15 text-accent"
                  : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {filtered.map((entry) => (
          <div
            key={entry.shotId}
            className="group relative flex flex-col overflow-hidden rounded-xl border border-white/5 bg-surface-2 transition-all duration-200 hover:border-white/10 hover:shadow-md hover:shadow-black/20"
          >
            <div className="relative overflow-hidden">
              <FallbackImage
                src={entry.imageUrl}
                alt={entry.title}
                className="h-40 w-full object-cover transition-transform duration-300 group-hover:scale-105"
                loading="lazy"
                fallbackClassName="flex h-40 w-full items-center justify-center bg-surface-3 text-gray-600"
                fallbackIcon={<ImageOff size={24} strokeWidth={1.5} />}
              />
              <button
                onClick={() => setLightbox(entry)}
                className="absolute right-2 top-2 rounded-lg bg-black/50 p-1.5 text-white/60 opacity-0 backdrop-blur-sm transition-all hover:text-white group-hover:opacity-100"
              >
                <Maximize2 size={13} />
              </button>
            </div>
            <div className="flex flex-col gap-1 p-2.5">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-accent">
                  {entry.shotId}
                </span>
                <span className="text-[10px] text-gray-600">
                  {entry.shotType}
                </span>
              </div>
              <p className="line-clamp-2 text-[11px] leading-relaxed text-gray-400">
                {entry.title}
              </p>
            </div>
          </div>
        ))}
      </div>

      {lightbox && (
        <LightboxModal entry={lightbox} onClose={() => setLightbox(null)} />
      )}
    </div>
  );
}

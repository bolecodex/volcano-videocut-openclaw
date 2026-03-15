import { useMedia } from "../../hooks/use-api";
import { Image as ImageIcon, Music, Video, Inbox } from "lucide-react";
import { FallbackImage } from "../ui/FallbackImage";

const ICONS = {
  images: ImageIcon,
  audio: Music,
  video: Video,
} as const;

const LABELS = {
  images: "图片",
  audio: "音频",
  video: "视频",
} as const;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function MediaGallery({
  project,
  type,
}: {
  project: string;
  type: "images" | "audio" | "video";
}) {
  const { data: files, isLoading } = useMedia(project, type);
  const Icon = ICONS[type];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-600">
        <span className="text-sm">加载中...</span>
      </div>
    );
  }

  if (!files || files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-12 text-gray-600">
        <Inbox size={32} strokeWidth={1} />
        <p className="text-sm">暂无{LABELS[type]}文件</p>
      </div>
    );
  }

  if (type === "images") {
    return (
      <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {files.map((f) => (
          <div
            key={f.path}
            className="flex flex-col rounded-lg border border-white/5 bg-surface-2 overflow-hidden"
          >
            <FallbackImage
              src={`/api/workspace/file-raw?path=${encodeURIComponent(f.path)}`}
              alt={f.name}
              className="h-32 w-full object-cover"
              fallbackClassName="flex h-32 w-full items-center justify-center bg-surface-3 text-gray-600"
            />
            <div className="p-2">
              <p className="truncate text-xs text-gray-300">{f.name}</p>
              <p className="text-[10px] text-gray-600">{formatSize(f.size)}</p>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 p-4">
      {files.map((f) => (
        <div
          key={f.path}
          className="flex items-center gap-3 rounded-lg border border-white/5 bg-surface-2 p-3"
        >
          <Icon size={16} className="shrink-0 text-gray-500" />
          <div className="flex-1 min-w-0">
            <p className="truncate text-xs text-gray-300">{f.name}</p>
            <p className="text-[10px] text-gray-600">{formatSize(f.size)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

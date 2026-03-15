import { useFileContent } from "../../hooks/use-api";
import { FileText } from "lucide-react";
import { FallbackImage } from "../ui/FallbackImage";

const IMAGE_EXTS = ["png", "jpg", "jpeg", "webp", "gif"];
const VIDEO_EXTS = ["mp4", "webm", "mov"];
const AUDIO_EXTS = ["mp3", "wav", "m4a", "ogg", "aac", "flac"];

export function FileEditor({ path }: { path: string }) {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  const rawUrl = `/api/workspace/file-raw?path=${encodeURIComponent(path)}`;

  const isImage = IMAGE_EXTS.includes(ext);
  const isVideo = VIDEO_EXTS.includes(ext);
  const isAudio = AUDIO_EXTS.includes(ext);
  const isBinary = isImage || isVideo || isAudio;

  const { data, isLoading, error } = useFileContent(isBinary ? null : path);

  if (isImage) {
    return (
      <div className="flex items-center justify-center p-4">
        <FallbackImage
          src={rawUrl}
          alt={path}
          className="max-h-[80vh] rounded-lg"
          fallbackClassName="flex h-64 items-center justify-center rounded-lg bg-surface-2 text-gray-600"
        />
      </div>
    );
  }

  if (isVideo) {
    return (
      <div className="flex items-center justify-center bg-black p-4">
        <video
          key={path}
          src={rawUrl}
          controls
          className="max-h-[80vh] w-full rounded"
        />
      </div>
    );
  }

  if (isAudio) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-12">
        <p className="text-sm text-gray-400">{path.split("/").pop()}</p>
        <audio key={path} src={rawUrl} controls />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-600">
        <span className="text-sm">加载中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-12 text-red-400">
        <FileText size={24} />
        <p className="text-sm">无法读取文件</p>
        <p className="text-xs text-gray-500">{path}</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <pre className="p-4 text-xs leading-relaxed text-gray-300 whitespace-pre-wrap">
        {data?.content}
      </pre>
    </div>
  );
}

import { useShots } from "../../hooks/use-api";
import { resolveAudioSrc } from "../../lib/asset-resolver";
import { Music, Play, Pause, Volume2, Inbox } from "lucide-react";
import { useState, useRef, useCallback, useEffect } from "react";
import type { ShotInfo } from "../../lib/types";

interface AudioEntry {
  shotId: string;
  sceneId: string;
  sceneName: string;
  title: string;
  speaker?: string;
  audioUrl: string;
  status: string;
}

function AudioItem({
  entry,
  isPlaying,
  onToggle,
}: {
  entry: AudioEntry;
  isPlaying: boolean;
  onToggle: () => void;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState(false);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    if (isPlaying) {
      el.play().catch(() => setError(true));
    } else {
      el.pause();
    }
  }, [isPlaying]);

  const onTimeUpdate = useCallback(() => {
    const el = audioRef.current;
    if (!el || !el.duration) return;
    setProgress(el.currentTime / el.duration);
  }, []);

  const onLoadedMetadata = useCallback(() => {
    const el = audioRef.current;
    if (el) setDuration(el.duration);
  }, []);

  const onEnded = useCallback(() => {
    setProgress(0);
    onToggle();
  }, [onToggle]);

  const seek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const el = audioRef.current;
    if (!el || !el.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    el.currentTime = pct * el.duration;
    setProgress(pct);
  }, []);

  const fmtTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-white/5 bg-surface-2 p-3 transition-colors hover:border-white/10">
      <audio
        ref={audioRef}
        src={entry.audioUrl}
        preload="metadata"
        onTimeUpdate={onTimeUpdate}
        onLoadedMetadata={onLoadedMetadata}
        onEnded={onEnded}
        onError={() => setError(true)}
      />

      <button
        onClick={onToggle}
        disabled={error}
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors ${
          error
            ? "bg-red-500/10 text-red-400"
            : isPlaying
              ? "bg-accent/20 text-accent"
              : "bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white"
        }`}
      >
        {error ? (
          <Volume2 size={14} />
        ) : isPlaying ? (
          <Pause size={14} />
        ) : (
          <Play size={14} className="ml-0.5" />
        )}
      </button>

      <div className="flex flex-1 flex-col gap-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-accent">{entry.shotId}</span>
          {entry.speaker && (
            <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-gray-400">
              {entry.speaker}
            </span>
          )}
          <span className="flex-1 truncate text-xs text-gray-300">{entry.title}</span>
        </div>

        <div className="flex items-center gap-2">
          <div
            className="flex-1 h-1 cursor-pointer rounded-full bg-white/5"
            onClick={seek}
          >
            <div
              className="h-full rounded-full bg-accent/60 transition-all"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
          {duration > 0 && (
            <span className="text-[10px] text-gray-600 tabular-nums">
              {fmtTime(progress * duration)}/{fmtTime(duration)}
            </span>
          )}
        </div>
      </div>

      <span className="text-[10px] text-gray-600">{entry.sceneName}</span>
    </div>
  );
}

export function AudioView({ project }: { project: string }) {
  const { data, isLoading } = useShots(project);
  const [playingId, setPlayingId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-600">
        <span className="text-sm">加载中...</span>
      </div>
    );
  }

  const entries: AudioEntry[] = [];
  for (const scene of data?.scenes ?? []) {
    for (const shot of scene.shots as ShotInfo[]) {
      let hasLineAudio = false;
      if (shot.lines) {
        for (let i = 0; i < shot.lines.length; i++) {
          const line = shot.lines[i];
          if (line.audio_status !== "completed") continue;
          const resolved = resolveAudioSrc(project, line.audio_url, line.audio_path);
          if (!resolved) continue;
          hasLineAudio = true;
          entries.push({
            shotId: `${shot.id}_line_${i}`,
            sceneId: scene.sceneId,
            sceneName: scene.sceneName,
            title: line.text ?? "",
            speaker: line.speaker,
            audioUrl: resolved,
            status: "completed",
          });
        }
      }
      if (!hasLineAudio && shot.audio_status !== "pending") {
        const resolved = resolveAudioSrc(project, shot.audio_url, shot.audio_path);
        if (!resolved) continue;
        entries.push({
          shotId: shot.id,
          sceneId: scene.sceneId,
          sceneName: scene.sceneName,
          title: shot.title?.replace(/\*\*/g, "") ?? shot.id,
          speaker: shot.audio_speaker,
          audioUrl: resolved,
          status: shot.audio_status ?? "completed",
        });
      }
    }
  }

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-12 text-gray-600">
        <Inbox size={32} strokeWidth={1} />
        <p className="text-sm">暂无音频</p>
        <p className="text-xs">在 Agent 中输入「生成配音」开始</p>
      </div>
    );
  }

  const toggle = (id: string) => {
    setPlayingId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="flex flex-col gap-0">
      <div className="flex items-center gap-2 border-b border-white/5 px-4 py-2">
        <Music size={14} className="text-accent" />
        <span className="text-xs font-medium text-gray-300">
          音频 ({entries.length})
        </span>
        <span className="text-[10px] text-gray-600">
          {data?.scenes?.length ?? 0} 个场景
        </span>
      </div>

      <div className="flex flex-col gap-2 p-4">
        {entries.map((entry) => (
          <AudioItem
            key={entry.shotId}
            entry={entry}
            isPlaying={playingId === entry.shotId}
            onToggle={() => toggle(entry.shotId)}
          />
        ))}
      </div>
    </div>
  );
}

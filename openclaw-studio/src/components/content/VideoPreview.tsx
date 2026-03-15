import { useShots } from "../../hooks/use-api";
import { resolveImageSrc, resolveAudioSrc } from "../../lib/asset-resolver";
import { FallbackImage } from "../ui/FallbackImage";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Inbox,
  Gauge,
} from "lucide-react";
import {
  useState,
  useRef,
  useCallback,
  useEffect,
  useMemo,
} from "react";
import type { ShotInfo } from "../../lib/types";

interface TimelineEntry {
  shotId: string;
  sceneId: string;
  sceneName: string;
  imageUrl: string;
  audioUrl: string | null;
  subtitle: string;
  speaker: string;
  startTime: number;
  duration: number;
}

const PLAYBACK_RATES = [0.5, 1, 1.5, 2];
const DEFAULT_SHOT_DURATION = 3;

function parseShotContent(title: string): { speaker: string; text: string } {
  const cleaned = title.replace(/\*\*/g, "");
  const match = cleaned.match(/^(.+?)(?:：|:)\s*([\s\S]*)$/);
  if (match) return { speaker: match[1].trim(), text: match[2].trim() };
  return { speaker: "", text: cleaned.trim() };
}

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function ShotTimeline({
  entries,
  currentIndex,
  onSelect,
}: {
  entries: TimelineEntry[];
  currentIndex: number;
  onSelect: (index: number) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "center",
    });
  }, [currentIndex]);

  return (
    <div
      ref={scrollRef}
      className="flex gap-1.5 overflow-x-auto px-4 py-2 scrollbar-thin"
    >
      {entries.map((entry, i) => (
        <button
          key={entry.shotId}
          ref={i === currentIndex ? activeRef : undefined}
          onClick={() => onSelect(i)}
          className={`flex shrink-0 flex-col items-center gap-1 rounded-lg border p-1 transition-all ${
            i === currentIndex
              ? "border-accent bg-accent/10"
              : "border-white/5 bg-surface-2 hover:border-white/10"
          }`}
          style={{ width: 72 }}
        >
          <FallbackImage
            src={entry.imageUrl}
            alt={entry.shotId}
            className="h-10 w-full rounded object-cover"
            loading="lazy"
            fallbackClassName="flex h-10 w-full items-center justify-center rounded bg-surface-3 text-gray-600 text-[8px]"
          />
          <span
            className={`text-[9px] tabular-nums ${i === currentIndex ? "text-accent" : "text-gray-500"}`}
          >
            {entry.shotId.replace("shot_", "")}
          </span>
        </button>
      ))}
    </div>
  );
}

export function VideoPreview({ project }: { project: string }) {
  const { data, isLoading } = useShots(project);

  const [currentIndex, setCurrentIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [transitioning, setTransitioning] = useState(false);

  const audioRef = useRef<HTMLAudioElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const prevImageRef = useRef<string | null>(null);

  const entries = useMemo<TimelineEntry[]>(() => {
    const result: TimelineEntry[] = [];
    let cumTime = 0;
    for (const scene of data?.scenes ?? []) {
      for (const shot of scene.shots as ShotInfo[]) {
        const imgSrc = resolveImageSrc(project, shot.image_url, shot.image_path, "shots/");
        if (!imgSrc) continue;
        const { speaker, text } = parseShotContent(shot.title ?? shot.id);
        const dur = shot.duration_sec ?? DEFAULT_SHOT_DURATION;
        const audioSrc = shot.audio_status !== "pending"
          ? resolveAudioSrc(project, shot.audio_url, shot.audio_path) ?? null
          : null;
        result.push({
          shotId: shot.id,
          sceneId: scene.sceneId,
          sceneName: scene.sceneName,
          imageUrl: imgSrc,
          audioUrl: audioSrc,
          subtitle: text,
          speaker,
          startTime: cumTime,
          duration: dur,
        });
        cumTime += dur;
      }
    }
    return result;
  }, [data, project]);

  const totalDuration = useMemo(
    () => entries.reduce((acc, e) => acc + e.duration, 0),
    [entries],
  );

  const current = entries[currentIndex];

  const goTo = useCallback(
    (index: number) => {
      if (index < 0 || index >= entries.length) return;
      clearTimeout(timerRef.current);
      prevImageRef.current = entries[currentIndex]?.imageUrl ?? null;
      setTransitioning(true);
      setTimeout(() => setTransitioning(false), 500);
      setCurrentIndex(index);
      setAudioProgress(0);
      setAudioDuration(0);
      const el = audioRef.current;
      if (el) {
        el.pause();
        el.currentTime = 0;
      }
    },
    [entries, currentIndex],
  );

  const playNext = useCallback(() => {
    if (currentIndex < entries.length - 1) {
      goTo(currentIndex + 1);
      setPlaying(true);
    } else {
      setPlaying(false);
    }
  }, [currentIndex, entries.length, goTo]);

  useEffect(() => {
    const el = audioRef.current;
    if (!el || !current) return;

    if (current.audioUrl) {
      el.src = current.audioUrl;
      el.playbackRate = playbackRate;
      if (playing) {
        el.play().catch(() => {});
      }
    } else if (playing) {
      const dur = (current.duration * 1000) / playbackRate;
      timerRef.current = setTimeout(playNext, dur);
    }

    return () => clearTimeout(timerRef.current);
  }, [currentIndex, playing, current, playbackRate, playNext]);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  const onAudioTimeUpdate = useCallback(() => {
    const el = audioRef.current;
    if (!el || !el.duration) return;
    setAudioProgress(el.currentTime);
    setAudioDuration(el.duration);
  }, []);

  const onAudioEnded = useCallback(() => {
    playNext();
  }, [playNext]);

  const onAudioLoadedMetadata = useCallback(() => {
    const el = audioRef.current;
    if (el) setAudioDuration(el.duration);
  }, []);

  const togglePlay = useCallback(() => {
    if (playing) {
      audioRef.current?.pause();
      clearTimeout(timerRef.current);
    }
    setPlaying((p) => !p);
  }, [playing]);

  const seekGlobal = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const targetTime = pct * totalDuration;

      let cumulative = 0;
      for (let i = 0; i < entries.length; i++) {
        if (cumulative + entries[i].duration > targetTime) {
          goTo(i);
          break;
        }
        cumulative += entries[i].duration;
      }
    },
    [entries, totalDuration, goTo],
  );

  const globalProgress = useMemo(() => {
    if (!current || totalDuration === 0) return 0;
    const elapsed = current.startTime + (audioDuration > 0 ? audioProgress : 0);
    return elapsed / totalDuration;
  }, [current, totalDuration, audioProgress, audioDuration]);

  const currentGlobalTime = useMemo(() => {
    if (!current) return 0;
    return current.startTime + (audioDuration > 0 ? audioProgress : 0);
  }, [current, audioProgress, audioDuration]);

  const cycleRate = useCallback(() => {
    setPlaybackRate((r) => {
      const idx = PLAYBACK_RATES.indexOf(r);
      return PLAYBACK_RATES[(idx + 1) % PLAYBACK_RATES.length];
    });
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-600">
        <span className="text-sm">加载中...</span>
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-12 text-gray-600">
        <Inbox size={32} strokeWidth={1} />
        <p className="text-sm">暂无可预览的镜头</p>
        <p className="text-xs">需要先生成配图</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0">
      <audio
        ref={audioRef}
        preload="metadata"
        onTimeUpdate={onAudioTimeUpdate}
        onEnded={onAudioEnded}
        onLoadedMetadata={onAudioLoadedMetadata}
      />

      {/* Canvas */}
      <div className="relative flex items-center justify-center bg-black" style={{ minHeight: 360 }}>
        {prevImageRef.current && transitioning && (
          <img
            src={prevImageRef.current}
            className="absolute inset-0 h-full w-full object-contain opacity-0 transition-opacity duration-500"
            alt=""
          />
        )}
        {current && (
          <img
            key={current.shotId}
            src={current.imageUrl}
            alt={current.subtitle}
            className={`h-full max-h-[60vh] w-full object-contain transition-opacity duration-500 ${
              transitioning ? "opacity-0" : "opacity-100"
            }`}
            style={{ animationFillMode: "forwards" }}
          />
        )}

        {/* Subtitle overlay */}
        {current && current.subtitle && (
          <div className="absolute bottom-4 left-4 right-4 flex justify-center">
            <div className="rounded-lg bg-black/70 px-4 py-2 backdrop-blur-sm">
              {current.speaker && (
                <span className="mr-2 text-xs font-medium text-accent">
                  {current.speaker}
                </span>
              )}
              <span className="text-sm text-white">{current.subtitle}</span>
            </div>
          </div>
        )}

        {/* Shot counter */}
        <div className="absolute right-3 top-3 rounded bg-black/50 px-2 py-1">
          <span className="font-mono text-[10px] text-white/60">
            {currentIndex + 1} / {entries.length}
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 border-y border-white/5 bg-surface-1 px-4 py-2">
        <button
          onClick={() => goTo(currentIndex - 1)}
          disabled={currentIndex === 0}
          className="text-gray-400 hover:text-white disabled:opacity-30"
        >
          <SkipBack size={16} />
        </button>

        <button
          onClick={togglePlay}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/20 text-accent hover:bg-accent/30"
        >
          {playing ? <Pause size={16} /> : <Play size={16} className="ml-0.5" />}
        </button>

        <button
          onClick={() => goTo(currentIndex + 1)}
          disabled={currentIndex === entries.length - 1}
          className="text-gray-400 hover:text-white disabled:opacity-30"
        >
          <SkipForward size={16} />
        </button>

        {/* Global progress bar */}
        <div className="flex flex-1 items-center gap-2">
          <div
            className="h-1.5 flex-1 cursor-pointer rounded-full bg-white/5"
            onClick={seekGlobal}
          >
            <div
              className="h-full rounded-full bg-accent/60 transition-all"
              style={{ width: `${globalProgress * 100}%` }}
            />
          </div>
          <span className="text-[10px] tabular-nums text-gray-500">
            {fmtTime(currentGlobalTime)} / {fmtTime(totalDuration)}
          </span>
        </div>

        <button
          onClick={cycleRate}
          className="flex items-center gap-1 rounded bg-white/5 px-2 py-0.5 text-[10px] text-gray-400 hover:bg-white/10 hover:text-white"
          title="播放速度"
        >
          <Gauge size={12} />
          {playbackRate}x
        </button>
      </div>

      {/* Shot timeline */}
      <div className="border-b border-white/5 bg-surface-1">
        <ShotTimeline
          entries={entries}
          currentIndex={currentIndex}
          onSelect={(i) => {
            goTo(i);
            setPlaying(true);
          }}
        />
      </div>
    </div>
  );
}

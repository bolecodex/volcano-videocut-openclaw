import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { ImageLayer } from "./ImageLayer";
import { AudioSequence } from "./AudioSequence";
import { SubtitleOverlay } from "./SubtitleOverlay";
import type { Shot, SceneVideoProps } from "../types";

interface ShotSequenceProps {
  shot: Shot;
  enableKenBurns: boolean;
  enableSubtitles: boolean;
  subtitleStyle: SceneVideoProps["subtitleStyle"];
}

export const ShotSequence: React.FC<ShotSequenceProps> = ({
  shot,
  enableKenBurns,
  enableSubtitles,
  subtitleStyle,
}) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <ImageLayer src={shot.imageSrc} enableKenBurns={enableKenBurns} />

      <AudioSequence lines={shot.lines} fps={fps} />

      {enableSubtitles && (
        <SubtitleOverlay
          lines={shot.lines}
          fps={fps}
          style={subtitleStyle}
        />
      )}
    </AbsoluteFill>
  );
};

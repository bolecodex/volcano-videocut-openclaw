import React from "react";
import { Audio, Sequence, staticFile } from "remotion";
import type { Line } from "../types";

interface AudioSequenceProps {
  lines: Line[];
  fps: number;
}

/**
 * Lays out audio clips sequentially using Remotion Sequences.
 * Each line's audio starts after the previous one ends.
 */
export const AudioSequence: React.FC<AudioSequenceProps> = ({
  lines,
  fps,
}) => {
  let currentFrame = 0;

  return (
    <>
      {lines.map((line, i) => {
        const startFrame = currentFrame;
        const durationInFrames = Math.ceil(line.durationInSeconds * fps);
        currentFrame += durationInFrames;

        return (
          <Sequence
            key={`audio-${i}`}
            from={startFrame}
            durationInFrames={durationInFrames}
            layout="none"
          >
            <Audio src={staticFile(line.audioSrc)} volume={1} />
          </Sequence>
        );
      })}
    </>
  );
};

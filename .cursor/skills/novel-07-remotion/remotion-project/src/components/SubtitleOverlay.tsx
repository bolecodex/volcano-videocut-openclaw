import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  interpolate,
} from "remotion";
import type { Line, SceneVideoProps } from "../types";

interface SubtitleOverlayProps {
  lines: Line[];
  fps: number;
  style: SceneVideoProps["subtitleStyle"];
}

interface SingleSubtitleProps {
  line: Line;
  style: SceneVideoProps["subtitleStyle"];
  durationInFrames: number;
}

const FADE_FRAMES = 6;

const SingleSubtitle: React.FC<SingleSubtitleProps> = ({
  line,
  style,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  const fadeIn = interpolate(frame, [0, FADE_FRAMES], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const fadeOut = interpolate(
    frame,
    [durationInFrames - FADE_FRAMES, durationInFrames],
    [1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  const opacity = Math.min(fadeIn, fadeOut);

  const slideUp = interpolate(frame, [0, FADE_FRAMES], [8, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const positionStyles: React.CSSProperties =
    style.position === "top"
      ? { top: 80, left: 0, right: 0 }
      : style.position === "center"
        ? { top: "50%", left: 0, right: 0, transform: "translateY(-50%)" }
        : { bottom: 120, left: 0, right: 0 };

  return (
    <AbsoluteFill
      style={{
        justifyContent:
          style.position === "top"
            ? "flex-start"
            : style.position === "center"
              ? "center"
              : "flex-end",
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateY(${slideUp}px)`,
          position: "absolute",
          ...positionStyles,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "0 40px",
        }}
      >
        {line.speaker !== "旁白" && (
          <div
            style={{
              fontSize: style.fontSize * 0.65,
              fontFamily: style.fontFamily,
              color: "rgba(255, 255, 255, 0.7)",
              marginBottom: 6,
              textShadow: "0 1px 4px rgba(0,0,0,0.8)",
            }}
          >
            {line.speaker}
          </div>
        )}
        <div
          style={{
            fontSize: style.fontSize,
            fontFamily: style.fontFamily,
            color: style.color,
            backgroundColor: style.backgroundColor,
            padding: "12px 28px",
            borderRadius: 8,
            textAlign: "center",
            lineHeight: 1.5,
            maxWidth: "90%",
            textShadow: "0 2px 6px rgba(0,0,0,0.6)",
            letterSpacing: 1,
          }}
        >
          {line.text}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const SubtitleOverlay: React.FC<SubtitleOverlayProps> = ({
  lines,
  fps,
  style,
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
            key={`sub-${i}`}
            from={startFrame}
            durationInFrames={durationInFrames}
            layout="none"
          >
            <SingleSubtitle
              line={line}
              style={style}
              durationInFrames={durationInFrames}
            />
          </Sequence>
        );
      })}
    </>
  );
};

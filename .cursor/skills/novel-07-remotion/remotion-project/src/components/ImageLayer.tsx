import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Img,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  staticFile,
} from "remotion";

type KenBurnsDirection =
  | "zoom-in"
  | "zoom-out"
  | "pan-left"
  | "pan-right"
  | "pan-up";

interface ImageLayerProps {
  src: string;
  enableKenBurns: boolean;
}

/**
 * Deterministic pseudo-random from shot image src to pick a Ken Burns variant.
 */
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

const KB_DIRECTIONS: KenBurnsDirection[] = [
  "zoom-in",
  "zoom-out",
  "pan-left",
  "pan-right",
  "pan-up",
];

export const ImageLayer: React.FC<ImageLayerProps> = ({
  src,
  enableKenBurns,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const direction = useMemo<KenBurnsDirection>(() => {
    if (!enableKenBurns) return "zoom-in";
    return KB_DIRECTIONS[hashString(src) % KB_DIRECTIONS.length];
  }, [src, enableKenBurns]);

  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  let scale = 1;
  let translateX = 0;
  let translateY = 0;

  if (enableKenBurns) {
    switch (direction) {
      case "zoom-in":
        scale = 1 + progress * 0.12;
        break;
      case "zoom-out":
        scale = 1.12 - progress * 0.12;
        break;
      case "pan-left":
        scale = 1.08;
        translateX = progress * -3;
        break;
      case "pan-right":
        scale = 1.08;
        translateX = progress * 3;
        break;
      case "pan-up":
        scale = 1.08;
        translateY = progress * -3;
        break;
    }
  }

  return (
    <AbsoluteFill>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${translateX}%, ${translateY}%)`,
          transformOrigin: "center center",
        }}
      />
    </AbsoluteFill>
  );
};

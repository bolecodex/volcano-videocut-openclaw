import React from "react";
import {
  TransitionSeries,
  linearTiming,
  springTiming,
} from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { wipe } from "@remotion/transitions/wipe";
import { slide } from "@remotion/transitions/slide";
import { ShotSequence } from "../components/ShotSequence";
import type { SceneVideoProps, Shot } from "../types";

interface ShotSequenceWrapperProps {
  shot: Shot;
  enableKenBurns: boolean;
  enableSubtitles: boolean;
  subtitleStyle: SceneVideoProps["subtitleStyle"];
}

const ShotSeqWrapper: React.FC<ShotSequenceWrapperProps> = (props) => (
  <ShotSequence {...props} />
);

function buildFadeScene(
  shots: Shot[],
  durationInFrames: number,
  wrapperProps: Omit<ShotSequenceWrapperProps, "shot">
) {
  const timing = linearTiming({ durationInFrames });
  const elements: React.ReactNode[] = [];
  for (let i = 0; i < shots.length; i++) {
    elements.push(
      <TransitionSeries.Sequence
        key={shots[i].id}
        durationInFrames={shots[i].durationInFrames}
      >
        <ShotSeqWrapper shot={shots[i]} {...wrapperProps} />
      </TransitionSeries.Sequence>
    );
    if (i < shots.length - 1) {
      elements.push(
        <TransitionSeries.Transition
          key={`t-${shots[i].id}`}
          presentation={fade()}
          timing={timing}
        />
      );
    }
  }
  return <TransitionSeries>{elements}</TransitionSeries>;
}

function buildWipeScene(
  shots: Shot[],
  durationInFrames: number,
  wrapperProps: Omit<ShotSequenceWrapperProps, "shot">
) {
  const timing = linearTiming({ durationInFrames });
  const elements: React.ReactNode[] = [];
  for (let i = 0; i < shots.length; i++) {
    elements.push(
      <TransitionSeries.Sequence
        key={shots[i].id}
        durationInFrames={shots[i].durationInFrames}
      >
        <ShotSeqWrapper shot={shots[i]} {...wrapperProps} />
      </TransitionSeries.Sequence>
    );
    if (i < shots.length - 1) {
      elements.push(
        <TransitionSeries.Transition
          key={`t-${shots[i].id}`}
          presentation={wipe()}
          timing={timing}
        />
      );
    }
  }
  return <TransitionSeries>{elements}</TransitionSeries>;
}

function buildSlideScene(
  shots: Shot[],
  durationInFrames: number,
  wrapperProps: Omit<ShotSequenceWrapperProps, "shot">
) {
  const timing = springTiming({
    config: { damping: 200 },
    durationInFrames,
  });
  const elements: React.ReactNode[] = [];
  for (let i = 0; i < shots.length; i++) {
    elements.push(
      <TransitionSeries.Sequence
        key={shots[i].id}
        durationInFrames={shots[i].durationInFrames}
      >
        <ShotSeqWrapper shot={shots[i]} {...wrapperProps} />
      </TransitionSeries.Sequence>
    );
    if (i < shots.length - 1) {
      elements.push(
        <TransitionSeries.Transition
          key={`t-${shots[i].id}`}
          presentation={slide()}
          timing={timing}
        />
      );
    }
  }
  return <TransitionSeries>{elements}</TransitionSeries>;
}

export const SceneVideo: React.FC<SceneVideoProps> = ({
  shots,
  transitionDurationInFrames,
  transitionType,
  enableKenBurns,
  enableSubtitles,
  subtitleStyle,
}) => {
  if (shots.length === 0) {
    return null;
  }

  const wrapperProps = { enableKenBurns, enableSubtitles, subtitleStyle };

  if (transitionType === "none" || shots.length <= 1) {
    return (
      <TransitionSeries>
        {shots.map((shot) => (
          <TransitionSeries.Sequence
            key={shot.id}
            durationInFrames={shot.durationInFrames}
          >
            <ShotSeqWrapper shot={shot} {...wrapperProps} />
          </TransitionSeries.Sequence>
        ))}
      </TransitionSeries>
    );
  }

  switch (transitionType) {
    case "wipe":
      return buildWipeScene(shots, transitionDurationInFrames, wrapperProps);
    case "slide":
      return buildSlideScene(shots, transitionDurationInFrames, wrapperProps);
    case "fade":
    default:
      return buildFadeScene(shots, transitionDurationInFrames, wrapperProps);
  }
};

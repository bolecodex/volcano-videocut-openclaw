import React from "react";
import { Composition } from "remotion";
import { SceneVideo } from "./compositions/SceneVideo";
import { SceneVideoPropsSchema } from "./types";
import type { SceneVideoProps } from "./types";

const FPS = 30;

const defaultProps: SceneVideoProps = {
  sceneId: "SC_01",
  sceneName: "开篇旁白",
  shots: [
    {
      id: "SC_01_001",
      title: "当了十年班主任",
      shotType: "中景",
      imageSrc: "images/SC_01_001.png",
      lines: [
        {
          speaker: "旁白",
          text: "当了十年班主任，",
          audioSrc: "audio/SC_01_001_line_00.mp3",
          durationInSeconds: 2.0,
        },
        {
          speaker: "旁白",
          text: "被学生气到猝死那天……",
          audioSrc: "audio/SC_01_001_line_01.mp3",
          durationInSeconds: 2.5,
        },
      ],
      totalDurationInSeconds: 4.5,
      durationInFrames: 150,
      mood: "戏谑、悬念",
      lighting: "烛光/自然光",
    },
    {
      id: "SC_01_002",
      title: "穿进了宫斗剧",
      shotType: "中景",
      imageSrc: "images/SC_01_002.png",
      lines: [
        {
          speaker: "旁白",
          text: "我穿进了宫斗剧，",
          audioSrc: "audio/SC_01_002_line_00.mp3",
          durationInSeconds: 1.8,
        },
        {
          speaker: "旁白",
          text: "成了被打入冷宫的废妃。",
          audioSrc: "audio/SC_01_002_line_01.mp3",
          durationInSeconds: 2.2,
        },
      ],
      totalDurationInSeconds: 4.0,
      durationInFrames: 135,
      mood: "戏谑、悬念",
      lighting: "烛光/自然光",
    },
    {
      id: "SC_01_003",
      title: "萧凌狗脾气",
      shotType: "中景",
      imageSrc: "images/SC_01_003.png",
      lines: [
        {
          speaker: "旁白",
          text: "坏消息是，萧凌狗脾气，",
          audioSrc: "audio/SC_01_003_line_00.mp3",
          durationInSeconds: 2.0,
        },
        {
          speaker: "旁白",
          text: "贵妃想我死。",
          audioSrc: "audio/SC_01_003_line_01.mp3",
          durationInSeconds: 3.0,
        },
      ],
      totalDurationInSeconds: 5.0,
      durationInFrames: 165,
      mood: "戏谑、悬念",
      lighting: "烛光/自然光",
    },
  ],
  fps: FPS,
  width: 1080,
  height: 1920,
  transitionDurationInFrames: 15,
  transitionType: "fade",
  enableKenBurns: true,
  enableSubtitles: true,
  subtitleStyle: {
    fontSize: 42,
    fontFamily: "Noto Sans SC, sans-serif",
    color: "#FFFFFF",
    backgroundColor: "rgba(0, 0, 0, 0.6)",
    position: "bottom",
  },
};

function calculateTotalDuration(props: SceneVideoProps): number {
  const shotFrames = props.shots.reduce(
    (sum, s) => sum + s.durationInFrames,
    0
  );
  const transitionFrames =
    props.transitionType !== "none"
      ? Math.max(0, props.shots.length - 1) *
        props.transitionDurationInFrames
      : 0;
  return Math.max(1, shotFrames - transitionFrames);
}

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SceneVideo"
        component={SceneVideo}
        durationInFrames={150}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={defaultProps}
        schema={SceneVideoPropsSchema}
        calculateMetadata={({ props }) => {
          return {
            durationInFrames: calculateTotalDuration(props),
            fps: props.fps,
            width: props.width,
            height: props.height,
          };
        }}
      />
    </>
  );
};

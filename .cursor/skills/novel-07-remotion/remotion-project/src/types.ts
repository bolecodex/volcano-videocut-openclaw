import { z } from "zod";

export const LineSchema = z.object({
  speaker: z.string(),
  text: z.string(),
  emotion: z.string().optional(),
  audioSrc: z.string(),
  durationInSeconds: z.number(),
});

export const ShotSchema = z.object({
  id: z.string(),
  title: z.string(),
  shotType: z.string().optional(),
  imageSrc: z.string(),
  lines: z.array(LineSchema),
  totalDurationInSeconds: z.number(),
  durationInFrames: z.number(),
  mood: z.string().optional(),
  lighting: z.string().optional(),
});

export const SceneVideoPropsSchema = z.object({
  sceneId: z.string(),
  sceneName: z.string(),
  shots: z.array(ShotSchema),
  fps: z.number().default(30),
  width: z.number().default(1080),
  height: z.number().default(1920),
  transitionDurationInFrames: z.number().default(15),
  transitionType: z
    .enum(["fade", "wipe", "slide", "none"])
    .default("fade"),
  enableKenBurns: z.boolean().default(true),
  enableSubtitles: z.boolean().default(true),
  subtitleStyle: z
    .object({
      fontSize: z.number().default(42),
      fontFamily: z.string().default("Noto Sans SC, sans-serif"),
      color: z.string().default("#FFFFFF"),
      backgroundColor: z.string().default("rgba(0, 0, 0, 0.6)"),
      position: z.enum(["bottom", "center", "top"]).default("bottom"),
    })
    .default({}),
});

export type Line = z.infer<typeof LineSchema>;
export type Shot = z.infer<typeof ShotSchema>;
export type SceneVideoProps = z.infer<typeof SceneVideoPropsSchema>;

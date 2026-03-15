export interface ParamSchema {
  key: string;
  label: string;
  type: "select" | "text" | "number" | "toggle";
  options?: Array<{ value: string; label: string }>;
  default?: unknown;
}

export interface StepAction {
  id: string;
  label: string;
  variant: "primary" | "secondary" | "danger";
  requiresSelection?: boolean;
}

export interface StepDefinition {
  id: string;
  name: string;
  skill: string;
  order: number;
  dependsOn: string[];
  optional: boolean;
  parallelWith?: string[];
  actions: StepAction[];
  params: ParamSchema[];
  contentTab: string;
}

export const STEP_DEFINITIONS: StepDefinition[] = [
  {
    id: "extract-characters",
    name: "提取角色",
    skill: "novel-01-character-extractor",
    order: 1,
    dependsOn: [],
    optional: false,
    actions: [
      { id: "run", label: "提取全部角色", variant: "primary" },
      { id: "generate-images", label: "全部角色出图", variant: "secondary" },
      { id: "regenerate-one", label: "重新生图", variant: "secondary", requiresSelection: true },
    ],
    params: [
      {
        key: "image_model",
        label: "图片模型",
        type: "select",
        options: [
          { value: "seedream-5.0-lite", label: "Seedream 5.0 Lite" },
          { value: "seedream-4.5", label: "Seedream 4.5" },
          { value: "flux-2-flash", label: "Flux 2 Flash" },
          { value: "nano-banana-pro", label: "Nano Banana Pro" },
        ],
        default: "seedream-5.0-lite",
      },
      {
        key: "image_size",
        label: "图片尺寸",
        type: "select",
        options: [
          { value: "portrait_16_9", label: "竖版 16:9" },
          { value: "landscape_16_9", label: "横版 16:9" },
          { value: "square_1_1", label: "正方形 1:1" },
        ],
        default: "portrait_16_9",
      },
    ],
    contentTab: "characters",
  },
  {
    id: "script-to-scenes",
    name: "剧本转场景",
    skill: "novel-02-script-to-scenes",
    order: 2,
    dependsOn: [],
    optional: false,
    actions: [
      { id: "run", label: "切分场景", variant: "primary" },
    ],
    params: [
      {
        key: "line_max",
        label: "每行最大字数",
        type: "number",
        default: 15,
      },
    ],
    contentTab: "scenes",
  },
  {
    id: "scenes-to-storyboard",
    name: "场景转分镜",
    skill: "novel-03-scenes-to-storyboard",
    order: 3,
    dependsOn: ["script-to-scenes"],
    optional: false,
    actions: [
      { id: "run", label: "生成分镜", variant: "primary" },
    ],
    params: [
      {
        key: "shot_duration_min",
        label: "最短镜头(秒)",
        type: "number",
        default: 3,
      },
      {
        key: "shot_duration_max",
        label: "最长镜头(秒)",
        type: "number",
        default: 7,
      },
    ],
    contentTab: "shots",
  },
  {
    id: "shots-to-images",
    name: "分镜出图",
    skill: "novel-04-shots-to-images",
    order: 4,
    dependsOn: ["scenes-to-storyboard"],
    optional: false,
    parallelWith: ["shots-to-audio"],
    actions: [
      { id: "run-all", label: "全部出图", variant: "primary" },
      { id: "run-selected", label: "选中出图", variant: "secondary", requiresSelection: true },
      { id: "retry-failed", label: "重试失败", variant: "secondary" },
      { id: "reset-all", label: "重置全部图片", variant: "danger" },
    ],
    params: [
      {
        key: "image_model",
        label: "图片模型",
        type: "select",
        options: [
          { value: "seedream-5.0-lite", label: "Seedream 5.0 Lite" },
          { value: "seedream-4.5", label: "Seedream 4.5" },
          { value: "flux-2-flash", label: "Flux 2 Flash" },
        ],
        default: "seedream-5.0-lite",
      },
      {
        key: "use_character_ref",
        label: "使用角色参考图",
        type: "toggle",
        default: true,
      },
    ],
    contentTab: "images",
  },
  {
    id: "shots-to-audio",
    name: "分镜配音",
    skill: "novel-05-shots-to-audio",
    order: 5,
    dependsOn: ["scenes-to-storyboard"],
    optional: false,
    parallelWith: ["shots-to-images"],
    actions: [
      { id: "run-all", label: "全部配音", variant: "primary" },
      { id: "run-selected", label: "选中配音", variant: "secondary", requiresSelection: true },
      { id: "retry-failed", label: "重试失败", variant: "secondary" },
    ],
    params: [
      {
        key: "tts_model",
        label: "TTS 模型",
        type: "select",
        options: [
          { value: "speech-2.8-hd", label: "Minimax HD" },
          { value: "speech-2.6", label: "Minimax 标准" },
        ],
        default: "speech-2.8-hd",
      },
    ],
    contentTab: "audio",
  },
  {
    id: "shots-to-ai-video",
    name: "分镜AI视频",
    skill: "novel-06-shots-to-ai-video",
    order: 6,
    dependsOn: ["scenes-to-storyboard"],
    optional: true,
    actions: [
      { id: "run-all", label: "全部生成", variant: "primary" },
      { id: "run-selected", label: "选中生成", variant: "secondary", requiresSelection: true },
    ],
    params: [
      {
        key: "video_model",
        label: "视频模型",
        type: "select",
        options: [
          { value: "seedance-lite", label: "Seedance Lite" },
          { value: "seedance-2.0", label: "Seedance 2.0" },
        ],
        default: "seedance-lite",
      },
      {
        key: "video_duration",
        label: "视频时长(秒)",
        type: "number",
        default: 5,
      },
    ],
    contentTab: "video",
  },
  {
    id: "compose-video",
    name: "合成长视频",
    skill: "novel-07-remotion",
    order: 7,
    dependsOn: ["shots-to-images", "shots-to-audio"],
    optional: false,
    actions: [
      { id: "run", label: "合成视频", variant: "primary" },
    ],
    params: [
      {
        key: "transition",
        label: "转场效果",
        type: "select",
        options: [
          { value: "fade", label: "淡入淡出" },
          { value: "wipe", label: "擦除" },
          { value: "slide", label: "滑动" },
          { value: "none", label: "无" },
        ],
        default: "fade",
      },
      {
        key: "kenburns",
        label: "Ken Burns 效果",
        type: "toggle",
        default: true,
      },
      {
        key: "subtitles",
        label: "字幕叠加",
        type: "toggle",
        default: true,
      },
    ],
    contentTab: "video",
  },
];

export function getStepDefinition(stepId: string): StepDefinition | undefined {
  return STEP_DEFINITIONS.find((s) => s.id === stepId);
}

export function getStepByContentTab(tab: string): StepDefinition | undefined {
  return STEP_DEFINITIONS.find((s) => s.contentTab === tab);
}

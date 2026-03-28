import { createHash } from 'crypto';
import {
  getProject,
  saveScript,
  upsertStoryboard,
  listStoryboards,
  readStdin,
} from './state.js';

function stableId(project_id, name) {
  return createHash('sha1').update(`${project_id}:${name}`).digest('hex').slice(0, 36);
}

const input = JSON.parse(await readStdin());
const { project_id, storyboard_json } = input;

const normalizedStoryboards = typeof storyboard_json === 'string'
  ? JSON.parse(storyboard_json.replace(/\r\n/g, '\\n').replace(/[\r\n\t]/g, ' '))
  : storyboard_json;

if (!Array.isArray(normalizedStoryboards)) {
  throw new Error('storyboard_json must be an array');
}

function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function upsertStoryboardsIntoScript(existing, incoming) {
  const existingArr = Array.isArray(existing) ? existing : [];
  const byId = new Map();

  for (const s of existingArr) {
    const id = s?.storyboard_id;
    if (typeof id === 'string' && id) byId.set(id, s);
  }

  for (const s of incoming) {
    const id = s?.storyboard_id;
    if (typeof id === 'string' && id) byId.set(id, s);
  }

  const merged = Array.from(byId.values());
  merged.sort((a, b) => {
    const an = toNumber(a?.shot_number) ?? 0;
    const bn = toNumber(b?.shot_number) ?? 0;
    return an - bn;
  });
  return merged;
}

let storyboard_count = 0;
const storyboardsForScript = [];
for (const [index, shot] of normalizedStoryboards.entries()) {
  const shotNumber = Number.isFinite(shot.shot_number) ? shot.shot_number : index + 1;
  const id = shot.storyboard_id ?? stableId(project_id, `shot_${shotNumber}`);
  storyboardsForScript.push({
    ...shot,
    shot_number: shotNumber,
    storyboard_id: id,
  });
  upsertStoryboard({
    id,
    project_id,
    episode: 1,
    shot_index: shotNumber,
    description: shot.image_description ?? shot.visual_content ?? '',
    dialogue: shot.dialogue ?? '',
    speaker: null,
    dialogue_type: 'spoken',
    char_ids: shot.characters ?? [],
    scene_id: shot.scene ?? null,
    duration: shot.duration ?? null,
    framing: shot.framing ?? '',
    voiceover: shot.voiceover ?? null,
    visual_content: shot.visual_content ?? '',
    focus: shot.focus ?? '',
    generation_mode: shot.generation_mode ?? null,
    lighting: shot.lighting ?? '',
    action: shot.action ?? '',
    shot_type: shot.shot_type ?? '',
    color_tone: shot.color_tone ?? '',
    transition: shot.transition ?? null,
    camera_movement: shot.camera_movement ?? '',
    camera_angle: shot.camera_angle ?? '',
    notes: shot.notes ?? '',
    props: shot.props ?? [],
    image_description: shot.image_description ?? '',
    video_description: shot.video_description ?? '',
  });
  storyboard_count++;
}

const project = getProject(project_id);
if (project?.script) {
  const parsedScript = JSON.parse(project.script.replace(/\r\n/g, '\\n').replace(/[\r\n\t]/g, ' '));
  const mergedStoryboards = upsertStoryboardsIntoScript(parsedScript.storyboards, storyboardsForScript);
  const merged = { ...parsedScript, storyboards: mergedStoryboards };
  saveScript({
    project_id,
    title: project.name,
    style: project.style,
    style_prompt: project.style_prompt,
    script_json: JSON.stringify(merged),
  });
}

const storyboards = listStoryboards(project_id);

console.log(JSON.stringify({
  success: true,
  project_id,
  storyboard_count,
  storyboards,
}));

import { createHash } from 'crypto';
import {
  saveScript,
  upsertCharacter,
  upsertProp,
  upsertScene,
  listCharacters,
  listProps,
  listScenes,
  readStdin,
} from './state.js';

const STYLE_PROMPTS = {
  anime: 'anime style, vibrant colors, soft shading',
  realistic: 'realistic, photorealistic, cinematic lighting',
  comic: 'comic book style, bold lines, dynamic action',
  watercolor: 'watercolor painting, soft dreamy atmosphere',
  chinese: 'chinese ink painting style, traditional aesthetic',
};

function stableId(project_id, name) {
  return createHash('sha1').update(`${project_id}:${name}`).digest('hex').slice(0, 36);
}

function stripBom(text) {
  if (!text) return text;
  return text.charCodeAt(0) === 0xFEFF ? text.slice(1) : text;
}

function extractFirstJsonValue(text) {
  const s = stripBom(String(text ?? ''));
  let i = 0;
  while (i < s.length && /\s/.test(s[i])) i++;
  if (i >= s.length) return null;
  const start = i;
  const first = s[start];

  if (first !== '{' && first !== '[' && first !== '"') return null;

  let inString = false;
  let escaped = false;
  let depth = 0;

  for (; i < s.length; i++) {
    const ch = s[i];

    if (inString) {
      if (escaped) {
        escaped = false;
        continue;
      }
      if (ch === '\\') {
        escaped = true;
        continue;
      }
      if (ch === '"') {
        inString = false;
      }
      continue;
    }

    if (ch === '"') {
      inString = true;
      continue;
    }

    if (ch === '{' || ch === '[') {
      depth++;
      continue;
    }

    if (ch === '}' || ch === ']') {
      depth--;
      if (depth === 0) {
        return s.slice(start, i + 1);
      }
    }
  }

  return null;
}

function parseJsonInput(raw) {
  const text = stripBom(String(raw ?? ''));

  const tryParse = (value) => {
    try {
      return { ok: true, value: JSON.parse(value) };
    } catch (err) {
      return { ok: false, err };
    }
  };

  const direct = tryParse(text);
  if (direct.ok) return direct.value;

  const trimmed = tryParse(text.trim());
  if (trimmed.ok) return trimmed.value;

  const extracted = extractFirstJsonValue(text);
  if (extracted) {
    const recovered = tryParse(extracted);
    if (recovered.ok) {
      const rest = text.slice(text.indexOf(extracted) + extracted.length);
      if (rest.trim().length > 0) {
        process.stderr.write('警告: 检测到输入 JSON 后存在额外字符，已自动忽略。\n');
      }
      return recovered.value;
    }
  }

  throw direct.err;
}

const input = parseJsonInput(await readStdin());
const { project_id, script_json, style, style_prompt } = input;

if (!project_id) throw new Error('project_id is required');
if (script_json == null) throw new Error('script_json is required');

const normalizedScriptJson = typeof script_json === 'string'
  ? script_json.trim()
  : JSON.stringify(script_json);

const script = JSON.parse(normalizedScriptJson.replace(/\r\n/g, '\\n').replace(/[\r\n\t]/g, ' '));
const scriptInfo = script.script ?? {};
const assets = script.assets ?? {};

const title = scriptInfo.title ?? input.title ?? '未命名';
const finalStyle = style ?? scriptInfo.visual_style ?? 'anime';
const finalStylePrompt = style_prompt ?? scriptInfo.style_prompt ?? STYLE_PROMPTS[finalStyle] ?? STYLE_PROMPTS.anime;

saveScript({
  project_id,
  title,
  style: finalStyle,
  style_prompt: finalStylePrompt,
  script_json: JSON.stringify(script),
});

for (const char of assets.characters ?? []) {
  const id = char.character_id ?? stableId(project_id, char.name ?? '');
  upsertCharacter({
    id,
    project_id,
    name: char.name,
    description: char.description,
    voice: char.voice,
  });
}

for (const prop of assets.props ?? []) {
  const id = prop.prop_id ?? stableId(project_id, prop.name ?? '');
  upsertProp({
    id,
    project_id,
    name: prop.name,
    appearance: prop.appearance ?? '',
    description: prop.description,
    symbolism: prop.symbolism ?? '',
  });
}

for (const scene of assets.scenes ?? []) {
  const id = scene.scene_id ?? stableId(project_id, scene.name ?? '');
  upsertScene({
    id,
    project_id,
    name: scene.name,
    description: scene.description,
  });
}

const characters = listCharacters(project_id);
const props = listProps(project_id);
const scenes = listScenes(project_id);

process.stdout.write(JSON.stringify({
  success: true,
  project_id,
  style: finalStyle,
  style_prompt: finalStylePrompt,
  characters,
  props,
  scenes,
}));

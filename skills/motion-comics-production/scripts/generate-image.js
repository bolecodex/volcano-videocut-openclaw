/**
 * generate-image.js
 * Generates a character portrait, prop image, or scene background image.
 * Input (stdin): { type: "char"|"prop"|"scene", id, project_id }
 * Output (stdout): { id, name, image_url }
 */

import {
  getCharacter, setCharacterImage,
  getProp, setPropImage,
  getScene, setSceneImage,
  getProject,
  readStdin,
} from './state.js';
import fs from 'fs';
import path from 'path';
import { generateImage } from './jimeng.js';

const STYLE_PROMPTS = {
  anime: '动漫风格，色彩鲜艳，柔和阴影',
  realistic: '写实风格，照片级真实感，电影级光照',
  comic: '漫画书风格，粗线条，强动感',
  watercolor: '水彩画风格，柔和梦幻氛围',
  chinese: '中国水墨画风格，传统美学',
};

const input = JSON.parse(await readStdin());
const { type, id, project_id } = input;

const SAFETY_SUFFIX = '无暴力血腥画面, 无伤口流血, 无武器, 无仇恨符号, 无政治标识与口号, 无国旗国徽与制服标识, 无真实人物肖像, 无露骨或低俗内容';

function getStylePromptFromProjectScript(resolvedProjectId) {
  if (!resolvedProjectId) return null;
  const project = getProject(resolvedProjectId);
  if (!project?.script) return null;
  try {
    const parsed = JSON.parse(project.script);
    const visualStyle = parsed?.script?.visual_style;
    if (typeof visualStyle !== 'string') return null;
    return STYLE_PROMPTS[visualStyle] || visualStyle;
  } catch {
    return null;
  }
}

function ensureImagesDir(projectId) {
  const dir = path.join(process.cwd(), '.yiwa', projectId, 'images');
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function extractNumericSuffix(value) {
  const s = String(value ?? '');
  const m = s.match(/(\d+)(?!.*\d)/);
  if (!m) return null;
  return m[1].padStart(3, '0');
}

function sanitizeFileToken(value) {
  return String(value ?? '').replace(/[^a-zA-Z0-9_-]+/g, '_');
}

function inferExtFromUrl(url) {
  try {
    const u = new URL(url);
    const ext = path.extname(u.pathname);
    if (ext) return ext;
  } catch {
  }
  return '.jpeg';
}

async function downloadImage(url, outPath) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to download image: HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(outPath, buf);
}

let prompt, name;
let resolvedProjectId = project_id ?? null;
let baseDescription = '';
let suffix = '';

if (type === 'char') {
  const char = getCharacter(id, project_id);
  if (!char) throw new Error(`Character ${id} not found`);
  name = char.name;
  resolvedProjectId ||= char.project_id ?? null;
  baseDescription = char.description;
  suffix = '角色三视图设计稿, 前向/侧向/后向三栏并排放在同一张图上, 全身, 同一比例与站姿, 纯白背景, 细节清晰, 高质量, 无文字, 无水印';
} else if (type === 'prop') {
  const prop = getProp(id, project_id);
  if (!prop) throw new Error(`Prop ${id} not found`);
  name = prop.name;
  resolvedProjectId ||= prop.project_id ?? null;
  const appearance = prop.appearance ? `, ${prop.appearance}` : '';
  baseDescription = `${prop.description}${appearance}`;
  suffix = '道具三视图设计稿, 前向/侧向/后向三栏并排放在同一张图上, 同一比例, 干净纯白背景, 物体居中, 细节清晰, 高质量, 无文字, 无水印';
} else if (type === 'scene') {
  const scene = getScene(id, project_id);
  if (!scene) throw new Error(`Scene ${id} not found`);
  name = scene.name;
  resolvedProjectId ||= scene.project_id ?? null;
  baseDescription = scene.description;
  suffix = '场景背景图, 无人物, 电影感, 高质量';
} else {
  throw new Error(`type must be "char", "prop" or "scene", got: ${type}`);
}

const stylePrompt = getStylePromptFromProjectScript(resolvedProjectId) || STYLE_PROMPTS.anime;
prompt = `${baseDescription}, ${stylePrompt}, ${suffix}, ${SAFETY_SUFFIX}`;

const ratio = '16:9';
const image_url = await generateImage(prompt, { ratio, resolution: '2k' });

if (type === 'char') {
  setCharacterImage(id, image_url, resolvedProjectId);
} else if (type === 'prop') {
  setPropImage(id, image_url, resolvedProjectId);
} else {
  setSceneImage(id, image_url, resolvedProjectId);
}

if (resolvedProjectId) {
  const imagesDir = ensureImagesDir(resolvedProjectId);
  const prefix = type === 'char' ? 'character' : type === 'prop' ? 'prop' : 'scene';
  const num = extractNumericSuffix(id);
  const baseName = num ? `${prefix}_${num}` : `${prefix}_${sanitizeFileToken(id)}`;
  const outPath = path.join(imagesDir, `${baseName}${inferExtFromUrl(image_url)}`);
  await downloadImage(image_url, outPath);
}

console.log(JSON.stringify({ id, name, image_url, style_prompt: stylePrompt }));

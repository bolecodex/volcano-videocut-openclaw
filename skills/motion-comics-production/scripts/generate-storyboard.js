/**
 * generate-storyboard.js
 * Generates a storyboard frame image, using character/scene reference images if available.
 * Input (stdin): { storyboard_id, project_id }
 * Output (stdout): { storyboard_id, image_url, style_prompt }
 *
 * style can be:
 * - omitted: use project's style_prompt
 * - short name: anime/realistic/comic/watercolor/chinese
 * - full prompt: custom style description
 */

import {
  setStoryboardImage,
  listStoryboards,
  listCharacters, listScenes, listProps,
  getProject,
  readStdin,
} from './state.js';
import fs from 'fs';
import path from 'path';
import { generateImage, generateImageWithRef } from './jimeng.js';

const STYLE_PROMPTS = {
  anime: '动漫风格，色彩鲜艳，柔和阴影',
  realistic: '写实风格，照片级真实感，电影级光照',
  comic: '漫画书风格，粗线条，强动感',
  watercolor: '水彩画风格，柔和梦幻氛围',
  chinese: '中国水墨画风格，传统美学',
};

const input = JSON.parse(await readStdin());
const { storyboard_id, project_id } = input;

if (!project_id) throw new Error('project_id is required');

const storyboard = listStoryboards(project_id).find(s => s.id === storyboard_id);
if (!storyboard) throw new Error(`Storyboard ${storyboard_id} not found`);

// Determine style prompt
let stylePrompt = '动漫风格，色彩鲜艳，柔和阴影'; // default

const project = getProject(project_id);
if (project?.script) {
  try {
    const parsed = JSON.parse(project.script);
    const visualStyle = parsed?.script?.visual_style;
    if (typeof visualStyle === 'string' && visualStyle.trim()) {
      stylePrompt = STYLE_PROMPTS[visualStyle.trim()] || visualStyle.trim();
    }
  } catch {
  }
} else if (project?.style_prompt) {
  stylePrompt = project.style_prompt;
}

const refItems = [];

const charIds = storyboard.char_ids ?? [];
if (charIds.length > 0) {
  const allChars = listCharacters(project_id);
  for (const idOrName of charIds) {
    const char = allChars.find(c => c.id === idOrName || c.name === idOrName);
    if (char?.image_url) refItems.push({ url: char.image_url, label: `角色：${char.name}` });
  }
}

const propIds = storyboard.props ?? storyboard.prop_ids ?? [];
if (propIds.length > 0) {
  const allProps = listProps(project_id);
  for (const idOrName of propIds) {
    const prop = allProps.find(p => p.id === idOrName || p.name === idOrName);
    if (prop?.image_url) refItems.push({ url: prop.image_url, label: `道具：${prop.name}` });
  }
}

if (storyboard.scene_id) {
  const allScenes = listScenes(project_id);
  const scene = allScenes.find(s => s.id === storyboard.scene_id);
  if (scene?.image_url) refItems.push({ url: scene.image_url, label: `场景：${scene.name}` });
}

const baseDescription = storyboard.image_description || '';
const refHint = refItems.length > 0
  ? `，参考图含义：${refItems.map((r, idx) => `${idx + 1}.${r.label}`).join('；')}`
  : '';
const prompt = `${baseDescription}, ${stylePrompt}, 分镜画面, 电影级构图${refHint}`;
const refUrls = refItems.map(r => r.url);

function isSensitiveError(err) {
  const msg = String(err?.message ?? '');
  return msg.includes('OutputImageSensitiveContentDetected') || msg.includes('SensitiveContentDetected');
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

const safeSuffix = '画面中不要出现任何文字、标识、logo、水印、二维码、编号、印章文字；书页/布料上的文字用抽象纹理代替，避免生成可读内容；画面不含血腥暴力、不含武器与伤口流血；不出现政治标识、口号、旗帜徽记与敏感符号。';
const safePrompt = `${prompt}，${safeSuffix}`;

let image_url;
try {
  image_url = refUrls.length > 0
    ? await generateImageWithRef(safePrompt, refUrls)
    : await generateImage(safePrompt, { ratio: '16:9', resolution: '2k' });
} catch (err) {
  if (!isSensitiveError(err)) throw err;
  process.stderr.write(`Sensitive content detected for ${storyboard_id}, retrying without reference images...\n`);
  try {
    image_url = await generateImage(safePrompt, { ratio: '16:9', resolution: '2k' });
  } catch (err2) {
    if (!isSensitiveError(err2)) throw err2;
    const extraSafePrompt = `${safePrompt}，避免出现血迹、伤口、刑具与任何可读文字内容。`;
    image_url = await generateImage(extraSafePrompt, { ratio: '16:9', resolution: '2k' });
  }
}

setStoryboardImage(storyboard_id, image_url, project_id);

{
  const imagesDir = ensureImagesDir(project_id);
  const num = extractNumericSuffix(storyboard_id);
  const baseName = num ? `sb_${num}` : `sb_${sanitizeFileToken(storyboard_id)}`;
  const outPath = path.join(imagesDir, `${baseName}${inferExtFromUrl(image_url)}`);
  await downloadImage(image_url, outPath);
}

console.log(JSON.stringify({ storyboard_id, image_url, style_prompt: stylePrompt }));

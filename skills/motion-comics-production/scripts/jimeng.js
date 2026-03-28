/**
 * Jimeng (即梦) API client — Volcengine Ark
 * Docs: https://www.volcengine.com/docs/82379
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';

// Load .env from skills/motion-comics-production/ directory (parent of scripts/)
try {
  const envPath = resolve(import.meta.dirname, '../.env');
  const lines = readFileSync(envPath, 'utf8').split('\n');
  for (const line of lines) {
    const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (m && !process.env[m[1]]) {
      process.env[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
    }
  }
} catch { /* .env not found, fall back to process.env */ }

const BASE = 'https://ark.cn-beijing.volces.com/api/v3';
const TTS_BASE = 'https://openspeech.bytedance.com/api/v1/tts';
const IMAGE_MODEL = 'doubao-seedream-5-0-260128';
const VIDEO_MODEL = 'doubao-seedance-1-5-pro-251215';
const POLL_INTERVAL = 5000;
const POLL_TIMEOUT = 300_000;

const RATIO_SIZE = {
  '16:9': '2560x1440',
  '9:16': '1440x2560',
  '1:1':  '1920x1920',
  '4:3':  '2240x1680',
  '3:4':  '1680x2240',
};

function headers() {
  const key = process.env.ARK_API_KEY;
  if (!key) throw new Error('ARK_API_KEY 未设置。请在 skills/motion-comics-production/.env 中配置，或运行 /motion-comics-production:setup');
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` };
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST', headers: headers(), body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json();
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: headers() });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function generateImage(prompt, { ratio = '16:9' } = {}) {
  const data = await post('/images/generations', {
    model: IMAGE_MODEL,
    prompt,
    response_format: 'url',
    size: RATIO_SIZE[ratio] ?? '1280x720',
    sequential_image_generation: 'disabled',
  });
  const url = data?.data?.[0]?.url;
  if (!url) throw new Error(`No image URL in response: ${JSON.stringify(data)}`);
  return url;
}

export async function generateImageWithRef(prompt, refUrls, { ratio = '16:9' } = {}) {
  const data = await post('/images/generations', {
    model: IMAGE_MODEL,
    prompt,
    response_format: 'url',
    size: RATIO_SIZE[ratio] ?? '1280x720',
    image: refUrls,
  });
  const url = data?.data?.[0]?.url;
  if (!url) throw new Error(`No image URL in response: ${JSON.stringify(data)}`);
  return url;
}

export async function imageToVideo(imageUrl, { motionDesc = '' } = {}) {
  const submitData = await post('/contents/generations/tasks', {
    model: VIDEO_MODEL,
    content: [
      { type: 'image_url', image_url: { url: imageUrl } },
      { type: 'text', text: motionDesc || 'natural motion, cinematic' },
    ],
  });
  const taskId = submitData?.id;
  if (!taskId) throw new Error(`No task id in response: ${JSON.stringify(submitData)}`);

  const deadline = Date.now() + POLL_TIMEOUT;
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, POLL_INTERVAL));
    const pollData = await get(`/contents/generations/tasks/${taskId}`);
    const status = pollData?.status;
    if (status === 'succeeded') {
      const url = pollData?.content?.video_url;
      if (!url) throw new Error('No video_url in done response');
      return url;
    }
    if (status === 'failed') throw new Error('Video generation failed');
    process.stderr.write('.');
  }
  throw new Error('Video generation timed out after 5 minutes');
}

export async function textToSpeech(text, { voice = 'zh_female_shuangkuaisisi_moon_bigtts', speedRatio = 1.0 } = {}) {
  const appid = process.env.TTS_APPID;
  const token = process.env.TTS_TOKEN;
  const cluster = process.env.TTS_CLUSTER ?? 'volcano_tts';
  if (!appid || !token) throw new Error('TTS_APPID / TTS_TOKEN 未设置。请在 skills/motion-comics-production/.env 中配置');

  const body = {
    app: { appid, token, cluster },
    user: { uid: 'yiwa' },
    audio: { voice_type: voice, encoding: 'mp3', rate: 24000, speed_ratio: speedRatio },
    request: { reqid: randomUUID(), text, operation: 'query' },
  };
  const res = await fetch(TTS_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer;${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`TTS HTTP ${res.status}: ${await res.text()}`);
  const data = await res.json();
  if (data.code !== 3000) throw new Error(`TTS error ${data.code}: ${data.message}`);
  return Buffer.from(data.data, 'base64');
}

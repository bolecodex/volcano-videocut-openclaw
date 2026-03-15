#!/usr/bin/env node

import { createInterface } from 'readline';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
try {
  const envFile = readFileSync(resolve(__dirname, '..', '..', '.env'), 'utf-8');
  for (const line of envFile.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const [key, ...rest] = trimmed.split('=');
    const k = key.trim();
    if (k && !(k in process.env)) process.env[k] = rest.join('=').trim();
  }
} catch {}

const API_URL = process.env.XSKILL_MCP_URL || 'https://api.xskill.ai/api/v3/mcp-http';
const API_KEY = process.env.XSKILL_API_KEY || '';

const fullUrl = API_KEY ? `${API_URL}?api_key=${API_KEY}` : API_URL;

let sessionId = null;

const TOOLS = [
  {
    name: 'generate',
    description: '生成 AI 图片或视频。高频参数已提为一级字段，80% 场景只需 model + prompt 即可。',
    inputSchema: {
      type: 'object',
      properties: {
        model: { type: 'string', description: '模型 ID' },
        prompt: { type: 'string', description: '生成描述 / 提示词' },
        image_url: { type: 'string', description: '输入图片 URL' },
        image_size: { type: 'string', description: '图片尺寸' },
        aspect_ratio: { type: 'string', description: '宽高比' },
        duration: { type: 'string', description: '视频时长（秒）' },
        options: { type: 'object', description: '模型特有参数' },
      },
      required: ['model', 'prompt'],
    },
  },
  {
    name: 'get_result',
    description: '查询任务状态和结果。传入 task_id 查询单个任务；不传则返回最近任务列表。',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: { type: 'string', description: '任务 ID' },
        status: { type: 'string', enum: ['pending', 'processing', 'completed', 'failed', 'all'] },
        limit: { type: 'integer', description: '返回数量', default: 10 },
      },
    },
  },
  {
    name: 'speak',
    description: '语音合成和音色管理。支持 synthesize / list_voices / design_voice / clone_voice。',
    inputSchema: {
      type: 'object',
      properties: {
        action: { type: 'string', enum: ['synthesize', 'list_voices', 'design_voice', 'clone_voice'], default: 'synthesize' },
        text: { type: 'string', description: '合成文本' },
        voice_id: { type: 'string', description: '音色 ID' },
        prompt: { type: 'string', description: '音色描述' },
        audio_url: { type: 'string', description: '音频 URL' },
        model: { type: 'string', enum: ['speech-2.8-hd', 'speech-2.8-turbo'], default: 'speech-2.8-hd' },
        speed: { type: 'number', description: '语速 0.5-2.0', default: 1 },
      },
    },
  },
  {
    name: 'search_models',
    description: '搜索 AI 模型。支持文本搜索、类别筛选，或传入 model_id 获取完整参数 Schema。',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: '搜索关键词' },
        category: { type: 'string', enum: ['image', 'video', 'audio', 'all'] },
        capability: { type: 'string', enum: ['t2i', 'i2i', 't2v', 'i2v', 'v2v', 't2a', 'stt', 'i2t', 'v2t'] },
        model_id: { type: 'string', description: '精确模型 ID' },
      },
    },
  },
  {
    name: 'parse_video',
    description: '解析视频分享链接，获取无水印视频下载地址。',
    inputSchema: { type: 'object', properties: { url: { type: 'string' } }, required: ['url'] },
  },
  {
    name: 'transfer_url',
    description: '将外部 URL 转存到 CDN，返回稳定的访问链接。',
    inputSchema: {
      type: 'object',
      properties: {
        url: { type: 'string' },
        type: { type: 'string', enum: ['image', 'audio'], default: 'image' },
      },
      required: ['url'],
    },
  },
  {
    name: 'account',
    description: '账户管理：查询余额、签到、充值。',
    inputSchema: {
      type: 'object',
      properties: {
        action: { type: 'string', enum: ['balance', 'checkin', 'packages', 'pay'], default: 'balance' },
        package_id: { type: 'integer' },
      },
    },
  },
  {
    name: 'guide',
    description: '获取模型使用教程和最佳实践。',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string' },
        skill_id: { type: 'string' },
        category: { type: 'string', enum: ['image', 'video', 'audio', 'tool'] },
      },
    },
  },
];

async function mcpPost(method, params, id) {
  const headers = { 'Content-Type': 'application/json' };
  if (sessionId) headers['Mcp-Session-Id'] = sessionId;

  const isNotification = method.startsWith('notifications/');
  const payload = isNotification
    ? { jsonrpc: '2.0', method, params: params || {} }
    : { jsonrpc: '2.0', id: id ?? 1, method, params: params || {} };

  const res = await fetch(fullUrl, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });

  const newSession = res.headers.get('mcp-session-id');
  if (newSession) sessionId = newSession;

  if (isNotification) return null;

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  return res.json();
}

async function ensureSession() {
  if (sessionId) return;
  await mcpPost('initialize', {
    protocolVersion: '2024-11-05',
    capabilities: {},
    clientInfo: { name: 'xskill-proxy', version: '1.0.0' },
  }, 0);
  await mcpPost('notifications/initialized', {});
}

function respond(id, result) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
}

function respondError(id, code, message) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n');
}

let pending = 0;
let inputClosed = false;
function maybeExit() {
  if (inputClosed && pending === 0) process.exit(0);
}

const rl = createInterface({ input: process.stdin, terminal: false });

rl.on('line', async (line) => {
  let req;
  try { req = JSON.parse(line); } catch { return; }
  const { id, method, params } = req;
  if (method === 'notifications/initialized') return;

  pending++;
  try {
    if (method === 'initialize') {
      await ensureSession();
      respond(id, {
        protocolVersion: '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: 'xskill-ai-proxy', version: '1.0.0' },
      });
    } else if (method === 'tools/list') {
      respond(id, { tools: TOOLS });
    } else if (method === 'tools/call') {
      await ensureSession();
      const remote = await mcpPost('tools/call', params, id);
      if (remote.error) {
        respondError(id, remote.error.code || -1, remote.error.message);
      } else {
        respond(id, remote.result);
      }
    } else {
      respondError(id, -32601, `Method not found: ${method}`);
    }
  } catch (err) {
    respondError(id, -32000, err.message);
  } finally {
    pending--;
    maybeExit();
  }
});

rl.on('close', () => { inputClosed = true; maybeExit(); });

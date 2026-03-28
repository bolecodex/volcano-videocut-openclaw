/**
 * expand-script.js
 * Input (stdin): { idea, episodes? }
 * Output (stdout): { project_id, prompt }
 */

import { randomUUID } from 'crypto';
import { scriptwriterPrompt } from './prompt/scriptwriter_prompt.js';

const input = JSON.parse(await new Response(process.stdin).text());
const { idea } = input;

const project_id = randomUUID();

const prompt = `${scriptwriterPrompt.trim()}

请根据以下想法创作一个漫剧剧本。

故事想法：${idea}

只输出 JSON，不要其他文字。`;

console.log(JSON.stringify({ project_id, prompt }));

import { storyboardPrompt } from './prompt/storyboard_prompt.js';
import fs from 'fs';
import path from 'path';

const input = JSON.parse(await new Response(process.stdin).text());
const { project_id, script_json } = input;

let normalizedScript = null;
if (script_json != null) {
  normalizedScript = typeof script_json === 'string' ? script_json : JSON.stringify(script_json);
} else {
  if (!project_id) throw new Error('project_id is required when script_json is not provided');
  const scriptPath = path.join(process.cwd(), '.yiwa', project_id, 'script.json');
  if (!fs.existsSync(scriptPath)) throw new Error(`script.json not found: ${scriptPath}`);
  normalizedScript = fs.readFileSync(scriptPath, 'utf8');
}

const prompt = `${storyboardPrompt.trim()}

剧本JSON：${normalizedScript}

只输出分镜脚本 JSON，不要其他文字。`;

console.log(JSON.stringify({  prompt }));

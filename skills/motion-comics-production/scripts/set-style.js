/**
 * set-style.js
 * Updates the art style for a project.
 * Input (stdin): { project_id, style, style_prompt }
 * Output (stdout): { success, project_id, style, style_prompt }
 *
 * Available styles:
 * - anime: anime style, vibrant colors, soft shading
 * - realistic: realistic, photorealistic, cinematic lighting
 * - comic: comic book style, bold lines, dynamic action
 * - watercolor: watercolor painting, soft dreamy atmosphere
 * - chinese: chinese ink painting style, traditional aesthetic
 */

import { setProjectStyle, getProject } from './state.js';
import { readStdin } from './state.js';

const STYLE_PROMPTS = {
  anime: 'anime style, vibrant colors, soft shading',
  realistic: 'realistic, photorealistic, cinematic lighting',
  comic: 'comic book style, bold lines, dynamic action',
  watercolor: 'watercolor painting, soft dreamy atmosphere',
  chinese: 'chinese ink painting style, traditional aesthetic',
};

const input = JSON.parse(await readStdin());
const { project_id, style, style_prompt } = input;

const project = getProject(project_id);
if (!project) throw new Error(`Project ${project_id} not found`);

const finalStyle = style || project.style;
const finalStylePrompt = style_prompt || STYLE_PROMPTS[style] || project.style_prompt;

if (!finalStyle || !finalStylePrompt) {
  throw new Error('Please provide style and style_prompt, or use one of: anime, realistic, comic, watercolor, chinese');
}

setProjectStyle(project_id, finalStyle, finalStylePrompt);

console.log(JSON.stringify({
  success: true,
  project_id,
  style: finalStyle,
  style_prompt: finalStylePrompt,
}));
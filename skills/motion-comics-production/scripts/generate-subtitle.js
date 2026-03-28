/**
 * generate-subtitle.js
 * Generates an SRT subtitle file from all storyboard dialogues.
 * Uses actual audio/video duration for accurate timing alignment.
 * Input (stdin): { project_id }
 * Output (stdout): { project_id, srt_path, count }
 */

import fs from 'fs';
import path from 'path';
import { spawnSync } from 'child_process';
import { listStoryboards, readStdin } from './state.js';

const { project_id } = JSON.parse(await readStdin());

const storyboards = listStoryboards(project_id);

function toSrtTime(seconds) {
  const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  const ms = Math.floor((seconds % 1) * 1000).toString().padStart(3, '0');
  return `${h}:${m}:${s},${ms}`;
}

function ffprobeDuration(filePath) {
  const r = spawnSync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration',
    '-of', 'default=noprint_wrappers=1:nokey=1', filePath
  ], { stdio: ['ignore', 'pipe', 'pipe'] });
  if (r.status !== 0) return 5; // default fallback
  return parseFloat(r.stdout.toString().trim()) || 5;
}

let srt = '';
let index = 1;
let t = 0;
for (const shot of storyboards) {
  // Get actual duration - prefer merged_duration from compose-video.js
  let duration = 5; // default
  if (shot.merged_duration) {
    duration = shot.merged_duration;
  } else if (shot.local_audio_path && fs.existsSync(shot.local_audio_path)) {
    duration = ffprobeDuration(shot.local_audio_path);
  } else if (shot.local_video_path && fs.existsSync(shot.local_video_path)) {
    duration = ffprobeDuration(shot.local_video_path);
  }

  if (shot.dialogue) {
    srt += `${index}\n${toSrtTime(t)} --> ${toSrtTime(t + duration)}\n${shot.dialogue}\n\n`;
    index++;
  }
  t += duration;
}

const outputDir = path.join(process.cwd(), '.yiwa', project_id, 'output');
if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });
const srt_path = path.join(outputDir, `${project_id}.srt`);
fs.writeFileSync(srt_path, srt);

console.log(JSON.stringify({ project_id, srt_path, count: index - 1 }));

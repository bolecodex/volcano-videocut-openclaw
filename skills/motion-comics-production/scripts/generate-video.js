/**
 * generate-video.js
 * Converts a storyboard image to a 5-second video clip and saves it locally.
 * Input (stdin): { storyboard_id, project_id }
 * Output (stdout): { storyboard_id, video_url, local_path }
 */

import fs from 'fs';
import path from 'path';
import { listStoryboards, setStoryboardVideo, readStdin } from './state.js';
import { imageToVideo } from './jimeng.js';

const input = JSON.parse(await readStdin());
const { storyboard_id, project_id, motion_desc } = input;

if (!project_id) throw new Error('project_id is required');

const shot = listStoryboards(project_id).find(s => s.id === storyboard_id);
if (!shot) throw new Error(`Storyboard ${storyboard_id} not found`);
if (!shot.image_url) throw new Error('Storyboard has no image yet. Run generate-storyboard.js first.');

process.stderr.write(`Generating video for storyboard ${storyboard_id}...\n`);

const video_url = await imageToVideo(shot.image_url, {
  motionDesc: motion_desc ?? shot.video_description ?? shot.description,
  duration: 5,
  ratio: '16:9',
});

// Download video to .yiwa/videos/
const videoDir = path.join(process.cwd(), '.yiwa', project_id, 'videos');
if (!fs.existsSync(videoDir)) fs.mkdirSync(videoDir, { recursive: true });
const local_path = path.join(videoDir, `${storyboard_id}.mp4`);

const res = await fetch(video_url);
if (!res.ok) throw new Error(`Failed to download video: HTTP ${res.status}`);
const buf = Buffer.from(await res.arrayBuffer());
fs.writeFileSync(local_path, buf);

setStoryboardVideo(storyboard_id, video_url, local_path, project_id);

console.log(JSON.stringify({ storyboard_id, video_url, local_path }));

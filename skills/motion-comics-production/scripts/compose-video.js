/**
 * compose-video.js
 * Concatenates all storyboard video clips into a final video using ffmpeg.
 * Optionally merges per-shot audio and burns SRT subtitles.
 * Input (stdin): { project_id, clip_ids? }
 * Output (stdout): { success, output_path, clips }
 *
 * Requires: ffmpeg in PATH
 */

import fs from 'fs';
import path from 'path';
import { spawnSync } from 'child_process';
import { listStoryboards, setStoryboardMergedDuration, readStdin } from './state.js';

const input = JSON.parse(await readStdin());
const { project_id, clip_ids } = input;

let storyboards = listStoryboards(project_id).filter(s => s.local_video_path);

if (clip_ids && clip_ids.length > 0) {
  storyboards = clip_ids.map(id => storyboards.find(s => s.id === id)).filter(Boolean);
}

if (storyboards.length === 0) {
  throw new Error('No video clips found. Run generate-video.js for each storyboard first.');
}

const outputDir = path.join(process.cwd(), '.yiwa', project_id, 'output');
if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

function ffmpeg(args) {
  const r = spawnSync('ffmpeg', args, { stdio: ['ignore', 'pipe', 'pipe'] });
  if (r.status !== 0) throw new Error(`ffmpeg failed:\n${r.stderr?.toString()}`);
}

function ffprobeDuration(filePath) {
  const r = spawnSync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration',
    '-of', 'default=noprint_wrappers=1:nokey=1', filePath
  ], { stdio: ['ignore', 'pipe', 'pipe'] });
  if (r.status !== 0) return 0;
  return parseFloat(r.stdout.toString().trim()) || 0;
}

// Step 1: If any clip has audio, merge audio into each clip first
const hasAudio = storyboards.some(s => s.local_audio_path);
let clipsToConcat = storyboards.map(s => s.local_video_path);

if (hasAudio) {
  const mergedDir = path.join(process.cwd(), '.yiwa', project_id, 'merged');
  if (!fs.existsSync(mergedDir)) fs.mkdirSync(mergedDir, { recursive: true });

  clipsToConcat = storyboards.map(s => {
    const out = path.join(mergedDir, `${s.id}.mp4`);

    if (s.local_audio_path) {
      // Get durations
      const videoDur = ffprobeDuration(s.local_video_path);
      const audioDur = ffprobeDuration(s.local_audio_path);

      if (audioDur > videoDur) {
        // Audio is longer - extend video by freezing last frame to match audio duration
        ffmpeg(['-y', '-i', s.local_video_path, '-i', s.local_audio_path,
          '-filter_complex',
          `[0:v]tpad=stop_mode=clone:stop_duration=${audioDur}[v]`,
          '-map', '[v]', '-map', '1:a',
          '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac',
          '-shortest',
          out]);
        // Save merged duration for subtitle alignment
        setStoryboardMergedDuration(s.id, audioDur, project_id);
      } else {
        // Video is longer or equal - extend audio with silence to match video duration
        ffmpeg(['-y', '-i', s.local_video_path, '-i', s.local_audio_path,
          '-filter_complex',
          `[1:a]apad=whole_dur=${videoDur}[a]`,
          '-map', '0:v', '-map', '[a]',
          '-c:v', 'copy', '-c:a', 'aac',
          out]);
        // Save merged duration for subtitle alignment
        setStoryboardMergedDuration(s.id, videoDur, project_id);
      }
    } else {
      // No audio - add silent audio track
      ffmpeg(['-y', '-i', s.local_video_path,
        '-f', 'lavfi', '-i', 'anullsrc=channel_layout=mono:sample_rate=44100',
        '-c:v', 'copy', '-c:a', 'aac', '-shortest', out]);
      // Save merged duration for subtitle alignment
      setStoryboardMergedDuration(s.id, ffprobeDuration(s.local_video_path), project_id);
    }
    return out;
  });
}

// Step 2: Concatenate all clips
const listPath = path.join(outputDir, `${project_id}_list.txt`);
const concatPath = hasAudio
  ? path.join(outputDir, `${project_id}_concat.mp4`)
  : path.join(outputDir, `${project_id}.mp4`);

fs.writeFileSync(listPath, clipsToConcat.map(f => `file '${f}'`).join('\n'));
ffmpeg(['-y', '-f', 'concat', '-safe', '0', '-i', listPath,
  '-c', 'copy', concatPath]);

// Step 3: Burn subtitles if SRT exists
const srtPath = path.join(outputDir, `${project_id}.srt`);
const outputPath = path.join(outputDir, `${project_id}.mp4`);

if (fs.existsSync(srtPath) && concatPath !== outputPath) {
  ffmpeg(['-y', '-i', concatPath, '-vf', `subtitles=${srtPath}`, outputPath]);
  fs.unlinkSync(concatPath); // clean up intermediate file
} else if (concatPath !== outputPath) {
  fs.renameSync(concatPath, outputPath);
}

console.log(JSON.stringify({ success: true, output_path: outputPath, clips: storyboards.length }));

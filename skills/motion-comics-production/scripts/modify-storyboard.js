/**
 * modify-storyboard.js
 * Updates the description of a storyboard and clears its image/video.
 * Input (stdin): { storyboard_id, new_description }
 * Output (stdout): { storyboard_id, updated, note }
 */

import { getStoryboard, upsertStoryboard, setStoryboardImage, readStdin } from './state.js';

const input = JSON.parse(await readStdin());
const { storyboard_id, new_description } = input;

const shot = getStoryboard(storyboard_id);
if (!shot) throw new Error(`Storyboard ${storyboard_id} not found`);

// Update description and clear image/video by re-upserting then clearing image
upsertStoryboard({ ...shot, description: new_description });
// Clear image (which also clears video per state.js setStoryboardImage logic)
setStoryboardImage(storyboard_id, null, shot.project_id);

console.log(JSON.stringify({
  storyboard_id,
  updated: true,
  note: '描述已更新，图像已清空，请重新运行 generate-storyboard.js',
}));

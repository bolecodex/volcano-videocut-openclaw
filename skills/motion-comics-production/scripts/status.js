/**
 * status.js
 * Shows the current progress of a project.
 * Input (stdin): { project_id }
 * Output (stdout): { project_id, name, stage, characters, scenes, storyboards }
 */

import { getProject, listCharacters, listScenes, listStoryboards, readStdin } from './state.js';

const input = JSON.parse(await readStdin());
const { project_id } = input;

const project = getProject(project_id);
if (!project) throw new Error(`Project ${project_id} not found`);

const characters = listCharacters(project_id);
const scenes = listScenes(project_id);
const storyboards = listStoryboards(project_id);

const totalShots = storyboards.length;
const imagesGenerated = storyboards.filter(s => s.image_url).length;
const videosGenerated = storyboards.filter(s => s.video_url).length;

let stage = 'script';
if (characters.length > 0) stage = 'entities_extracted';
if (characters.some(c => c.image_url)) stage = 'images_generating';
if (totalShots > 0 && imagesGenerated === totalShots) stage = 'all_images_done';
if (videosGenerated > 0) stage = 'videos_generating';
if (totalShots > 0 && videosGenerated === totalShots) stage = 'ready_to_compose';

console.log(JSON.stringify({
  project_id,
  name: project.name,
  stage,
  characters: { total: characters.length, with_image: characters.filter(c => c.image_url).length, list: characters },
  scenes: { total: scenes.length, with_image: scenes.filter(s => s.image_url).length, list: scenes },
  storyboards: { total: totalShots, images: imagesGenerated, videos: videosGenerated, list: storyboards },
}));

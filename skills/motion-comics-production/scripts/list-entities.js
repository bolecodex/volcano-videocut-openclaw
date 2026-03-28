/**
 * list-entities.js
 * Lists all characters, scenes, and storyboards for a project.
 * Input (stdin): { project_id }
 * Output (stdout): { characters, scenes, storyboards }
 */

import { listCharacters, listScenes, listStoryboards, readStdin } from './state.js';

const input = JSON.parse(await readStdin());
const { project_id } = input;

const characters = listCharacters(project_id);
const scenes = listScenes(project_id);
const storyboards = listStoryboards(project_id);

console.log(JSON.stringify({ characters, scenes, storyboards }));

/**
 * JSON-based state management (replaces SQLite)
 * Data is stored in .yiwa/ relative to cwd (user's project)
 */

import fs from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';

const DATA_DIR = path.join(process.cwd(), '.yiwa');
const PROJECTS_TABLE = 'projects';

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function projectDir(project_id) {
  return path.join(DATA_DIR, project_id);
}

function ensureProjectDir(project_id) {
  ensureDir();
  const dir = projectDir(project_id);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function tablePath(name, project_id) {
  if (name === PROJECTS_TABLE) return path.join(DATA_DIR, `${PROJECTS_TABLE}.json`);
  if (!project_id) throw new Error(`project_id is required for table: ${name}`);
  return path.join(projectDir(project_id), `${name}.json`);
}

function legacyTablePath(name) {
  return path.join(DATA_DIR, `${name}.json`);
}

function loadTable(name, project_id) {
  const p = tablePath(name, project_id);
  if (!fs.existsSync(p)) return [];
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function loadProjectTable(name, project_id) {
  const p = tablePath(name, project_id);
  if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, 'utf8'));
  const legacyPath = legacyTablePath(name);
  if (!fs.existsSync(legacyPath)) return [];
  return JSON.parse(fs.readFileSync(legacyPath, 'utf8')).filter(r => r.project_id === project_id);
}

function saveTable(name, rows, project_id) {
  if (name === PROJECTS_TABLE) ensureDir();
  else ensureProjectDir(project_id);
  fs.writeFileSync(tablePath(name, project_id), JSON.stringify(rows, null, 2));
}

function scriptPath(project_id) {
  return path.join(projectDir(project_id), 'script.json');
}

function listProjectIds() {
  return loadTable(PROJECTS_TABLE).map(p => p.id).filter(Boolean);
}

function findInProjects(table, predicate) {
  for (const pid of listProjectIds()) {
    const rows = loadProjectTable(table, pid);
    const row = rows.find(predicate);
    if (row) return { project_id: pid, row, rows };
  }
  const legacyPath = legacyTablePath(table);
  if (fs.existsSync(legacyPath)) {
    const legacyRows = JSON.parse(fs.readFileSync(legacyPath, 'utf8'));
    const row = legacyRows.find(predicate);
    if (row?.project_id) return { project_id: row.project_id, row, rows: legacyRows };
  }
  return null;
}

// ── Projects ────────────────────────────────────────────────────────────────

export function createProject({ name, style = 'anime' }) {
  const id = randomUUID();
  ensureProjectDir(id);
  const projects = loadTable(PROJECTS_TABLE);
  projects.push({ id, name, style, style_prompt: null, script: null, script_path: 'script.json', created_at: new Date().toISOString() });
  saveTable(PROJECTS_TABLE, projects);
  return id;
}

export function saveScript({ project_id, title, style, style_prompt, script_json }) {
  ensureProjectDir(project_id);
  if (script_json != null) {
    fs.writeFileSync(scriptPath(project_id), script_json);
  }

  const projects = loadTable(PROJECTS_TABLE);
  const idx = projects.findIndex(p => p.id === project_id);
  if (idx === -1) {
    projects.push({
      id: project_id,
      name: title,
      style,
      style_prompt,
      script: null,
      script_path: 'script.json',
      created_at: new Date().toISOString(),
    });
  } else {
    projects[idx] = {
      ...projects[idx],
      name: title,
      style,
      style_prompt,
      script: null,
      script_path: 'script.json',
    };
  }
  saveTable(PROJECTS_TABLE, projects);
}

export function setProjectStyle(project_id, style, style_prompt) {
  const projects = loadTable(PROJECTS_TABLE);
  const idx = projects.findIndex(p => p.id === project_id);
  if (idx === -1) throw new Error(`Project ${project_id} not found`);
  projects[idx].style = style;
  projects[idx].style_prompt = style_prompt;
  saveTable(PROJECTS_TABLE, projects);
}

export function getProject(project_id) {
  const p = loadTable(PROJECTS_TABLE).find(r => r.id === project_id);
  if (!p) return null;
  const localScriptPath = scriptPath(project_id);
  const script = fs.existsSync(localScriptPath)
    ? fs.readFileSync(localScriptPath, 'utf8')
    : (p.script ?? null);
  return { ...p, script };
}

// ── Characters ───────────────────────────────────────────────────────────────

export function upsertCharacter({ id, project_id, name, description, voice }) {
  const rows = loadProjectTable('characters', project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx === -1) {
    rows.push({ id, project_id, name, description, voice, image_url: null });
  } else {
    rows[idx] = { ...rows[idx], name, description, voice };
  }
  saveTable('characters', rows, project_id);
}

export function setCharacterImage(id, image_url, project_id = null) {
  const resolved = project_id
    ? { project_id }
    : findInProjects('characters', r => r.id === id);
  if (!resolved?.project_id) return;
  const rows = loadProjectTable('characters', resolved.project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx !== -1) {
    rows[idx].image_url = image_url;
    saveTable('characters', rows, resolved.project_id);
  }
}

export function getCharacter(id, project_id = null) {
  if (project_id) return loadProjectTable('characters', project_id).find(r => r.id === id);
  return findInProjects('characters', r => r.id === id)?.row ?? null;
}

export function listCharacters(project_id) {
  return loadProjectTable('characters', project_id);
}

// ── Scenes ───────────────────────────────────────────────────────────────────

export function upsertScene({ id, project_id, name, description }) {
  const rows = loadProjectTable('scenes', project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx === -1) {
    rows.push({ id, project_id, name, description, image_url: null });
  } else {
    rows[idx] = { ...rows[idx], name, description };
  }
  saveTable('scenes', rows, project_id);
}

export function setSceneImage(id, image_url, project_id = null) {
  const resolved = project_id
    ? { project_id }
    : findInProjects('scenes', r => r.id === id);
  if (!resolved?.project_id) return;
  const rows = loadProjectTable('scenes', resolved.project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx !== -1) {
    rows[idx].image_url = image_url;
    saveTable('scenes', rows, resolved.project_id);
  }
}

export function getScene(id, project_id = null) {
  if (project_id) return loadProjectTable('scenes', project_id).find(r => r.id === id);
  return findInProjects('scenes', r => r.id === id)?.row ?? null;
}

export function listScenes(project_id) {
  return loadProjectTable('scenes', project_id);
}

// ── Props ────────────────────────────────────────────────────────────────────

export function upsertProp({ id, project_id, name, appearance = '', description, symbolism = '' }) {
  const rows = loadProjectTable('props', project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx === -1) {
    rows.push({ id, project_id, name, appearance, description, symbolism, image_url: null });
  } else {
    rows[idx] = { ...rows[idx], name, appearance, description, symbolism };
  }
  saveTable('props', rows, project_id);
}

export function setPropImage(id, image_url, project_id = null) {
  const resolved = project_id
    ? { project_id }
    : findInProjects('props', r => r.id === id);
  if (!resolved?.project_id) return;
  const rows = loadProjectTable('props', resolved.project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx !== -1) {
    rows[idx].image_url = image_url;
    saveTable('props', rows, resolved.project_id);
  }
}

export function getProp(id, project_id = null) {
  if (project_id) return loadProjectTable('props', project_id).find(r => r.id === id);
  return findInProjects('props', r => r.id === id)?.row ?? null;
}

export function listProps(project_id) {
  return loadProjectTable('props', project_id);
}

// ── Storyboards ───────────────────────────────────────────────────────────────

export function upsertStoryboard({
  id,
  project_id,
  episode = 1,
  shot_index = 0,
  description = '',
  dialogue = '',
  speaker = null,
  dialogue_type = 'spoken',
  char_ids = [],
  scene_id = null,
  duration = null,
  framing = '',
  voiceover = null,
  visual_content = '',
  focus = '',
  generation_mode = null,
  lighting = '',
  action = '',
  shot_type = '',
  color_tone = '',
  transition = null,
  camera_movement = '',
  camera_angle = '',
  notes = '',
  props = [],
  image_description = '',
  video_description = '',
} = {}) {
  const rows = loadProjectTable('storyboards', project_id);
  const idx = rows.findIndex(r => r.id === id);
  const base = idx === -1
    ? { image_url: null, video_url: null, local_audio_path: null }
    : rows[idx];
  const next = {
    ...base,
    id,
    project_id,
    episode,
    shot_index,
    description,
    dialogue,
    speaker,
    dialogue_type,
    char_ids,
    scene_id,
    duration,
    framing,
    voiceover,
    visual_content,
    focus,
    generation_mode,
    lighting,
    action,
    shot_type,
    color_tone,
    transition,
    camera_movement,
    camera_angle,
    notes,
    props,
    image_description,
    video_description,
  };
  if (idx === -1) {
    rows.push(next);
  } else {
    rows[idx] = next;
  }
  saveTable('storyboards', rows, project_id);
}

export function setStoryboardImage(id, image_url, project_id = null) {
  const resolved = project_id
    ? { project_id }
    : findInProjects('storyboards', r => r.id === id);
  if (!resolved?.project_id) return;
  const rows = loadProjectTable('storyboards', resolved.project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx !== -1) {
    rows[idx].image_url = image_url;
    rows[idx].video_url = null;
    saveTable('storyboards', rows, resolved.project_id);
  }
}

export function setStoryboardAudio(id, local_audio_path, project_id = null) {
  const resolved = project_id
    ? { project_id }
    : findInProjects('storyboards', r => r.id === id);
  if (!resolved?.project_id) return;
  const rows = loadProjectTable('storyboards', resolved.project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx !== -1) {
    rows[idx].local_audio_path = local_audio_path;
    saveTable('storyboards', rows, resolved.project_id);
  }
}

export function setStoryboardVideo(id, video_url, local_video_path, project_id = null) {
  const resolved = project_id
    ? { project_id }
    : findInProjects('storyboards', r => r.id === id);
  if (!resolved?.project_id) return;
  const rows = loadProjectTable('storyboards', resolved.project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx !== -1) {
    rows[idx].video_url = video_url;
    if (local_video_path) rows[idx].local_video_path = local_video_path;
    saveTable('storyboards', rows, resolved.project_id);
  }
}

export function setStoryboardMergedDuration(id, merged_duration, project_id = null) {
  const resolved = project_id
    ? { project_id }
    : findInProjects('storyboards', r => r.id === id);
  if (!resolved?.project_id) return;
  const rows = loadProjectTable('storyboards', resolved.project_id);
  const idx = rows.findIndex(r => r.id === id);
  if (idx !== -1) {
    rows[idx].merged_duration = merged_duration;
    saveTable('storyboards', rows, resolved.project_id);
  }
}

export function getStoryboard(id) {
  return findInProjects('storyboards', r => r.id === id)?.row ?? null;
}

export function listStoryboards(project_id) {
  return loadProjectTable('storyboards', project_id)
    .sort((a, b) => a.episode - b.episode || a.shot_index - b.shot_index);
}

// ── Shared utilities ──────────────────────────────────────────────────────────

export function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

import {
  readdirSync,
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  statSync,
  rmSync,
} from "fs";
import { join, extname, relative, basename, dirname } from "path";
import { homedir } from "os";
import YAML from "yaml";
import {
  getWorkspaceDirFromConfig,
  setWorkspaceDir as setWorkspaceDirConfig,
} from "./workspace-config.js";

function getDefaultWorkspaceDir(): string {
  return process.env.WORKSPACE_DIR || join(process.cwd(), "..", "..");
}

export function getWorkspaceDir(): string {
  const fromConfig = getWorkspaceDirFromConfig();
  if (fromConfig && existsSync(fromConfig)) return fromConfig;
  return getDefaultWorkspaceDir();
}

export function setWorkspaceDir(path: string): void {
  setWorkspaceDirConfig(path);
}

export interface FileEntry {
  name: string;
  path: string;
  type: "file" | "directory";
  size: number;
  mtime: string;
  extension?: string;
  children?: FileEntry[];
}

export interface ProjectInfo {
  name: string;
  path: string;
  hasStyle: boolean;
  hasCharacters: boolean;
  hasScenes: boolean;
  hasShots: boolean;
  hasImages: boolean;
  hasAudio: boolean;
  hasVideo: boolean;
  hasSource: boolean;
  mtime: string;
}

function isProject(dirPath: string): boolean {
  if (!existsSync(dirPath) || !statSync(dirPath).isDirectory()) return false;
  const files = readdirSync(dirPath);
  return (
    files.includes("style.yaml") ||
    files.some((f) => f.endsWith("_角色资产.yaml"))
  );
}

export function scanProjects(): ProjectInfo[] {
  const ws = getWorkspaceDir();
  if (!existsSync(ws)) return [];

  const entries = readdirSync(ws, { withFileTypes: true });
  const projects: ProjectInfo[] = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (entry.name.startsWith(".") || entry.name === "node_modules") continue;
    const dirPath = join(ws, entry.name);
    if (!isProject(dirPath)) continue;

    const files = readdirSync(dirPath);
    const stat = statSync(dirPath);
    projects.push({
      name: entry.name,
      path: dirPath,
      hasStyle: files.includes("style.yaml"),
      hasCharacters: files.some((f) => f.endsWith("_角色资产.yaml")),
      hasScenes:
        files.some((f) => f.endsWith("_场景索引.yaml")) ||
        existsSync(join(dirPath, "scenes")),
      hasShots: existsSync(join(dirPath, "shots")),
      hasImages: existsSync(join(dirPath, "images")),
      hasAudio: existsSync(join(dirPath, "audio")),
      hasVideo: existsSync(join(dirPath, "video")),
      hasSource: hasSourceFiles(dirPath),
      mtime: stat.mtime.toISOString(),
    });
  }
  return projects.sort(
    (a, b) => new Date(b.mtime).getTime() - new Date(a.mtime).getTime(),
  );
}

export function listDir(dirPath: string, recursive = false): FileEntry[] {
  if (!existsSync(dirPath) || !statSync(dirPath).isDirectory()) return [];

  const entries = readdirSync(dirPath, { withFileTypes: true });
  const result: FileEntry[] = [];

  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const fullPath = join(dirPath, entry.name);
    const stat = statSync(fullPath);
    const node: FileEntry = {
      name: entry.name,
      path: relative(getWorkspaceDir(), fullPath),
      type: entry.isDirectory() ? "directory" : "file",
      size: stat.size,
      mtime: stat.mtime.toISOString(),
    };
    if (entry.isFile()) {
      node.extension = extname(entry.name).slice(1);
    }
    if (entry.isDirectory() && recursive) {
      node.children = listDir(fullPath, true);
    }
    result.push(node);
  }

  return result.sort((a, b) => {
    if (a.type !== b.type) return a.type === "directory" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

export function readWorkspaceFile(filePath: string): {
  content: string;
  parsed?: unknown;
  mtime: string;
} {
  const abs = resolveWorkspacePath(filePath);
  if (!existsSync(abs)) throw new Error(`File not found: ${filePath}`);
  const content = readFileSync(abs, "utf-8");
  const stat = statSync(abs);
  const ext = extname(abs).toLowerCase();

  let parsed: unknown;
  if (ext === ".yaml" || ext === ".yml") {
    try {
      parsed = YAML.parse(content);
    } catch {}
  } else if (ext === ".json") {
    try {
      parsed = JSON.parse(content);
    } catch {}
  }

  return { content, parsed, mtime: stat.mtime.toISOString() };
}

export function writeWorkspaceFile(filePath: string, content: string): void {
  const abs = resolveWorkspacePath(filePath);
  mkdirSync(join(abs, ".."), { recursive: true });
  writeFileSync(abs, content, "utf-8");
}

export function createProject(name: string): ProjectInfo {
  const projectDir = join(getWorkspaceDir(), name);
  mkdirSync(projectDir, { recursive: true });

  const stylePath = join(projectDir, "style.yaml");
  if (!existsSync(stylePath)) {
    const defaultStyle = {
      style_base:
        "真人写实高清，超细节刻画，古风人像写实，光影细腻，氛围感拉满，服饰纹理清晰，面部神态精准",
      image_sizes: {
        storyboard: { preset: "portrait_16_9" },
      },
      video: {
        aspect_ratio: "9:16",
        resolution: "720p",
        duration_default: "5",
        fps: 24,
      },
    };
    writeFileSync(stylePath, YAML.stringify(defaultStyle), "utf-8");
  }

  return scanProjects().find((p) => p.name === name)!;
}

export function deleteProject(name: string): boolean {
  const projectDir = join(getWorkspaceDir(), name);
  if (!existsSync(projectDir) || !isProject(projectDir)) return false;
  rmSync(projectDir, { recursive: true });
  return true;
}

function resolveWorkspacePath(filePath: string): string {
  if (filePath.startsWith("/")) return filePath;
  return join(getWorkspaceDir(), filePath);
}

// --- Style ---

export function getStyle(projectName: string): Record<string, unknown> | null {
  const stylePath = join(getWorkspaceDir(), projectName, "style.yaml");
  if (!existsSync(stylePath)) return null;
  const content = readFileSync(stylePath, "utf-8");
  return YAML.parse(content) ?? null;
}

export function updateStyle(
  projectName: string,
  patch: Record<string, unknown>,
): void {
  const stylePath = join(getWorkspaceDir(), projectName, "style.yaml");
  let existing: Record<string, unknown> = {};
  if (existsSync(stylePath)) {
    existing = YAML.parse(readFileSync(stylePath, "utf-8")) ?? {};
  }
  const merged = deepMerge(existing, patch);
  writeFileSync(stylePath, YAML.stringify(merged, { lineWidth: 0 }), "utf-8");
}

// --- Structured data parsers ---

export function getCharacters(projectName: string): unknown[] {
  const projectDir = join(getWorkspaceDir(), projectName);
  if (!existsSync(projectDir)) return [];

  const files = readdirSync(projectDir);
  const charFile = files.find((f) => f.endsWith("_角色资产.yaml"));
  if (!charFile) return [];

  const content = readFileSync(join(projectDir, charFile), "utf-8");
  const data = YAML.parse(content);
  return data?.characters ?? [];
}

export function getScenes(projectName: string): {
  meta: unknown;
  scenes: unknown[];
} {
  const projectDir = join(getWorkspaceDir(), projectName);
  if (!existsSync(projectDir)) return { meta: null, scenes: [] };

  const files = readdirSync(projectDir);
  const indexFile = files.find((f) => f.endsWith("_场景索引.yaml"));

  let meta: unknown = null;
  let scenes: unknown[] = [];

  if (indexFile) {
    const content = readFileSync(join(projectDir, indexFile), "utf-8");
    const data = YAML.parse(content);
    meta = data?.meta ?? null;
    scenes = data?.scenes ?? [];
  }

  const scenesDir = join(projectDir, "scenes");
  if (existsSync(scenesDir)) {
    const sceneFiles = readdirSync(scenesDir).filter((f) => f.endsWith(".md"));
    for (const scene of scenes as Array<Record<string, unknown>>) {
      const matchFile = sceneFiles.find((f) =>
        f.startsWith(scene.id as string),
      );
      if (matchFile) {
        scene.content = readFileSync(join(scenesDir, matchFile), "utf-8");
        scene.fileName = matchFile;
      }
    }
  }

  return { meta, scenes };
}

export function getShots(projectName: string, sceneId?: string): {
  manifest: unknown;
  scenes: Array<{ sceneId: string; sceneName: string; shots: unknown[] }>;
} {
  const projectDir = join(getWorkspaceDir(), projectName);
  const shotsDir = join(projectDir, "shots");
  if (!existsSync(shotsDir)) return { manifest: null, scenes: [] };

  let manifest: unknown = null;
  const manifestPath = join(shotsDir, "_manifest.yaml");
  if (existsSync(manifestPath)) {
    manifest = YAML.parse(readFileSync(manifestPath, "utf-8"));
  }

  const yamlFiles = readdirSync(shotsDir).filter(
    (f) => f.endsWith(".yaml") && f !== "_manifest.yaml",
  );

  const scenes: Array<{
    sceneId: string;
    sceneName: string;
    shots: unknown[];
  }> = [];

  for (const file of yamlFiles) {
    try {
      const data = YAML.parse(readFileSync(join(shotsDir, file), "utf-8"));
      const sid = data?.scene_id as string | undefined;
      if (!sid) continue;
      if (sceneId && sid !== sceneId) continue;
      const rawShots = (data?.shots ?? []) as Record<string, unknown>[];
      const mapped = rawShots.map((s) => {
        const lines = (s.lines ?? s.dialogue ?? []) as Record<string, unknown>[];

        let audioUrl = s.audio_url as string | undefined;
        let audioPath = s.audio_path as string | undefined;
        let audioStatus = s.audio_status as string | undefined;
        let audioSpeaker = s.audio_speaker as string | undefined;

        if (!audioStatus || audioStatus === "pending") {
          const withAudio = lines.filter((l) => l.audio_status === "completed");
          if (withAudio.length > 0) {
            audioStatus = "completed";
            audioUrl = audioUrl ?? (withAudio[0].audio_url as string | undefined);
            audioPath = audioPath ?? (withAudio[0].audio_path as string | undefined);
            audioSpeaker = audioSpeaker ?? (withAudio[0].speaker as string | undefined);
          }
        }

        return {
          id: s.shot_id ?? s.id ?? "",
          title: s.title ?? (typeof s.content === "string" ? s.content.slice(0, 60).replace(/\n/g, " ") : s.shot_id ?? ""),
          shot_type: s.type ?? s.shot_type ?? "",
          characters: s.characters ?? [],
          mood: s.mood ?? "",
          lighting: s.lighting ?? "",
          lines,
          prompt: s.prompt ?? "",
          image_url: s.image_url ?? undefined,
          image_path: s.image_path ?? undefined,
          image_status: s.image_status ?? "pending",
          audio_url: audioUrl ?? undefined,
          audio_path: audioPath ?? undefined,
          audio_status: audioStatus ?? "pending",
          audio_speaker: audioSpeaker ?? undefined,
          duration_sec: s.duration ?? s.duration_sec ?? undefined,
        };
      });
      scenes.push({
        sceneId: sid,
        sceneName: data?.scene_name ?? basename(file, ".yaml"),
        shots: mapped,
      });
    } catch {
      // Skip malformed YAML files
    }
  }

  scenes.sort((a, b) => (a.sceneId ?? "").localeCompare(b.sceneId ?? ""));
  return { manifest, scenes };
}

export function getMedia(
  projectName: string,
  mediaType: "images" | "audio" | "video",
): Array<{ name: string; path: string; size: number; mtime: string }> {
  const mediaDir = join(getWorkspaceDir(), projectName, mediaType);
  if (!existsSync(mediaDir)) return [];

  return readdirSync(mediaDir)
    .filter((f) => !f.startsWith("."))
    .map((f) => {
      const fullPath = join(mediaDir, f);
      const stat = statSync(fullPath);
      return {
        name: f,
        path: `${projectName}/${mediaType}/${f}`,
        size: stat.size,
        mtime: stat.mtime.toISOString(),
      };
    })
    .sort(
      (a, b) => new Date(b.mtime).getTime() - new Date(a.mtime).getTime(),
    );
}

// --- Update functions (partial YAML merge) ---

export function updateCharacter(
  projectName: string,
  characterId: string,
  patch: Record<string, unknown>,
): boolean {
  const projectDir = join(getWorkspaceDir(), projectName);
  const files = readdirSync(projectDir);
  const charFile = files.find((f) => f.endsWith("_角色资产.yaml"));
  if (!charFile) return false;

  const filePath = join(projectDir, charFile);
  const data = YAML.parse(readFileSync(filePath, "utf-8"));
  if (!data?.characters) return false;

  const idx = data.characters.findIndex(
    (c: Record<string, unknown>) => c.id === characterId,
  );
  if (idx === -1) return false;

  data.characters[idx] = { ...data.characters[idx], ...patch };
  writeFileSync(filePath, YAML.stringify(data, { lineWidth: 0 }), "utf-8");
  return true;
}

export function updateScene(
  projectName: string,
  sceneId: string,
  patch: Record<string, unknown>,
): boolean {
  const projectDir = join(getWorkspaceDir(), projectName);
  const files = readdirSync(projectDir);
  const indexFile = files.find((f) => f.endsWith("_场景索引.yaml"));
  if (!indexFile) return false;

  const filePath = join(projectDir, indexFile);
  const data = YAML.parse(readFileSync(filePath, "utf-8"));
  if (!data?.scenes) return false;

  const idx = data.scenes.findIndex(
    (s: Record<string, unknown>) => s.id === sceneId,
  );
  if (idx === -1) return false;

  data.scenes[idx] = { ...data.scenes[idx], ...patch };
  writeFileSync(filePath, YAML.stringify(data, { lineWidth: 0 }), "utf-8");
  return true;
}

export function updateShot(
  projectName: string,
  sceneFileName: string,
  shotId: string,
  patch: Record<string, unknown>,
): boolean {
  const filePath = join(getWorkspaceDir(), projectName, "shots", sceneFileName);
  if (!existsSync(filePath)) return false;

  const data = YAML.parse(readFileSync(filePath, "utf-8"));
  if (!data?.shots) return false;

  const idx = data.shots.findIndex(
    (s: Record<string, unknown>) => s.id === shotId,
  );
  if (idx === -1) return false;

  data.shots[idx] = { ...data.shots[idx], ...patch };
  writeFileSync(filePath, YAML.stringify(data, { lineWidth: 0 }), "utf-8");
  return true;
}

// --- Directory browsing ---

export interface DirEntry {
  name: string;
  path: string;
}

export interface DirListing {
  current: string;
  parent: string | null;
  dirs: DirEntry[];
}

export function listDirs(targetPath?: string): DirListing {
  const resolved = targetPath || homedir();
  if (!existsSync(resolved) || !statSync(resolved).isDirectory()) {
    throw new Error(`Not a directory: ${resolved}`);
  }

  const parent = dirname(resolved);
  const dirs: DirEntry[] = [];

  try {
    const entries = readdirSync(resolved, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name.startsWith(".")) continue;
      dirs.push({
        name: entry.name,
        path: join(resolved, entry.name),
      });
    }
  } catch {
    // permission denied etc — return empty
  }

  dirs.sort((a, b) => a.name.localeCompare(b.name));

  return {
    current: resolved,
    parent: parent !== resolved ? parent : null,
    dirs,
  };
}

// --- Source / Novel ---

function hasSourceFiles(projectDir: string): boolean {
  const txtInRoot = readdirSync(projectDir).some(
    (f) => f.endsWith(".txt") && statSync(join(projectDir, f)).isFile(),
  );
  if (txtInRoot) return true;
  const sourceDir = join(projectDir, "source");
  return existsSync(sourceDir) && statSync(sourceDir).isDirectory();
}

export interface UploadResult {
  saved: string[];
  skipped: string[];
}

/**
 * Save uploaded novel files into the project root directory.
 * - .txt files are saved directly under {project}/
 * - Folders (represented as nested multer files with relative paths) are
 *   reconstructed under {project}/source/{folderName}/
 */
export function uploadNovelFiles(
  projectName: string,
  files: Array<{ originalname: string; buffer: Buffer }>,
  folderName?: string,
): UploadResult {
  const projectDir = join(getWorkspaceDir(), projectName);
  if (!existsSync(projectDir)) {
    throw new Error(`Project not found: ${projectName}`);
  }

  const saved: string[] = [];
  const skipped: string[] = [];

  for (const file of files) {
    const name = Buffer.from(file.originalname, "latin1").toString("utf8");
    const ext = extname(name).toLowerCase();

    if (ext !== ".txt") {
      skipped.push(name);
      continue;
    }

    let destPath: string;
    if (folderName) {
      const sourceDir = join(projectDir, "source", folderName);
      mkdirSync(sourceDir, { recursive: true });
      destPath = join(sourceDir, basename(name));
    } else {
      destPath = join(projectDir, basename(name));
    }

    writeFileSync(destPath, file.buffer);
    saved.push(relative(projectDir, destPath));
  }

  return { saved, skipped };
}

export function getSourceFiles(projectName: string): Array<{
  name: string;
  path: string;
  size: number;
  mtime: string;
}> {
  const projectDir = join(getWorkspaceDir(), projectName);
  if (!existsSync(projectDir)) return [];

  const result: Array<{
    name: string;
    path: string;
    size: number;
    mtime: string;
  }> = [];

  const rootFiles = readdirSync(projectDir).filter(
    (f) => f.endsWith(".txt") && statSync(join(projectDir, f)).isFile(),
  );
  for (const f of rootFiles) {
    const s = statSync(join(projectDir, f));
    result.push({
      name: f,
      path: `${projectName}/${f}`,
      size: s.size,
      mtime: s.mtime.toISOString(),
    });
  }

  const sourceDir = join(projectDir, "source");
  if (existsSync(sourceDir) && statSync(sourceDir).isDirectory()) {
    collectTxtFiles(sourceDir, projectName, "source", result);
  }

  return result.sort(
    (a, b) => new Date(b.mtime).getTime() - new Date(a.mtime).getTime(),
  );
}

function collectTxtFiles(
  dir: string,
  projectName: string,
  relPrefix: string,
  out: Array<{ name: string; path: string; size: number; mtime: string }>,
) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    const rel = `${relPrefix}/${entry.name}`;
    if (entry.isDirectory()) {
      collectTxtFiles(fullPath, projectName, rel, out);
    } else if (entry.name.endsWith(".txt")) {
      const s = statSync(fullPath);
      out.push({
        name: entry.name,
        path: `${projectName}/${rel}`,
        size: s.size,
        mtime: s.mtime.toISOString(),
      });
    }
  }
}

// --- Helpers ---

function deepMerge(
  target: Record<string, unknown>,
  source: Record<string, unknown>,
): Record<string, unknown> {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    const sv = source[key];
    const tv = target[key];
    if (
      sv &&
      typeof sv === "object" &&
      !Array.isArray(sv) &&
      tv &&
      typeof tv === "object" &&
      !Array.isArray(tv)
    ) {
      result[key] = deepMerge(
        tv as Record<string, unknown>,
        sv as Record<string, unknown>,
      );
    } else {
      result[key] = sv;
    }
  }
  return result;
}

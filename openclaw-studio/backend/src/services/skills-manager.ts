import { readdirSync, readFileSync, writeFileSync, mkdirSync, rmSync, existsSync, statSync } from "fs";
import { join, dirname } from "path";
import { homedir } from "os";
import { execSync } from "child_process";

function resolveOpenclawHome(): string {
  if (process.env.OPENCLAW_STATE_DIR) return process.env.OPENCLAW_STATE_DIR;
  const candidates = [
    join(process.cwd(), ".openclaw"),
    join(process.cwd(), "..", ".openclaw"),
    join(process.cwd(), "..", "..", ".openclaw"),
  ];
  const local = candidates.find((dir) => existsSync(dir));
  return local || join(homedir(), ".openclaw");
}

const OPENCLAW_HOME = resolveOpenclawHome();

const WORKSPACE_SKILLS = join(OPENCLAW_HOME, "workspace", "skills");
const MANAGED_SKILLS = join(OPENCLAW_HOME, "skills");
const BUNDLED_SKILLS = join(OPENCLAW_HOME, "bundled-skills");
const OPENCLAW_JSON = join(OPENCLAW_HOME, "openclaw.json");

function parseFrontmatter(content: string): { frontmatter: Record<string, unknown>; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { frontmatter: {}, body: content };
  const [, fm, body] = match;
  const frontmatter: Record<string, unknown> = {};
  for (const line of fm.split("\n")) {
    const colon = line.indexOf(":");
    if (colon > 0) {
      const key = line.slice(0, colon).trim();
      let val: unknown = line.slice(colon + 1).trim();
      const s = String(val);
      if (s.startsWith('"') && s.endsWith('"')) val = s.slice(1, -1);
      else if (s === "true") val = true;
      else if (s === "false") val = false;
      else if (/^\d+$/.test(s)) val = parseInt(s, 10);
      frontmatter[key] = val;
    }
  }
  return { frontmatter, body };
}

function readOpenclawJson(): Record<string, unknown> {
  if (!existsSync(OPENCLAW_JSON)) return {};
  try {
    return JSON.parse(readFileSync(OPENCLAW_JSON, "utf-8"));
  } catch {
    return {};
  }
}

function writeOpenclawJson(data: Record<string, unknown>) {
  mkdirSync(OPENCLAW_HOME, { recursive: true });
  writeFileSync(OPENCLAW_JSON, JSON.stringify(data, null, 2), "utf-8");
}

function scanDir(dir: string, source: "workspace" | "managed" | "bundled"): Array<Record<string, unknown>> {
  if (!existsSync(dir)) return [];
  const results: Array<Record<string, unknown>> = [];
  for (const name of readdirSync(dir, { withFileTypes: true })) {
    if (!name.isDirectory()) continue;
    const skillPath = join(dir, name.name);
    const skillMd = join(skillPath, "SKILL.md");
    if (!existsSync(skillMd)) continue;
    const raw = readFileSync(skillMd, "utf-8");
    const { frontmatter } = parseFrontmatter(raw);
    const config = readOpenclawJson();
    const entries = (config?.skills as Record<string, unknown>)?.entries as Record<string, unknown> ?? {};
    const skillConfig = entries[name.name] as Record<string, unknown> ?? {};
    const hasScripts = existsSync(join(skillPath, "scripts"));
    const hasReferences = existsSync(join(skillPath, "references"));
    const stat = existsSync(skillMd) ? statSync(skillMd) : null;
    results.push({
      name: name.name,
      displayName: frontmatter.displayName ?? frontmatter.name ?? name.name,
      description: frontmatter.description ?? "",
      version: frontmatter.version,
      source,
      path: skillPath,
      enabled: (skillConfig.enabled as boolean) ?? true,
      config: (skillConfig.env as Record<string, string>) ?? {},
      metadata: frontmatter,
      content: raw,
      hasScripts,
      hasReferences,
      updatedAt: stat?.mtime?.toISOString?.() ?? new Date().toISOString(),
      ...(frontmatter.pipeline_step ? { pipelineStep: frontmatter.pipeline_step } : {}),
      ...(frontmatter.pipeline_id ? { pipelineId: frontmatter.pipeline_id } : {}),
    });
  }
  return results;
}

export function scanSkills(): Array<Record<string, unknown>> {
  const workspace = scanDir(WORKSPACE_SKILLS, "workspace");
  const managed = scanDir(MANAGED_SKILLS, "managed");
  const bundled = scanDir(BUNDLED_SKILLS, "bundled");
  const bundledNames = new Set(bundled.map((b) => b.name as string));

  const seen = new Set<string>();
  const merged: Array<Record<string, unknown>> = [];

  for (const s of workspace) {
    const n = s.name as string;
    if (bundledNames.has(n)) {
      const orig = bundled.find((b) => b.name === n)!;
      s.source = "bundled";
      s.overridden = true;
      s.bundledPath = orig.path;
      if (!s.pipelineStep && orig.pipelineStep) s.pipelineStep = orig.pipelineStep;
      if (!s.pipelineId && orig.pipelineId) s.pipelineId = orig.pipelineId;
      if (!s.displayName || s.displayName === n) s.displayName = orig.displayName;
    }
    seen.add(n);
    merged.push(s);
  }

  for (const s of [...managed, ...bundled]) {
    const n = s.name as string;
    if (seen.has(n)) continue;
    seen.add(n);
    if (s.source === "bundled") s.overridden = false;
    merged.push(s);
  }

  return merged.sort((a, b) => ((a.name as string) ?? "").localeCompare((b.name as string) ?? ""));
}

export function getSkill(name: string): Record<string, unknown> | null {
  const bundledMd = join(BUNDLED_SKILLS, name, "SKILL.md");
  const isBundled = existsSync(bundledMd);
  let bundledFm: Record<string, unknown> | null = null;
  if (isBundled) {
    bundledFm = parseFrontmatter(readFileSync(bundledMd, "utf-8")).frontmatter;
  }

  for (const dir of [WORKSPACE_SKILLS, MANAGED_SKILLS, BUNDLED_SKILLS]) {
    const skillPath = join(dir, name);
    const skillMd = join(skillPath, "SKILL.md");
    if (!existsSync(skillMd)) continue;
    const raw = readFileSync(skillMd, "utf-8");
    const { frontmatter } = parseFrontmatter(raw);
    const config = readOpenclawJson();
    const entries = (config?.skills as Record<string, unknown>)?.entries as Record<string, unknown> ?? {};
    const skillConfig = entries[name] as Record<string, unknown> ?? {};
    const hasScripts = existsSync(join(skillPath, "scripts"));
    const hasReferences = existsSync(join(skillPath, "references"));
    const stat = statSync(skillMd);

    let source: string;
    let overridden = false;
    if (isBundled) {
      source = "bundled";
      overridden = dir === WORKSPACE_SKILLS;
    } else if (dir === WORKSPACE_SKILLS) {
      source = "workspace";
    } else if (dir === MANAGED_SKILLS) {
      source = "managed";
    } else {
      source = "bundled";
    }

    const pipelineStep = frontmatter.pipeline_step ?? bundledFm?.pipeline_step;
    const pipelineId = frontmatter.pipeline_id ?? bundledFm?.pipeline_id;

    return {
      name,
      displayName: frontmatter.displayName ?? bundledFm?.displayName ?? frontmatter.name ?? name,
      description: frontmatter.description ?? "",
      version: frontmatter.version,
      source,
      path: skillPath,
      enabled: (skillConfig.enabled as boolean) ?? true,
      config: (skillConfig.env as Record<string, string>) ?? {},
      metadata: frontmatter,
      content: raw,
      hasScripts,
      hasReferences,
      updatedAt: stat.mtime.toISOString(),
      overridden,
      ...(isBundled ? { bundledPath: join(BUNDLED_SKILLS, name) } : {}),
      ...(pipelineStep ? { pipelineStep } : {}),
      ...(pipelineId ? { pipelineId } : {}),
    };
  }
  return null;
}

export function createSkill(name: string, content: string): Record<string, unknown> {
  const skillPath = join(WORKSPACE_SKILLS, name);
  mkdirSync(skillPath, { recursive: true });
  const skillMd = join(skillPath, "SKILL.md");
  writeFileSync(skillMd, content, "utf-8");
  return getSkill(name)!;
}

export function updateSkill(name: string, content: string): Record<string, unknown> | null {
  if (existsSync(join(BUNDLED_SKILLS, name, "SKILL.md"))) {
    const overridePath = join(WORKSPACE_SKILLS, name);
    mkdirSync(overridePath, { recursive: true });
    writeFileSync(join(overridePath, "SKILL.md"), content, "utf-8");
    return getSkill(name);
  }
  for (const dir of [WORKSPACE_SKILLS, MANAGED_SKILLS]) {
    const skillMd = join(dir, name, "SKILL.md");
    if (existsSync(skillMd)) {
      writeFileSync(skillMd, content, "utf-8");
      return getSkill(name);
    }
  }
  return null;
}

export function deleteSkill(name: string): boolean {
  if (existsSync(join(BUNDLED_SKILLS, name, "SKILL.md"))) {
    throw new Error("系统技能不可删除");
  }
  for (const dir of [WORKSPACE_SKILLS, MANAGED_SKILLS]) {
    const skillPath = join(dir, name);
    if (existsSync(skillPath)) {
      rmSync(skillPath, { recursive: true });
      return true;
    }
  }
  return false;
}

export function resetSkill(name: string): boolean {
  if (!existsSync(join(BUNDLED_SKILLS, name, "SKILL.md"))) return false;
  const overridePath = join(WORKSPACE_SKILLS, name);
  if (existsSync(overridePath)) {
    rmSync(overridePath, { recursive: true });
  }
  return true;
}

export function updateConfig(name: string, config: { enabled?: boolean; env?: Record<string, string> }): void {
  const data = readOpenclawJson();
  const skills = (data.skills as Record<string, unknown>) ?? {};
  const entries = (skills.entries as Record<string, unknown>) ?? {};
  const current = (entries[name] as Record<string, unknown>) ?? {};
  if (config.enabled !== undefined) current.enabled = config.enabled;
  if (config.env !== undefined) current.env = config.env;
  entries[name] = current;
  skills.entries = entries;
  data.skills = skills;
  writeOpenclawJson(data);
}

export function installFromClawHub(slug: string): void {
  execSync(`clawhub install ${slug}`, {
    cwd: OPENCLAW_HOME,
    timeout: 60000,
    stdio: "inherit",
  });
}

export function installFromGithub(url: string): void {
  const tmpDir = join(OPENCLAW_HOME, ".tmp-install");
  mkdirSync(tmpDir, { recursive: true });
  try {
    execSync(`git clone --depth 1 ${url} repo`, {
      cwd: tmpDir,
      timeout: 60000,
    });
    const repoDir = join(tmpDir, "repo");
    const skillMd = join(repoDir, "SKILL.md");
    if (!existsSync(skillMd)) throw new Error("No SKILL.md in repository");
    const match = url.match(/\/([^/]+?)(?:\.git)?$/);
    const skillName = match?.[1] ?? "skill";
    const skillPath = join(WORKSPACE_SKILLS, skillName);
    mkdirSync(dirname(skillPath), { recursive: true });
    if (existsSync(skillPath)) rmSync(skillPath, { recursive: true });
    execSync(`cp -r "${repoDir}" "${skillPath}"`);
  } finally {
    rmSync(tmpDir, { recursive: true, force: true });
  }
}

export function publishSkill(name: string): void {
  const skillPath = join(WORKSPACE_SKILLS, name) || join(MANAGED_SKILLS, name);
  if (!existsSync(join(skillPath, "SKILL.md"))) throw new Error(`Skill ${name} not found`);
  execSync(`clawhub publish "${skillPath}"`, {
    timeout: 60000,
    stdio: "inherit",
  });
}

export function searchMarketplace(query: string): Array<Record<string, unknown>> {
  try {
    const raw = execSync(`clawhub search "${query.replace(/"/g, '\\"')}"`, {
      encoding: "utf-8",
      timeout: 15000,
    });
    const lines = raw.trim().split("\n").slice(1);
    const skills = scanSkills();
    const names = new Set(skills.map((s) => s.name));
    return lines.map((line: string) => {
      const parts = line.split(/\s{2,}/);
      const slug = parts[0] ?? "";
      const name = slug.split("/").pop() ?? slug;
      return {
        slug,
        name,
        description: parts[1] ?? "",
        version: parts[2] ?? "",
        author: parts[3] ?? "",
        downloads: parseInt(parts[4] ?? "0", 10) || 0,
        tags: [],
        installed: names.has(name),
      };
    });
  } catch {
    return [];
  }
}

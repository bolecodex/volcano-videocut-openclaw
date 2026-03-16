const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const BUILTIN_SKILLS = new Set(['video-analyzer', 'ffmpeg-cutter']);

class SkillsManager {
  constructor(skillsDir) {
    this.skillsDir = skillsDir;
  }

  listSkills() {
    if (!fs.existsSync(this.skillsDir)) return [];

    const entries = fs.readdirSync(this.skillsDir, { withFileTypes: true });
    const skills = [];

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const skillPath = path.join(this.skillsDir, entry.name);
      const skillMd = path.join(skillPath, 'SKILL.md');
      if (!fs.existsSync(skillMd)) continue;

      const meta = this._parseFrontmatter(skillMd);
      skills.push({
        id: entry.name,
        name: meta.name || entry.name,
        description: meta.description || '',
        version: meta.version || '',
        trigger: meta.trigger || '',
        builtin: BUILTIN_SKILLS.has(entry.name),
        path: skillPath,
      });
    }

    return skills.sort((a, b) => {
      if (a.builtin !== b.builtin) return a.builtin ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
  }

  getSkillDetail(skillName) {
    const skillPath = path.join(this.skillsDir, skillName);
    const skillMd = path.join(skillPath, 'SKILL.md');
    if (!fs.existsSync(skillMd)) return null;

    const content = fs.readFileSync(skillMd, 'utf-8');
    const meta = this._parseFrontmatter(skillMd);
    const body = this._extractBody(content);

    const files = this._listSkillFiles(skillPath, skillPath);

    return {
      id: skillName,
      name: meta.name || skillName,
      description: meta.description || '',
      version: meta.version || '',
      trigger: meta.trigger || '',
      metadata: meta.metadata || null,
      builtin: BUILTIN_SKILLS.has(skillName),
      content: body,
      rawContent: content,
      files,
    };
  }

  importSkill(sourcePath) {
    if (!fs.existsSync(sourcePath)) {
      throw new Error(`Source path does not exist: ${sourcePath}`);
    }

    const skillMd = path.join(sourcePath, 'SKILL.md');
    if (!fs.existsSync(skillMd)) {
      throw new Error('Invalid skill: SKILL.md not found in the selected directory');
    }

    const skillName = path.basename(sourcePath);
    const targetPath = path.join(this.skillsDir, skillName);

    if (fs.existsSync(targetPath)) {
      throw new Error(`Skill "${skillName}" already exists. Delete it first to reimport.`);
    }

    this._copyDirRecursive(sourcePath, targetPath);

    return {
      id: skillName,
      name: skillName,
      path: targetPath,
    };
  }

  deleteSkill(skillName) {
    if (BUILTIN_SKILLS.has(skillName)) {
      throw new Error(`Cannot delete built-in skill: ${skillName}`);
    }

    const skillPath = path.join(this.skillsDir, skillName);
    if (!fs.existsSync(skillPath)) {
      throw new Error(`Skill not found: ${skillName}`);
    }

    fs.rmSync(skillPath, { recursive: true, force: true });
    return true;
  }

  _parseFrontmatter(filePath) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const match = content.match(/^---\n([\s\S]*?)\n---/);
    if (!match) return {};

    try {
      return yaml.load(match[1]) || {};
    } catch {
      return {};
    }
  }

  _extractBody(content) {
    const match = content.match(/^---\n[\s\S]*?\n---\n?([\s\S]*)$/);
    return match ? match[1].trim() : content;
  }

  _listSkillFiles(dir, rootDir) {
    const results = [];
    if (!fs.existsSync(dir)) return results;

    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relPath = path.relative(rootDir, fullPath);

      if (entry.isDirectory()) {
        results.push(...this._listSkillFiles(fullPath, rootDir));
      } else {
        results.push(relPath);
      }
    }
    return results;
  }

  _copyDirRecursive(src, dest) {
    fs.mkdirSync(dest, { recursive: true });
    const entries = fs.readdirSync(src, { withFileTypes: true });

    for (const entry of entries) {
      const srcPath = path.join(src, entry.name);
      const destPath = path.join(dest, entry.name);

      if (entry.isDirectory()) {
        this._copyDirRecursive(srcPath, destPath);
      } else {
        fs.copyFileSync(srcPath, destPath);
      }
    }
  }
}

module.exports = { SkillsManager, BUILTIN_SKILLS };

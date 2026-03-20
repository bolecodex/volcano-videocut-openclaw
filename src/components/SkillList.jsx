import React, { useState, useEffect, useCallback } from 'react';

const TABS = [
  { id: 'system', label: '系统' },
  { id: 'imported', label: '已导入' },
  { id: 'all', label: '全部' },
];

function SkillList({ collapsed, onToggle, onSelectSkill, selectedSkill }) {
  const api = window.electronAPI;
  const [skills, setSkills] = useState([]);
  const [tab, setTab] = useState('all');
  const [search, setSearch] = useState('');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [importMode, setImportMode] = useState('local'); // 'local' | 'url'
  const [importUrl, setImportUrl] = useState('');
  const [createForm, setCreateForm] = useState({
    skillId: '',
    name: '',
    description: '',
    trigger: '',
    tags: '',
    icon: '🔧',
    content: '',
  });

  const loadSkills = useCallback(async () => {
    if (!api) return;
    const list = await api.listSkills();
    setSkills(list || []);
  }, [api]);

  useEffect(() => { loadSkills(); }, [loadSkills]);

  const handleImportLocal = async () => {
    if (!api) return;
    const result = await api.importSkill();
    if (result?.success) {
      loadSkills();
      setShowImportDialog(false);
    } else if (result?.error) {
      alert(`导入失败: ${result.error}`);
    }
  };

  const handleImportFromUrl = async () => {
    if (!api || !importUrl.trim()) return;
    const result = await api.importSkillFromUrl(importUrl.trim());
    if (result?.success) {
      loadSkills();
      setShowImportDialog(false);
      setImportUrl('');
    } else if (result?.error) {
      alert(`导入失败: ${result.error}`);
    }
  };

  const handleCreateSkill = async () => {
    if (!api || !createForm.skillId || !createForm.name) {
      alert('请填写技能 ID 和名称');
      return;
    }
    const tags = createForm.tags.split(',').map(t => t.trim()).filter(Boolean);
    const result = await api.createSkill({
      skillId: createForm.skillId,
      name: createForm.name,
      description: createForm.description,
      trigger: createForm.trigger,
      tags,
      icon: createForm.icon,
      content: createForm.content || `# ${createForm.name}\n\n${createForm.description || ''}`,
    });
    if (result?.success) {
      loadSkills();
      setShowCreateDialog(false);
      setCreateForm({ skillId: '', name: '', description: '', trigger: '', tags: '', icon: '🔧', content: '' });
    } else if (result?.error) {
      alert(`创建失败: ${result.error}`);
    }
  };

  const filtered = skills.filter((s) => {
    if (tab === 'system' && !s.builtin) return false;
    if (tab === 'imported' && s.builtin) return false;
    if (search) {
      const q = search.toLowerCase();
      return s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q);
    }
    return true;
  });

  if (collapsed) {
    return (
      <div className="skills-collapsed" onClick={onToggle}>
        <span className="skills-collapsed-icon">🧩</span>
        <span className="skills-collapsed-label">Skills</span>
      </div>
    );
  }

  return (
    <div className="skills-sidebar">
      <div className="skills-header">
        <span className="skills-title">Skills</span>
        <button className="btn-icon" onClick={onToggle} title="收起">✕</button>
      </div>

      <div className="skills-search">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索 Skill..."
          className="skills-search-input"
        />
      </div>

      <div className="skills-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`skills-tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="skills-list">
        {filtered.length === 0 && (
          <div className="skills-empty">
            {search ? '没有匹配的 Skill' : '暂无 Skill'}
          </div>
        )}
        {filtered.map((skill) => (
          <div
            key={skill.id}
            className={`skill-card ${selectedSkill === skill.id ? 'active' : ''}`}
            onClick={() => onSelectSkill(skill.id)}
          >
            <div className="skill-card-header">
              <span className={`skill-dot ${skill.builtin ? 'builtin' : 'imported'}`} />
              <span className="skill-card-name">{skill.name}</span>
              {skill.builtin && <span className="skill-badge">系统</span>}
            </div>
            <div className="skill-card-desc">{skill.description?.slice(0, 80)}{skill.description?.length > 80 ? '...' : ''}</div>
          </div>
        ))}
      </div>

      <div className="skills-footer">
        <button className="btn btn-primary skills-create-btn" onClick={() => setShowCreateDialog(true)}>
          + 创建 Skill
        </button>
        <button className="btn btn-secondary skills-import-btn" onClick={() => setShowImportDialog(true)}>
          📥 导入 Skill
        </button>
      </div>

      {showCreateDialog && (
        <div className="skill-dialog-overlay" onClick={() => setShowCreateDialog(false)}>
          <div className="skill-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="skill-dialog-header">
              <h3>创建新技能</h3>
              <button className="btn-icon" onClick={() => setShowCreateDialog(false)}>✕</button>
            </div>
            <div className="skill-dialog-body">
              <label className="skill-form-label">
                <span>技能 ID <em>（英文，用于文件夹名）</em></span>
                <input
                  type="text"
                  className="input"
                  value={createForm.skillId}
                  onChange={(e) => setCreateForm((f) => ({ ...f, skillId: e.target.value.toLowerCase().replace(/\s+/g, '-') }))}
                  placeholder="my-custom-skill"
                />
              </label>
              <label className="skill-form-label">
                <span>技能名称 <em>（必填）</em></span>
                <input
                  type="text"
                  className="input"
                  value={createForm.name}
                  onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="我的自定义技能"
                />
              </label>
              <label className="skill-form-label">
                <span>描述</span>
                <textarea
                  className="input"
                  rows={2}
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="技能功能描述"
                />
              </label>
              <label className="skill-form-label">
                <span>触发词 <em>（逗号分隔）</em></span>
                <input
                  type="text"
                  className="input"
                  value={createForm.trigger}
                  onChange={(e) => setCreateForm((f) => ({ ...f, trigger: e.target.value }))}
                  placeholder="关键词1, 关键词2"
                />
              </label>
              <label className="skill-form-label">
                <span>标签 <em>（逗号分隔）</em></span>
                <input
                  type="text"
                  className="input"
                  value={createForm.tags}
                  onChange={(e) => setCreateForm((f) => ({ ...f, tags: e.target.value }))}
                  placeholder="tag1, tag2"
                />
              </label>
              <label className="skill-form-label">
                <span>图标</span>
                <input
                  type="text"
                  className="input"
                  value={createForm.icon}
                  onChange={(e) => setCreateForm((f) => ({ ...f, icon: e.target.value }))}
                  placeholder="🔧"
                />
              </label>
              <label className="skill-form-label">
                <span>详细内容 <em>（Markdown，可选）</em></span>
                <textarea
                  className="input"
                  rows={6}
                  value={createForm.content}
                  onChange={(e) => setCreateForm((f) => ({ ...f, content: e.target.value }))}
                  placeholder="# 技能名称\n\n## 功能\n\n..."
                />
              </label>
            </div>
            <div className="skill-dialog-footer">
              <button className="btn btn-secondary" onClick={() => setShowCreateDialog(false)}>取消</button>
              <button className="btn btn-primary" onClick={handleCreateSkill}>创建</button>
            </div>
          </div>
        </div>
      )}

      {showImportDialog && (
        <div className="skill-dialog-overlay" onClick={() => setShowImportDialog(false)}>
          <div className="skill-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="skill-dialog-header">
              <h3>导入技能</h3>
              <button className="btn-icon" onClick={() => setShowImportDialog(false)}>✕</button>
            </div>
            <div className="skill-dialog-body">
              <div className="skill-import-tabs">
                <button
                  className={`skill-import-tab ${importMode === 'local' ? 'active' : ''}`}
                  onClick={() => setImportMode('local')}
                >
                  从本地文件夹
                </button>
                <button
                  className={`skill-import-tab ${importMode === 'url' ? 'active' : ''}`}
                  onClick={() => setImportMode('url')}
                >
                  从 URL / GitHub
                </button>
              </div>
              {importMode === 'local' ? (
                <div className="skill-import-local">
                  <p>选择包含 SKILL.md 的文件夹</p>
                  <button className="btn btn-primary" onClick={handleImportLocal}>
                    选择文件夹
                  </button>
                </div>
              ) : (
                <div className="skill-import-url">
                  <label className="skill-form-label">
                    <span>URL <em>（GitHub raw URL 或直接链接到 SKILL.md）</em></span>
                    <input
                      type="text"
                      className="input"
                      value={importUrl}
                      onChange={(e) => setImportUrl(e.target.value)}
                      placeholder="https://github.com/user/repo/raw/main/skills/my-skill/SKILL.md"
                    />
                  </label>
                  <p className="skill-import-hint">
                    提示：GitHub 完整仓库请先下载到本地，然后使用「从本地文件夹」导入。
                  </p>
                </div>
              )}
            </div>
            <div className="skill-dialog-footer">
              <button className="btn btn-secondary" onClick={() => { setShowImportDialog(false); setImportMode('local'); setImportUrl(''); }}>取消</button>
              {importMode === 'url' && (
                <button className="btn btn-primary" onClick={handleImportFromUrl} disabled={!importUrl.trim()}>导入</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SkillList;

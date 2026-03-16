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

  const loadSkills = useCallback(async () => {
    if (!api) return;
    const list = await api.listSkills();
    setSkills(list || []);
  }, [api]);

  useEffect(() => { loadSkills(); }, [loadSkills]);

  const handleImport = async () => {
    if (!api) return;
    const result = await api.importSkill();
    if (result?.success) {
      loadSkills();
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
        <button className="btn btn-secondary skills-import-btn" onClick={handleImport}>
          + 导入 Skill
        </button>
      </div>
    </div>
  );
}

export default SkillList;

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function SkillDetail({ skillName, onClose, onDeleted }) {
  const api = window.electronAPI;
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [activeTab, setActiveTab] = useState('readme');

  useEffect(() => {
    if (!api || !skillName) return;
    setLoading(true);
    api.getSkillDetail(skillName).then((d) => {
      setDetail(d);
      setLoading(false);
    });
  }, [skillName, api]);

  const handleDelete = async () => {
    if (!detail || detail.builtin || deleting) return;
    if (!window.confirm(`确认删除 Skill "${detail.name}" ?`)) return;

    setDeleting(true);
    const result = await api.deleteSkill(skillName);
    setDeleting(false);

    if (result?.success) {
      onDeleted?.(skillName);
    }
  };

  if (loading) {
    return (
      <div className="skill-detail">
        <div className="skill-detail-loading">
          <span className="spinner" /> 加载中...
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="skill-detail">
        <div className="skill-detail-empty">Skill 未找到</div>
      </div>
    );
  }

  return (
    <div className="skill-detail">
      <div className="skill-detail-header">
        <div className="skill-detail-title-row">
          <h2 className="skill-detail-name">{detail.name}</h2>
          {detail.builtin && <span className="skill-badge">系统</span>}
          {detail.version && <span className="skill-version">v{detail.version}</span>}
        </div>
        <p className="skill-detail-desc">{detail.description}</p>
        {detail.trigger && (
          <div className="skill-triggers">
            <span className="skill-triggers-label">触发词：</span>
            {detail.trigger.split(/[|,]/).map((t, i) => (
              <span key={i} className="skill-trigger-tag">{t.trim()}</span>
            ))}
          </div>
        )}
        <div className="skill-detail-actions">
          {!detail.builtin && (
            <button
              className="btn btn-secondary"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? '删除中...' : '删除 Skill'}
            </button>
          )}
          <button className="btn btn-ghost" onClick={onClose}>返回项目</button>
        </div>
      </div>

      <div className="skill-detail-tabs">
        <button
          className={`skills-tab ${activeTab === 'readme' ? 'active' : ''}`}
          onClick={() => setActiveTab('readme')}
        >
          说明
        </button>
        <button
          className={`skills-tab ${activeTab === 'files' ? 'active' : ''}`}
          onClick={() => setActiveTab('files')}
        >
          文件 ({detail.files?.length || 0})
        </button>
      </div>

      <div className="skill-detail-body">
        {activeTab === 'readme' && (
          <div className="skill-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{detail.content}</ReactMarkdown>
          </div>
        )}
        {activeTab === 'files' && (
          <div className="skill-files">
            {(detail.files || []).map((f) => (
              <div key={f} className="skill-file-item">
                <span className="skill-file-icon">📄</span>
                <span className="skill-file-name">{f}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default SkillDetail;

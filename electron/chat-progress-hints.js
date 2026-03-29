/**
 * 从 OpenClaw 工具入参、终端输出中抽取「当前技能 / 视频」等，供对话进度展示。
 */

function basename(p) {
  if (!p || typeof p !== 'string') return '';
  const s = p.replace(/\\/g, '/').split('/').pop() || p;
  return s.replace(/^["']|["']$/g, '').trim();
}

function firstVideoPath(str) {
  if (!str) return null;
  const re = /[^\s"'`]+?\.(mp4|mov|webm|mpeg|avi)/gi;
  const m = str.match(re);
  if (!m || !m.length) return null;
  return basename(m[m.length - 1]);
}

/** 从字符串中提取不重复的视频文件名（按出现顺序），最多 max 个 */
function allVideoBasenames(str, max) {
  if (!str || typeof str !== 'string') return [];
  const cap = typeof max === 'number' && max > 0 ? max : 50;
  const re = /[^\s"'`]+?\.(mp4|mov|webm|mpeg|avi)/gi;
  const seen = new Set();
  const out = [];
  let m;
  while ((m = re.exec(str)) !== null) {
    const b = basename(m[0]);
    if (b && !seen.has(b)) {
      seen.add(b);
      out.push(b);
      if (out.length >= cap) break;
    }
  }
  return out;
}

function appendNote(existing, add) {
  const a = String(add || '').trim();
  if (!a) return existing ? String(existing).trim() : '';
  if (!existing || !String(existing).trim()) return a;
  return `${String(existing).trim()} · ${a}`;
}

function detailFromToolInput(toolName, inputRaw) {
  let str = '';
  if (typeof inputRaw === 'string') str = inputRaw;
  else if (inputRaw != null) {
    try {
      str = JSON.stringify(inputRaw);
    } catch {
      str = String(inputRaw);
    }
  }

  const out = {};
  const t = (toolName || '').toLowerCase();

  if (/analyze_video\.py|video-analyzer|投流高光|高光分析/i.test(str)) {
    out.skill = '投流高光片段分析';
    out.phase = '运行分析脚本';
  } else if (/ffmpeg_cut\.py|ffmpeg-cutter|高光切片|成片合成/i.test(str)) {
    out.skill = '高光切片与成片合成';
    out.phase = '运行剪辑脚本';
  } else if (/seedance|video_generate|skill\.py/i.test(str) && /skills\//i.test(str)) {
    const m = str.match(/skills\/([^/\\]+)/i);
    out.skill = m ? `技能：${m[1]}` : '扩展技能脚本';
    out.phase = '执行命令';
  }

  if (/bash|zsh|sh\s|terminal|run_terminal|exec/i.test(t) || /python3?\s|\.py\s/i.test(str)) {
    if (!out.phase) out.phase = '终端命令';
  }

  if (/templates\/default\.txt/i.test(str) || /通用剪辑/.test(str)) {
    out.note = appendNote(out.note, '通用剪辑模版');
  }

  const jsonCmd = tryParseJsonCommand(str);
  const fromStr = allVideoBasenames(str);
  const fromCmd = jsonCmd ? allVideoBasenames(jsonCmd) : [];
  const seenV = new Set();
  const mergedVids = [];
  for (const v of [...fromStr, ...fromCmd]) {
    if (v && !seenV.has(v)) {
      seenV.add(v);
      mergedVids.push(v);
    }
  }
  if (mergedVids.length === 1) {
    out.video = mergedVids[0];
  } else if (mergedVids.length > 1) {
    out.video = mergedVids[0];
    out.note = appendNote(out.note, `视频：${mergedVids.join('、')}`);
  }

  return Object.keys(out).length ? out : null;
}

function tryParseJsonCommand(s) {
  try {
    const o = JSON.parse(s);
    const cmd = o.command || o.shell || o.cmd || o.script || o.input || '';
    return typeof cmd === 'string' ? cmd : '';
  } catch {
    return '';
  }
}

/**
 * 解析单行日志（analyze_video / ffmpeg_cut 等打印）
 */
function detailFromLogLine(line) {
  if (!line || typeof line !== 'string') return null;
  const s = line.trim();
  if (!s) return null;

  let m = s.match(/Analyzing\s*\(S-Level\):\s*(.+)/i);
  if (m) {
    return {
      skill: '投流高光片段分析',
      phase: '正在分析视频',
      video: m[1].trim(),
    };
  }

  m = s.match(/Cross-episode analysis\s*\(S-Level\):\s*(\d+)\s*video/i);
  if (m) {
    return {
      skill: '投流高光片段分析',
      phase: `跨集分析（${m[1]} 个视频）`,
    };
  }

  m = s.match(/Found\s+(\d+)\s+videos?/i);
  if (m) {
    return {
      phase: `找到 ${m[1]} 个视频`,
    };
  }

  m = s.match(/Compressing\s*\(([^)]*)/i);
  if (m) {
    const inner = m[1].trim();
    return {
      phase: inner ? `压缩中（${inner}）` : '压缩视频中…',
    };
  }

  m = s.match(/---\s*Batch\s+(\d+)\/(\d+)\s*\((\d+)\s*videos?\)\s*---/i);
  if (m) {
    return {
      skill: '投流高光片段分析',
      phase: `分析批次 ${m[1]}/${m[2]}（${m[3]} 个视频）`,
    };
  }

  m = s.match(/Cross-episode cut\s*\(S-Level\):\s*(.+)/i);
  if (m) {
    return {
      skill: '高光切片与成片合成',
      phase: '跨集切片合并',
      note: m[1].trim(),
    };
  }

  m = s.match(/Cut\s+([^\s]+\.(?:mp4|mov|webm))/i);
  if (m) {
    return {
      skill: '高光切片与成片合成',
      phase: '切割片段',
      video: basename(m[1]),
    };
  }

  m = s.match(/Results saved to:\s*(.+)/i);
  if (m) {
    return {
      phase: '分析结果已写入',
      note: basename(m[1].trim()),
    };
  }

  m = s.match(/Batch \d+ saved to:\s*(.+)/i);
  if (m) {
    return {
      skill: '投流高光片段分析',
      phase: '批次结果已写入',
      note: basename(m[1].trim()),
    };
  }

  m = s.match(/Output:\s*(.+?\.mp4)/i);
  if (m) {
    return {
      skill: '高光切片与成片合成',
      phase: '已输出成片',
      video: basename(m[1].trim()),
    };
  }

  m = s.match(/\[\s*Refine\s*\]/i);
  if (m) {
    return {
      skill: '投流高光片段分析',
      phase: '精修切点（Refine）',
    };
  }

  m = s.match(/Calling\s+[^\s]+/i);
  if (m) {
    return {
      phase: '调用模型推理中…',
    };
  }

  return null;
}

function detailFromProgressMessage(msg) {
  if (!msg || typeof msg !== 'string') return null;
  const lines = msg.split(/\n/).map((x) => x.trim()).filter(Boolean);
  let merged = null;
  for (const line of lines) {
    const d = detailFromLogLine(line);
    if (d) merged = { ...merged, ...d };
  }
  return merged && Object.keys(merged).length ? merged : null;
}

function mergeDetail(prev, next) {
  const a = prev && typeof prev === 'object' ? prev : {};
  const b = next && typeof next === 'object' ? next : {};
  const o = { ...a };
  for (const k of ['skill', 'video', 'phase', 'note']) {
    if (b[k] != null && String(b[k]).trim() !== '') o[k] = String(b[k]).trim();
  }
  return o;
}

module.exports = {
  detailFromToolInput,
  detailFromLogLine,
  detailFromProgressMessage,
  mergeDetail,
  firstVideoPath,
  allVideoBasenames,
};

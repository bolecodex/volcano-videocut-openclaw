#!/usr/bin/env python3
"""解析任务输出目录：默认输出在 OUTPUT_DIR/music_output/<歌曲名|随机数>。"""
import random
import re
import string
import os
from pathlib import Path
from typing import Optional

def _read_output_dir_from_env_file(env_path: Path) -> str:
    """从 .env 文件读取 OUTPUT_DIR（不依赖 python-dotenv 是否可用）。"""
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if not line.startswith("OUTPUT_DIR="):
                continue
            val = line.split("=", 1)[1].strip().strip("'").strip('"')
            return val
    except Exception:
        return ""
    return ""


# 本文件在 scripts/music_project/：
# - Skill 根目录 = parents[2]（即包含 SKILL.md 的目录）
# - 工作区根目录（默认 OUTPUT_DIR）= Skill 根目录向上三级
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACE_ROOT = _SKILL_ROOT.parent.parent.parent

_ENV_OUTPUT_DIR = (os.getenv("OUTPUT_DIR", "") or _read_output_dir_from_env_file(_SCRIPT_DIR / ".env")).strip()
_ENV_OUTPUT_DIR = _ENV_OUTPUT_DIR.strip().strip("'").strip('"')

_OUTPUT_ROOT = Path(_ENV_OUTPUT_DIR) if _ENV_OUTPUT_DIR else _WORKSPACE_ROOT
_DEFAULT_OUTPUT_BASE = _OUTPUT_ROOT / "music_output"


def get_default_output_base() -> Path:
    """返回默认输出根目录。优先使用 OUTPUT_DIR，否则默认工作区根目录。"""
    return _DEFAULT_OUTPUT_BASE


def sanitize_song_name(name: str) -> str:
    """将歌曲名称转为安全目录名（去掉非法字符、空白规整）。"""
    if not name or not str(name).strip():
        return "unnamed"
    s = str(name).strip()
    for c in r'\/:*?"<>|':
        s = s.replace(c, "_")
    s = re.sub(r"\s+", "_", s)
    s = s.strip("_")
    return s or "unnamed"


def random_6_digits() -> str:
    """返回 6 位随机数字字符串。"""
    return "".join(random.choices(string.digits, k=6))


def resolve_output_dir(*, output_dir: Optional[str], song_name: Optional[str]) -> Path:
    """
    解析任务输出目录。
    - 若 output_dir 已指定，直接使用；
    - 否则为 Skill 根目录 / music_output / <歌曲名称|6位随机数>。
    """
    if output_dir is not None and output_dir.strip():
        return Path(output_dir.strip())
    base = _DEFAULT_OUTPUT_BASE
    if song_name and str(song_name).strip():
        subdir = sanitize_song_name(str(song_name))
    else:
        subdir = random_6_digits()
    return base / subdir

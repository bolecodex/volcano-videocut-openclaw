#!/usr/bin/env bash

set -euo pipefail

# 解析当前脚本所在目录（Skill 根目录）
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

cd "${SCRIPT_DIR}/scripts"

if ! command -v uv >/dev/null 2>&1; then
  echo "[mv-production] 未检测到 uv，请先参考 https://github.com/astral-sh/uv 安装 uv。"
  exit 1
fi

echo "[mv-production] 当前目录：$(pwd)"
echo "[mv-production] 开始使用 uv 安装依赖（uv sync）..."

uv sync

echo "[mv-production] 依赖安装完成。"


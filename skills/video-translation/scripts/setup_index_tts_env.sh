#!/usr/bin/env bash
set -euo pipefail

# One-shot environment bootstrap for Index-TTS + video-translation base pipeline.
# Usage:
#   bash scripts/setup_index_tts_env.sh
#   HF_ENDPOINT=https://hf-mirror.com bash scripts/setup_index_tts_env.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENDORS_DIR="${ROOT_DIR}/scripts/vendors"
INDEX_TTS_DIR="${VENDORS_DIR}/index-tts"
BASE_DIR="${ROOT_DIR}/scripts/base"
LEGACY_INDEX_TTS_DIR="${ROOT_DIR}/vendors/index-tts"

if ! command -v uv >/dev/null 2>&1; then
  echo "[ERROR] uv not found. Please install uv first: https://astral.sh/uv/"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "[ERROR] git not found. Please install git first."
  exit 1
fi

echo "[1/6] Prepare scripts/vendors/index-tts repository"
mkdir -p "${VENDORS_DIR}"
if [ -d "${LEGACY_INDEX_TTS_DIR}" ] && [ ! -d "${INDEX_TTS_DIR}" ]; then
  echo "Found legacy index-tts at ${LEGACY_INDEX_TTS_DIR}, moving to ${INDEX_TTS_DIR}"
  mv "${LEGACY_INDEX_TTS_DIR}" "${INDEX_TTS_DIR}"
fi
if [ ! -d "${INDEX_TTS_DIR}" ]; then
  git clone https://github.com/index-tts/index-tts.git "${INDEX_TTS_DIR}"
fi

echo "[2/6] Sync index-tts virtual environment"
cd "${INDEX_TTS_DIR}"
uv sync --all-extras

echo "[3/6] Check IndexTTS checkpoints"
if [ -f checkpoints/gpt.pth ] && \
   [ -f checkpoints/s2mel.pth ] && \
   [ -f checkpoints/wav2vec2bert_stats.pt ] && \
   [ -f checkpoints/feat1.pt ] && \
   [ -f checkpoints/feat2.pt ] && \
   [ -d checkpoints/qwen0.6bemo4-merge ]; then
  echo "IndexTTS checkpoints already exist, skip download."
else
  echo "IndexTTS checkpoints missing, download from HuggingFace..."
  uv tool install "huggingface-hub[cli,hf_xet]"
  hf download IndexTeam/IndexTTS-2 --local-dir=checkpoints
fi

echo "[4/6] Validate required checkpoint files"
ls checkpoints/gpt.pth \
   checkpoints/s2mel.pth \
   checkpoints/wav2vec2bert_stats.pt \
   checkpoints/feat1.pt \
   checkpoints/feat2.pt \
   checkpoints/qwen0.6bemo4-merge >/dev/null

echo "[5/6] Sync base pipeline environment"
cd "${BASE_DIR}"
uv sync --dev

echo "[6/6] Done"
echo "Index-TTS and base pipeline environments are ready."

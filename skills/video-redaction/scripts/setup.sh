#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Environment Setup...${NC}"

# 1. Check for system dependencies
echo "Checking system dependencies..."


if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add to path for current session
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Python Environment Setup
echo "Setting up Python environment..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ -f "pyproject.toml" ]; then
    echo "Installing dependencies from pyproject.toml..."
    uv sync
else
    echo -e "${RED}pyproject.toml not found!${NC}"
    exit 1
fi

# 3. .env Setup
if [ ! -f ".env" ]; then
    echo "Creating .env template..."
    cat << EOF > .env
# LLM Configuration (for sensitive word detection)
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# Optional: Volcengine ASR (if still used)
VOLCENGINE_API_KEY=your_volc_key_here
EOF
    echo -e "${GREEN}Created .env file. Please edit it with your API keys.${NC}"
else
    echo ".env file already exists."
fi

echo -e "${GREEN}Setup Complete!${NC}"

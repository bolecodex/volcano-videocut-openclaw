#!/usr/bin/env bash
# ============================================================================
# OpenClaw Skills & Plugins 一键部署脚本
# 将自定义 Skills 和 Plugins 快速内置到 OpenClaw 中
#
# 用法:
#   ./openclaw-deploy.sh [选项]
#
# 选项:
#   --skills-dir <path>    自定义 skills 源目录 (默认: ./skills)
#   --plugins-dir <path>   自定义 plugins 源目录 (默认: ./plugins)
#   --config <path>        自定义配置文件 (默认: ./openclaw-extra.json5)
#   --target <scope>       部署目标: workspace | managed | both (默认: workspace)
#   --clawhub-install <slugs>  从 ClawHub 安装的 skills (逗号分隔)
#   --npm-plugins <pkgs>   从 npm 安装的 plugins (逗号分隔)
#   --env-file <path>      .env 文件路径 (会合并到 ~/.openclaw/.env)
#   --publish              将 skills 自动发布到 ClawHub
#   --publish-bump <type>  版本号递增方式: patch | minor | major (默认: patch)
#   --clawhub-token <tok>  ClawHub API Token (CI/CD 环境用)
#   --dry-run              仅预览，不执行
#   --help                 显示帮助
# ============================================================================

set -euo pipefail

# ---- 颜色 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---- 默认值 ----
SKILLS_DIR="./skills"
PLUGINS_DIR="./plugins"
CONFIG_FILE="./openclaw-extra.json5"
TARGET="workspace"
CLAWHUB_INSTALL=""
NPM_PLUGINS=""
ENV_FILE=""
PUBLISH=false
PUBLISH_BUMP="patch"
CLAWHUB_TOKEN=""
DRY_RUN=false
OPENCLAW_HOME="${OPENCLAW_STATE_DIR:-$HOME/.openclaw}"
WORKSPACE="${OPENCLAW_HOME}/workspace"

# ---- 函数 ----

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${CYAN}===== $1 =====${NC}"
}

show_help() {
    head -20 "$0" | tail -16 | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# ---- 参数解析 ----

while [[ $# -gt 0 ]]; do
    case $1 in
        --skills-dir)
            SKILLS_DIR="$2"
            shift 2
            ;;
        --plugins-dir)
            PLUGINS_DIR="$2"
            shift 2
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --target)
            TARGET="$2"
            shift 2
            ;;
        --clawhub-install)
            CLAWHUB_INSTALL="$2"
            shift 2
            ;;
        --npm-plugins)
            NPM_PLUGINS="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --publish)
            PUBLISH=true
            shift
            ;;
        --publish-bump)
            PUBLISH_BUMP="$2"
            PUBLISH=true
            shift 2
            ;;
        --clawhub-token)
            CLAWHUB_TOKEN="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_error "未知选项: $1"
            exit 1
            ;;
    esac
done

# ---- 环境检查 ----

log_step "1/8 环境检查"

# 检查 Node.js
if command -v node &>/dev/null; then
    NODE_VERSION=$(node -v)
    log_success "Node.js: $NODE_VERSION"
    
    # 检查版本 >= 22
    MAJOR=$(echo "$NODE_VERSION" | sed 's/v//' | cut -d. -f1)
    if [[ "$MAJOR" -lt 22 ]]; then
        log_warn "建议使用 Node.js >= 22，当前为 $NODE_VERSION"
    fi
else
    log_error "未找到 Node.js，请先安装: https://nodejs.org"
    exit 1
fi

# 检查 openclaw
if command -v openclaw &>/dev/null; then
    OPENCLAW_VERSION=$(openclaw --version 2>/dev/null || echo "unknown")
    log_success "OpenClaw 已安装: $OPENCLAW_VERSION"
else
    log_warn "OpenClaw 未安装，将自动安装..."
    if [[ "$DRY_RUN" == false ]]; then
        npm install -g openclaw@latest
        log_success "OpenClaw 安装完成"
    else
        log_info "[DRY-RUN] 将执行: npm install -g openclaw@latest"
    fi
fi

# 检查 clawhub
NEED_CLAWHUB=false
if [[ -n "$CLAWHUB_INSTALL" ]] || [[ "$PUBLISH" == true ]]; then
    NEED_CLAWHUB=true
fi

if command -v clawhub &>/dev/null; then
    log_success "ClawHub CLI 已安装"
else
    if [[ "$NEED_CLAWHUB" == true ]]; then
        log_warn "ClawHub CLI 未安装，将自动安装..."
        if [[ "$DRY_RUN" == false ]]; then
            npm install -g clawhub
            log_success "ClawHub CLI 安装完成"
        else
            log_info "[DRY-RUN] 将执行: npm install -g clawhub"
        fi
    else
        log_info "ClawHub CLI 未安装 (无需安装)"
    fi
fi

# ClawHub Token 登录（CI/CD 模式）
if [[ -n "$CLAWHUB_TOKEN" ]]; then
    if [[ "$DRY_RUN" == false ]]; then
        log_info "使用 Token 登录 ClawHub..."
        clawhub login --token "$CLAWHUB_TOKEN" --no-browser 2>/dev/null && \
            log_success "ClawHub Token 登录成功" || \
            log_warn "ClawHub Token 登录失败，publish 可能无法执行"
    else
        log_info "[DRY-RUN] 将使用 Token 登录 ClawHub"
    fi
fi

# ---- 目录准备 ----

log_step "2/8 目录准备"

SKILL_TARGETS=()

case "$TARGET" in
    workspace)
        SKILL_TARGETS=("$WORKSPACE/skills")
        ;;
    managed)
        SKILL_TARGETS=("$OPENCLAW_HOME/skills")
        ;;
    both)
        SKILL_TARGETS=("$WORKSPACE/skills" "$OPENCLAW_HOME/skills")
        ;;
    *)
        log_error "无效的 --target 值: $TARGET (可选: workspace | managed | both)"
        exit 1
        ;;
esac

for dir in "${SKILL_TARGETS[@]}" "$OPENCLAW_HOME/extensions" "$WORKSPACE"; do
    if [[ "$DRY_RUN" == false ]]; then
        mkdir -p "$dir"
        log_success "确保目录存在: $dir"
    else
        log_info "[DRY-RUN] 将创建目录: $dir"
    fi
done

# ---- 部署 Skills ----

log_step "3/8 部署自定义 Skills"

SKILLS_COUNT=0

if [[ -d "$SKILLS_DIR" ]]; then
    # 遍历 skills 目录
    for skill_path in "$SKILLS_DIR"/*/; do
        if [[ -f "${skill_path}SKILL.md" ]]; then
            skill_name=$(basename "$skill_path")
            SKILLS_COUNT=$((SKILLS_COUNT + 1))
            
            for target_dir in "${SKILL_TARGETS[@]}"; do
                if [[ "$DRY_RUN" == false ]]; then
                    mkdir -p "${target_dir}/${skill_name}"
                    cp -r "${skill_path}"* "${target_dir}/${skill_name}/"
                    log_success "已部署 Skill: ${skill_name} -> ${target_dir}/${skill_name}"
                else
                    log_info "[DRY-RUN] 将复制: ${skill_path} -> ${target_dir}/${skill_name}/"
                fi
            done
        else
            log_warn "跳过 $(basename "$skill_path"): 缺少 SKILL.md"
        fi
    done
    
    if [[ $SKILLS_COUNT -eq 0 ]]; then
        log_warn "在 $SKILLS_DIR 中未找到有效的 Skills (需要包含 SKILL.md 的子目录)"
    else
        log_success "共部署 $SKILLS_COUNT 个自定义 Skills"
    fi
else
    log_info "Skills 目录不存在: $SKILLS_DIR (跳过自定义 Skills 部署)"
fi

# ---- 部署 Plugins ----

log_step "4/8 部署自定义 Plugins"

PLUGINS_COUNT=0

if [[ -d "$PLUGINS_DIR" ]]; then
    for plugin_path in "$PLUGINS_DIR"/*/; do
        if [[ -f "${plugin_path}openclaw.plugin.json" ]] || [[ -f "${plugin_path}index.ts" ]]; then
            plugin_name=$(basename "$plugin_path")
            PLUGINS_COUNT=$((PLUGINS_COUNT + 1))
            
            ext_target="${OPENCLAW_HOME}/extensions/${plugin_name}"
            
            if [[ "$DRY_RUN" == false ]]; then
                mkdir -p "$ext_target"
                cp -r "${plugin_path}"* "$ext_target/"
                log_success "已部署 Plugin: ${plugin_name} -> ${ext_target}"
            else
                log_info "[DRY-RUN] 将复制: ${plugin_path} -> ${ext_target}/"
            fi
        else
            log_warn "跳过 $(basename "$plugin_path"): 缺少 openclaw.plugin.json 或 index.ts"
        fi
    done
    
    # 也支持单文件 plugin
    for plugin_file in "$PLUGINS_DIR"/*.ts; do
        if [[ -f "$plugin_file" ]]; then
            plugin_name=$(basename "$plugin_file")
            PLUGINS_COUNT=$((PLUGINS_COUNT + 1))
            
            ext_target="${OPENCLAW_HOME}/extensions/${plugin_name}"
            
            if [[ "$DRY_RUN" == false ]]; then
                cp "$plugin_file" "$ext_target"
                log_success "已部署 Plugin 文件: ${plugin_name} -> ${ext_target}"
            else
                log_info "[DRY-RUN] 将复制: ${plugin_file} -> ${ext_target}"
            fi
        fi
    done
    
    if [[ $PLUGINS_COUNT -eq 0 ]]; then
        log_warn "在 $PLUGINS_DIR 中未找到有效的 Plugins"
    else
        log_success "共部署 $PLUGINS_COUNT 个自定义 Plugins"
    fi
else
    log_info "Plugins 目录不存在: $PLUGINS_DIR (跳过自定义 Plugins 部署)"
fi

# ---- 从 ClawHub 安装 Skills ----

log_step "5/8 从 ClawHub 安装 Skills"

if [[ -n "$CLAWHUB_INSTALL" ]]; then
    IFS=',' read -ra SLUGS <<< "$CLAWHUB_INSTALL"
    
    for slug in "${SLUGS[@]}"; do
        slug=$(echo "$slug" | xargs)  # trim whitespace
        if [[ -n "$slug" ]]; then
            if [[ "$DRY_RUN" == false ]]; then
                log_info "正在从 ClawHub 安装: $slug"
                (cd "$WORKSPACE" && clawhub install "$slug" --force) || {
                    log_warn "安装失败: $slug (可能不存在或网络问题)"
                }
            else
                log_info "[DRY-RUN] 将执行: clawhub install $slug"
            fi
        fi
    done
else
    log_info "未指定 ClawHub Skills (跳过)"
fi

# ---- 从 npm 安装 Plugins ----

if [[ -n "$NPM_PLUGINS" ]]; then
    log_info "从 npm 安装 Plugins..."
    IFS=',' read -ra PKGS <<< "$NPM_PLUGINS"
    
    for pkg in "${PKGS[@]}"; do
        pkg=$(echo "$pkg" | xargs)
        if [[ -n "$pkg" ]]; then
            if [[ "$DRY_RUN" == false ]]; then
                log_info "正在安装 Plugin: $pkg"
                openclaw plugins install "$pkg" || {
                    log_warn "Plugin 安装失败: $pkg"
                }
            else
                log_info "[DRY-RUN] 将执行: openclaw plugins install $pkg"
            fi
        fi
    done
else
    log_info "未指定 npm Plugins (跳过)"
fi

# ---- 自动发布到 ClawHub ----

log_step "6/8 发布 Skills 到 ClawHub"

PUBLISHED_COUNT=0

if [[ "$PUBLISH" == true ]] && [[ -d "$SKILLS_DIR" ]]; then
    for skill_path in "$SKILLS_DIR"/*/; do
        if [[ -f "${skill_path}SKILL.md" ]]; then
            skill_name=$(basename "$skill_path")
            
            # 从 SKILL.md 提取 name 和 description
            pub_name=$(grep -m1 "^name:" "${skill_path}SKILL.md" 2>/dev/null | sed 's/name: *//' || echo "$skill_name")
            pub_desc=$(grep -m1 "^description:" "${skill_path}SKILL.md" 2>/dev/null | sed 's/description: *//' || echo "")
            
            if [[ "$DRY_RUN" == false ]]; then
                log_info "发布 Skill: $skill_name (bump: $PUBLISH_BUMP)"
                
                # 先尝试 publish（新 skill），失败则尝试 sync/update
                clawhub publish "$skill_path" \
                    --slug "$skill_name" \
                    --name "$pub_name" \
                    --changelog "auto-published via openclaw-deploy.sh" \
                    --tags latest \
                    --no-input 2>/dev/null && {
                    PUBLISHED_COUNT=$((PUBLISHED_COUNT + 1))
                    log_success "已发布: $skill_name"
                } || {
                    # publish 失败可能是已存在，尝试作为更新发布
                    log_info "尝试作为更新发布 $skill_name..."
                    clawhub publish "$skill_path" \
                        --slug "$skill_name" \
                        --name "$pub_name" \
                        --changelog "auto-updated via openclaw-deploy.sh" \
                        --tags latest \
                        --no-input 2>/dev/null && {
                        PUBLISHED_COUNT=$((PUBLISHED_COUNT + 1))
                        log_success "已更新发布: $skill_name"
                    } || {
                        log_warn "发布失败: $skill_name (可能需要手动登录或检查权限)"
                    }
                }
            else
                log_info "[DRY-RUN] 将发布: clawhub publish $skill_path --slug $skill_name --tags latest"
                PUBLISHED_COUNT=$((PUBLISHED_COUNT + 1))
            fi
        fi
    done
    
    if [[ $PUBLISHED_COUNT -gt 0 ]]; then
        log_success "共发布 $PUBLISHED_COUNT 个 Skills 到 ClawHub"
    else
        log_warn "没有 Skills 被成功发布"
    fi
elif [[ "$PUBLISH" == true ]]; then
    log_warn "Skills 目录不存在: $SKILLS_DIR，无法发布"
else
    log_info "未启用 ClawHub 发布 (使用 --publish 启用)"
fi

# ---- 合并配置 ----

log_step "7/8 配置合并"

MAIN_CONFIG="${OPENCLAW_HOME}/openclaw.json"

# 合并 .env 文件
if [[ -n "$ENV_FILE" ]] && [[ -f "$ENV_FILE" ]]; then
    ENV_TARGET="${OPENCLAW_HOME}/.env"
    
    if [[ "$DRY_RUN" == false ]]; then
        if [[ -f "$ENV_TARGET" ]]; then
            # 追加不重复的行
            while IFS= read -r line; do
                key=$(echo "$line" | cut -d= -f1)
                if [[ -n "$key" ]] && [[ ! "$key" =~ ^# ]] && ! grep -q "^${key}=" "$ENV_TARGET" 2>/dev/null; then
                    echo "$line" >> "$ENV_TARGET"
                fi
            done < "$ENV_FILE"
            log_success "已合并环境变量到: $ENV_TARGET"
        else
            cp "$ENV_FILE" "$ENV_TARGET"
            log_success "已复制环境变量到: $ENV_TARGET"
        fi
    else
        log_info "[DRY-RUN] 将合并 $ENV_FILE -> $ENV_TARGET"
    fi
else
    if [[ -n "$ENV_FILE" ]]; then
        log_warn "环境变量文件不存在: $ENV_FILE"
    fi
fi

# 处理额外配置
if [[ -f "$CONFIG_FILE" ]]; then
    log_info "发现额外配置文件: $CONFIG_FILE"
    
    if [[ "$DRY_RUN" == false ]]; then
        if [[ -f "$MAIN_CONFIG" ]]; then
            log_warn "主配置文件已存在: $MAIN_CONFIG"
            log_info "额外配置内容如下，请手动合并到主配置中:"
            echo "---"
            cat "$CONFIG_FILE"
            echo "---"
            log_info "你可以使用以下命令通过 RPC 合并配置:"
            log_info "  openclaw gateway call config.patch --params '{\"raw\": \"...\"}'"
        else
            cp "$CONFIG_FILE" "$MAIN_CONFIG"
            log_success "已写入主配置: $MAIN_CONFIG"
        fi
    else
        log_info "[DRY-RUN] 将处理配置文件: $CONFIG_FILE -> $MAIN_CONFIG"
    fi
else
    log_info "未找到额外配置文件: $CONFIG_FILE (跳过)"
fi

# ---- 验证和报告 ----

log_step "8/8 部署报告"

echo ""
echo -e "${CYAN}部署摘要:${NC}"
echo "  OpenClaw Home : $OPENCLAW_HOME"
echo "  Workspace     : $WORKSPACE"
echo "  部署目标      : $TARGET"
echo "  自定义 Skills : $SKILLS_COUNT 个"
echo "  自定义 Plugins: $PLUGINS_COUNT 个"

if [[ "$PUBLISH" == true ]]; then
    echo "  已发布到 ClawHub: $PUBLISHED_COUNT 个"
fi

if [[ -n "$CLAWHUB_INSTALL" ]]; then
    echo "  ClawHub Skills: $CLAWHUB_INSTALL"
fi

if [[ -n "$NPM_PLUGINS" ]]; then
    echo "  npm Plugins   : $NPM_PLUGINS"
fi

echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}[DRY-RUN] 以上为预览模式，未实际执行任何操作${NC}"
    echo ""
    exit 0
fi

# 验证
if command -v openclaw &>/dev/null; then
    echo -e "${CYAN}运行 openclaw doctor 验证...${NC}"
    openclaw doctor 2>/dev/null || true
    echo ""
fi

# 列出已部署的 skills
echo -e "${CYAN}已部署的 Skills:${NC}"
for target_dir in "${SKILL_TARGETS[@]}"; do
    if [[ -d "$target_dir" ]]; then
        echo "  目录: $target_dir"
        for skill in "$target_dir"/*/; do
            if [[ -f "${skill}SKILL.md" ]]; then
                skill_name=$(basename "$skill")
                # 提取 SKILL.md 的 description
                desc=$(grep -m1 "^description:" "${skill}SKILL.md" 2>/dev/null | sed 's/description: *//' || echo "无描述")
                echo "    - $skill_name: $desc"
            fi
        done
    fi
done

echo ""

# 列出已部署的 plugins
echo -e "${CYAN}已部署的 Plugins:${NC}"
ext_dir="${OPENCLAW_HOME}/extensions"
if [[ -d "$ext_dir" ]]; then
    for item in "$ext_dir"/*; do
        if [[ -e "$item" ]]; then
            echo "    - $(basename "$item")"
        fi
    done
fi

echo ""
echo -e "${GREEN}部署完成！${NC}"
echo ""
echo "下一步操作:"
echo "  1. 编辑配置: nano $MAIN_CONFIG"
echo "  2. 重启 Gateway: openclaw gateway --port 18789 --verbose"
echo "  3. 验证 Skills: 在聊天中发送 /skills"
echo "  4. 验证 Plugins: openclaw plugins list"
echo ""

# OpenClaw Skills & Plugins 配置指南

> 基于 OpenClaw 官方文档整理，最后更新: 2026-02-09

## 一、核心概念

OpenClaw 有两套扩展机制：

| 机制 | 用途 | 类比 |
|------|------|------|
| **Skills** | 教 Agent 如何使用工具的提示词（SKILL.md） | 类似 Cursor 的 Agent Skills |
| **Plugins (Extensions)** | 运行时代码扩展（TypeScript 模块） | 类似 MCP Server / 插件系统 |

**重要说明**: OpenClaw 不使用标准 MCP 协议，而是使用自己的 Plugin/Extension 系统来实现类似功能。Plugin 可以注册 Gateway RPC 方法、Agent 工具、CLI 命令、后台服务等。

---

## 二、Skills 系统

### 2.1 Skills 加载位置和优先级

Skills 从三个位置加载，**优先级从高到低**：

1. **Workspace Skills（最高）**: `<workspace>/skills/<skill-name>/SKILL.md`
2. **Managed/Local Skills**: `~/.openclaw/skills/<skill-name>/SKILL.md`
3. **Bundled Skills（最低）**: 随安装包附带

此外可通过 `skills.load.extraDirs` 配置额外目录（最低优先级）。

### 2.2 SKILL.md 格式

每个 Skill 是一个包含 `SKILL.md` 的目录，格式为 YAML frontmatter + 说明文本：

```markdown
---
name: my-skill
description: 这个 Skill 的功能描述
metadata: {"openclaw":{"requires":{"env":["MY_API_KEY"]},"primaryEnv":"MY_API_KEY"}}
---

## 使用说明

这里写 Agent 如何使用这个 Skill 的指令。
用 `{baseDir}` 引用 Skill 文件夹路径。
```

### 2.3 Frontmatter 可选字段

| 字段 | 说明 |
|------|------|
| `name` | Skill 名称（必须） |
| `description` | Skill 描述（必须） |
| `metadata` | JSON 对象，包含 OpenClaw 加载时过滤条件 |
| `homepage` | 在 macOS Skills UI 中显示的网站链接 |
| `user-invocable` | `true/false`，是否暴露为用户斜杠命令（默认 true） |
| `disable-model-invocation` | `true/false`，是否从模型提示词中排除（默认 false） |

### 2.4 Metadata Gating（加载时过滤）

```yaml
metadata: {"openclaw":{"requires":{"bins":["uv"],"env":["GEMINI_API_KEY"],"config":["browser.enabled"]},"primaryEnv":"GEMINI_API_KEY","os":["darwin","linux"]}}
```

- `requires.bins`: PATH 中必须存在的二进制
- `requires.anyBins`: 至少存在一个即可
- `requires.env`: 环境变量必须存在或在配置中提供
- `requires.config`: `openclaw.json` 中必须为真值的路径
- `os`: 限定操作系统（`darwin`, `linux`, `win32`）
- `always: true`: 跳过所有门控，始终加载

### 2.5 Skills 配置 (`~/.openclaw/openclaw.json`)

```json5
{
  skills: {
    // 仅允许特定 bundled skills
    allowBundled: ["gemini", "peekaboo"],
    
    load: {
      // 额外的 skills 目录
      extraDirs: [
        "~/Projects/my-skills/skills",
        "~/Projects/shared-skills/skills"
      ],
      // 文件监听（自动刷新）
      watch: true,
      watchDebounceMs: 250,
    },
    
    install: {
      preferBrew: true,
      nodeManager: "npm",  // npm | pnpm | yarn | bun
    },
    
    // 每个 Skill 的配置
    entries: {
      "nano-banana-pro": {
        enabled: true,
        apiKey: "YOUR_KEY",
        env: {
          GEMINI_API_KEY: "YOUR_KEY",
        },
      },
      "some-skill": {
        enabled: false,  // 禁用此 Skill
      },
    },
  },
}
```

### 2.6 ClawHub（Skills 注册中心）

ClawHub 是 OpenClaw 的公共 Skills 注册中心：https://clawhub.com

```bash
# 安装 CLI
npm i -g clawhub

# 登录
clawhub login

# 搜索 skills
clawhub search "calendar"

# 安装 skill
clawhub install <skill-slug>

# 更新所有已安装的 skills
clawhub update --all

# 同步（扫描本地 + 发布更新）
clawhub sync --all
```

默认安装到 `./skills` 目录，OpenClaw 会在下个 session 自动加载。

### 2.7 自动发布到 ClawHub（CI/CD）

ClawHub 完全支持代码自动发布，核心方式有三种：

#### 方式一：单个 Skill 发布

```bash
clawhub publish ./my-skill \
  --slug my-skill \
  --name "My Skill" \
  --version 1.2.0 \
  --changelog "修复 + 文档更新" \
  --tags latest \
  --no-input
```

#### 方式二：批量扫描 + 自动发布（`sync`）

```bash
# 扫描本地所有 skills 目录，自动发布新增/更新的
clawhub sync --all --bump patch --changelog "auto update"

# 指定额外扫描根目录
clawhub sync --root ~/Projects/skills --all

# 预览模式
clawhub sync --dry-run
```

#### 方式三：CI/CD Token 认证

```bash
# 用 API Token 登录（无需浏览器交互，适合 CI 环境）
clawhub login --token <YOUR_API_TOKEN> --no-browser

# 之后的 publish/sync 命令自动使用该 Token
clawhub sync --all --no-input
```

#### CI/CD 关键参数

| 参数 | 说明 |
|------|------|
| `--no-input` | 禁用交互提示，适合自动化脚本 |
| `--force` | 强制覆盖本地不匹配的版本 |
| `--bump <type>` | 版本递增：`patch` / `minor` / `major` |
| `--tags <tags>` | 逗号分隔的标签（默认 `latest`） |
| `--changelog <text>` | 变更日志文本 |
| `--dry-run` | 预览模式，不实际执行 |

#### GitHub Actions 示例

```yaml
name: Publish Skills to ClawHub
on:
  push:
    paths: ['skills/**']
    branches: [main]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: npm i -g clawhub
      - run: clawhub login --token ${{ secrets.CLAWHUB_TOKEN }} --no-browser
      - run: clawhub sync --all --bump patch --changelog "CI auto-publish" --no-input
```

#### 环境变量

| 变量 | 说明 |
|------|------|
| `CLAWHUB_SITE` | 覆盖站点 URL |
| `CLAWHUB_REGISTRY` | 覆盖注册中心 API URL |
| `CLAWHUB_CONFIG_PATH` | 覆盖 token/config 存储位置 |
| `CLAWHUB_WORKDIR` | 覆盖默认工作目录 |
| `CLAWHUB_DISABLE_TELEMETRY=1` | 禁用遥测 |

---

## 三、Plugins (Extensions) 系统

### 3.1 Plugin 发现和优先级

插件从以下位置扫描，**优先级从高到低**：

1. **配置路径**: `plugins.load.paths`（文件或目录）
2. **Workspace Extensions**: `<workspace>/.openclaw/extensions/*.ts` 或 `<workspace>/.openclaw/extensions/*/index.ts`
3. **Global Extensions**: `~/.openclaw/extensions/*.ts` 或 `~/.openclaw/extensions/*/index.ts`
4. **Bundled Extensions**: `<openclaw>/extensions/*`（默认禁用，需手动启用）

### 3.2 Plugin 清单文件 (`openclaw.plugin.json`)

每个 Plugin 必须包含 `openclaw.plugin.json`：

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "configSchema": {
    "type": "object",
    "properties": {
      "apiKey": { "type": "string" },
      "region": { "type": "string" }
    }
  },
  "uiHints": {
    "apiKey": { "label": "API Key", "sensitive": true },
    "region": { "label": "Region", "placeholder": "us-east-1" }
  }
}
```

### 3.3 Plugin 入口文件

```typescript
// my-plugin/index.ts
export default function register(api) {
  // 注册 Gateway RPC 方法
  api.registerGatewayMethod("myplugin.status", ({ respond }) => {
    respond(true, { ok: true });
  });

  // 注册 CLI 命令
  api.registerCli(({ program }) => {
    program.command("mycmd").action(() => {
      console.log("Hello");
    });
  }, { commands: ["mycmd"] });

  // 注册后台服务
  api.registerService({
    id: "my-service",
    start: () => api.logger.info("ready"),
    stop: () => api.logger.info("bye"),
  });
  
  // 注册自动回复命令（无需 AI 处理）
  api.registerCommand({
    name: "mystatus",
    description: "Show plugin status",
    handler: (ctx) => ({
      text: `Plugin is running! Channel: ${ctx.channel}`,
    }),
  });
}
```

### 3.4 Plugin 配置 (`~/.openclaw/openclaw.json`)

```json5
{
  plugins: {
    enabled: true,       // 主开关
    allow: ["voice-call"],  // 允许列表
    deny: ["untrusted"],    // 拒绝列表（优先于 allow）
    
    load: {
      paths: ["~/Projects/my-plugin"]  // 额外插件路径
    },
    
    // 插件槽位（互斥分类）
    slots: {
      memory: "memory-core",  // 或 "memory-lancedb" 或 "none"
    },
    
    // 每个插件的配置
    entries: {
      "voice-call": {
        enabled: true,
        config: {
          provider: "twilio"
        }
      },
    },
  },
}
```

### 3.5 Plugin CLI 操作

```bash
# 列出已加载插件
openclaw plugins list

# 查看插件信息
openclaw plugins info <id>

# 从 npm 安装
openclaw plugins install @openclaw/voice-call

# 从本地路径安装（复制）
openclaw plugins install ./my-plugin

# 从本地路径链接（开发模式）
openclaw plugins install -l ./my-plugin

# 更新
openclaw plugins update <id>
openclaw plugins update --all

# 启用/禁用
openclaw plugins enable <id>
openclaw plugins disable <id>
```

### 3.6 官方 Plugins 列表

| 插件 | 包名 | 说明 |
|------|------|------|
| Voice Call | `@openclaw/voice-call` | 语音通话 (Twilio) |
| Microsoft Teams | `@openclaw/msteams` | Teams 频道 |
| Matrix | `@openclaw/matrix` | Matrix 频道 |
| Nostr | `@openclaw/nostr` | Nostr 频道 |
| Zalo | `@openclaw/zalo` | Zalo 频道 |
| Zalo Personal | `@openclaw/zalouser` | Zalo 个人频道 |
| Memory (Core) | 内置 | 记忆搜索 |
| Memory (LanceDB) | 内置 | 长期记忆 |
| Copilot Proxy | 内置 | VS Code Copilot 代理 |

---

## 四、Workspace 工作区结构

```
~/.openclaw/
├── openclaw.json              # 主配置文件（JSON5）
├── .env                       # 环境变量（不覆盖已有）
├── workspace/                 # 默认 workspace
│   ├── AGENTS.md              # Agent 系统提示词
│   ├── SOUL.md                # Agent 人格/灵魂
│   ├── TOOLS.md               # 本地工具备忘
│   └── skills/                # Workspace Skills
│       ├── my-skill/
│       │   └── SKILL.md
│       └── another-skill/
│           └── SKILL.md
├── skills/                    # Managed/Local Skills (所有 Agent 共享)
│   ├── skill-a/
│   │   └── SKILL.md
│   └── skill-b/
│       └── SKILL.md
├── extensions/                # Global Extensions/Plugins
│   ├── my-plugin.ts
│   └── another-plugin/
│       ├── index.ts
│       └── openclaw.plugin.json
├── credentials/               # 认证凭据
│   ├── whatsapp/
│   └── oauth.json
└── agents/                    # 多 Agent 配置
    └── main/
        └── agent/
            └── auth-profiles.json
```

---

## 五、快速部署清单

### 步骤 1: 安装 OpenClaw

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

### 步骤 2: 安装 ClawHub CLI

```bash
npm i -g clawhub
```

### 步骤 3: 部署自定义 Skills

```bash
# 复制 skills 到 workspace
cp -r ./my-skills/* ~/.openclaw/workspace/skills/

# 或者到 managed skills (所有 Agent 共享)
cp -r ./my-skills/* ~/.openclaw/skills/
```

### 步骤 4: 配置 Skills & Plugins

编辑 `~/.openclaw/openclaw.json`：

```json5
{
  agent: {
    model: "anthropic/claude-opus-4-6",
  },
  skills: {
    load: {
      extraDirs: ["~/my-shared-skills"],
      watch: true,
    },
    entries: {
      "my-custom-skill": {
        enabled: true,
        env: { MY_API_KEY: "xxx" },
      },
    },
  },
  plugins: {
    entries: {
      "voice-call": { enabled: true },
    },
  },
}
```

### 步骤 5: 发布到 ClawHub（可选）

```bash
# 一键部署 + 发布
./openclaw-deploy.sh --publish

# CI/CD 模式：带 Token + 自动发布
./openclaw-deploy.sh --publish --clawhub-token "YOUR_TOKEN"

# 指定版本递增方式
./openclaw-deploy.sh --publish --publish-bump minor
```

### 步骤 6: 验证

```bash
openclaw doctor
openclaw plugins list
openclaw skills list
```

---

## 六、参考链接

- 官网: https://openclaw.ai
- 文档: https://docs.openclaw.ai
- Skills 文档: https://docs.openclaw.ai/tools/skills
- Skills Config: https://docs.openclaw.ai/tools/skills-config
- ClawHub: https://clawhub.com
- Plugins: https://docs.openclaw.ai/tools/plugin
- 配置参考: https://docs.openclaw.ai/gateway/configuration
- GitHub: https://github.com/openclaw/openclaw

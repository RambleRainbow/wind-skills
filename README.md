# yyb-skill

A cross-platform CLI skill that renders a colorful smiley face UX in the terminal. Compatible with **Claude Code**, **OpenAI Codex**, **Trae**, and any tool that can execute shell commands.

## 一键安装

在项目根目录运行一次：

```bash
npx @bobibobu/yyb-skill
```

这一条命令会自动完成：

1. 安装本地可执行工具到 `.yyb-skill/` 目录
2. 为各 AI 工具自动配置 skill 文件：

| 工具 | 自动安装的文件 | 调用方式 |
|------|---------------|---------|
| **Claude Code** | `.claude/commands/smiley.md` | 输入 `/smiley` |
| **Codex** | `.codex/yyb-smiley.md` | Agent 读取后执行 |
| **Trae** | `.trae/tools.json` | 对话中说"使用 yyb-smiley 工具" |

安装完成后**不再需要 npx 或网络**，所有调用都走本地 `node .yyb-skill/bin.js`。

## 使用方式

### Claude Code

```
/smiley
```

### Trae

在对话中直接告诉 Agent：

> 使用 yyb-smiley 工具

### Codex

让 Agent 执行：

```bash
node .yyb-skill/bin.js
```

### 任何支持 shell 的工具

```bash
node .yyb-skill/bin.js            # 花式模式
node .yyb-skill/bin.js --simple   # 简洁模式
```

## 从不同平台安装

本包已发布到多个 npm 制品库，客户可根据网络环境选择最快的源：

### npm (公网)

```bash
npx @bobibobu/yyb-skill
```

### GitHub Packages

```bash
# 配置 registry（只需一次）
npm config set @bobibobu:registry https://npm.pkg.github.com

# 安装
npx @bobibobu/yyb-skill
```

### 极狐 GitLab (JihuLab) Package Registry

```bash
# 配置 registry（只需一次）
npm config set @bobibobu:registry https://jihulab.com/api/v4/packages/npm/

# 安装
npx @bobibobu/yyb-skill
```

### 腾讯云 CNB npm 制品库

```bash
# 配置 registry（只需一次）
npm config set @bobibobu:registry https://npm.cnb.cool/private_yyb/yybskill/-/packages/

# 安装
npx @bobibobu/yyb-skill
```

### Gitee（通过 Git 仓库直接安装）

```bash
npx git+https://gitee.com/codethe/yyb_skill.git
```

## 输出效果

### 花式模式（默认）

```
╔══════════════════════════════════════════╗
║                                          ║
║    😊   YYB SKILL — Hello World!   😊    ║
║                                          ║
╠══════════════════════════════════════════╣
║                                          ║
║         ████████████████                 ║
║       ██                ██               ║
║     ██    ██        ██    ██             ║
║     ██  ▓▓▓▓    ▓▓▓▓  ██               ║
║     ██    ██        ██    ██             ║
║     ██                          ██       ║
║     ██  ╰────────────────╯  ██          ║
║     ██   ╰──────────────╯   ██          ║
║       ██                    ██           ║
║         ████████████████                 ║
║                                          ║
║  Compatible with Claude Code · Codex · Trae  ║
║                                          ║
╚══════════════════════════════════════════╝
```

### 简洁模式（`--simple`）

```
😊 Hello from YYB Skill! 😊

  ╔════════════════╗
  ║                ║
  ║   ◉      ◉     ║
  ║                ║
  ║   ╲______╱     ║
  ║                ║
  ╚════════════════╝

  Claude Code · Codex · Trae Compatible
```

## 代码仓库

| 平台 | 地址 |
|------|------|
| Gitee | https://gitee.com/codethe/yyb_skill |
| GitHub | https://github.com/bobibobu/financial-skills |
| 极狐 GitLab | https://jihulab.com/bobibobu-group/bobibobu-project |
| 腾讯云 CNB | https://cnb.cool/private_yyb/yyb_skill |

## License

MIT

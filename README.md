# GameLink Agent

**网络语义驱动的游戏服务端自动生成与部署智能体**

把 Godot 单机游戏一键改造成联机游戏：导入工程 → 自动分析 → 选择选项 → 生成 Godot 原生 headless 权威服务端 → 导出可部署的服务端与部署说明。

> 完整方案见 [`dev_plan_1.md`](./dev_plan_1.md)（v2.0）。

## 项目现状

**Phase 0（可行性验证）已完成，并用 Godot 4.3 实测通过。**

- 仓库骨架、规格 Schema、Godot 服务端模板、CLI 链路（`inspect` / `analyze` / `generate` / `deploy`）均就绪。
- `examples/snake-mp` 是把 `examples/snake-single` 手工改造出的服务端权威多人贪吃蛇，已验证 **headless 服务端 + 客户端** 的连接、节点生成、状态复制、输入 RPC 全链路可跑通。
- 待办（Phase 1）：把这条手工链路自动化——调优 LLM 分析提示词，让 `analyze → generate` 直接产出 `snake-mp` 级别的服务端。

## 工作原理

```
Godot 工程 ──▶ 代码摄入 ──▶ LLM 语义分析 ──▶ 规格生成 ──▶ 代码生成 ──▶ 部署
 (输入)         ingest        analyze         *.spec.yaml    generate    Windows VPS
```

- **规格驱动**：所有代码由 `protocol.spec.yaml` / `server-architecture.spec.yaml` 派生。
- **引擎原生**：复用 Godot 高层多人 API（`ENetMultiplayerPeer` / `MultiplayerSynchronizer` / `MultiplayerSpawner` / `@rpc`），导出 headless dedicated server。
- **人机协同**：网络层自动生成，核心玩法逻辑生成框架由开发者确认补充。

## 仓库结构

```
.
├── dev_plan_1.md              # 方案规划文档 v2.0
├── pyproject.toml             # Python 包配置
├── docs/                      # 架构、规格与命令参考
├── src/gamelink/              # 智能体本体（Python）
│   ├── cli.py                 # CLI 入口：inspect / analyze / generate / verify / deploy / config / doctor
│   ├── ui.py                  # 欢迎界面与命令参考（命令元数据的唯一来源）
│   ├── ingest/                # 代码摄入（Godot 工程解析）
│   ├── analyze/               # LLM 语义分析（流式输出 + JSON 模式）
│   ├── spec/                  # 规格模型、读写与一致性校验
│   ├── generate/              # Godot 服务端代码生成
│   ├── deploy/                # 导出 headless 服务端 + 生成部署说明
│   ├── schemas/               # 两份规格的 JSON Schema
│   └── templates/             # GDScript / 导出预设 / 部署说明与脚本模板
├── examples/
│   ├── snake-single/          # 单机贪吃蛇（输入夹具）
│   ├── snake-mp/              # 手工联机版贪吃蛇（Phase 0 产物）
│   └── snake-specs/           # Phase 0 手写规格样例
└── tests/                     # 单元测试
```

## 快速开始

```bash
# 1. 安装（只需一次）
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"

# 2. 在仓库根目录直接输入 gla（不带参数）→ 打开欢迎界面
cd C:\Users\yy197\Documents\GitHub\GameLinkAgent
gla

# 3. 之后可直接执行命令（API key 已存在用户目录，无需每次输入）
gla doctor                                      # 检查环境（Python / Godot / LLM / 部署）
gla inspect examples/snake-single               # 查看工程摘要
gla analyze examples/snake-single               # LLM 分析 → 中文报告（写 specs/snake-single-report.md）

# 需要继续生成服务端时，让 analyze 一并导出规格：
gla analyze examples/snake-single --specs       # 额外写出 protocol.spec.yaml / server-architecture.spec.yaml
gla generate examples/snake-single --specs specs --out out/snake-gen
gla verify examples/snake-mp --specs specs      # 规格 ↔ 实现一致性校验
gla deploy out/snake-gen                        # 导出 headless 服务端 + 部署说明（out/snake-gen/dist）
```

### 欢迎界面

在仓库根目录直接输入 `gla`（不带参数）会打开欢迎界面：显示版本与**环境状态**（LLM / Godot / 配置文件路径），按「分析 / 生成与部署 / 配置与工具」分组列出全部命令，并在**首次使用时提示你输入 LLM API key**。

- 界面里可直接输入命令，例如 `analyze examples/snake-single`（等价于 `gla analyze examples/snake-single`）。
- `help` 重看命令列表；`help <命令>` 看某命令的详细用法（用法 / 说明 / 示例），例如 `help analyze`；`exit` 退出。
- 配置保存在**用户目录**，不写入仓库：
  - Windows：`%APPDATA%\GameLinkAgent\config.json`
  - 其他：`~/.config/gamelink/config.json`
- 之后可随时用 `gla config` 重新配置。

> 完整命令参考见 [`docs/commands.md`](./docs/commands.md)；命令行里随时可用 `gla help`、`gla help <命令>` 或 `gla <命令> --help`（后者列出全部选项）。

> `gla` 是 `gamelink` 的等价别名；`gla.cmd` 会切到仓库根目录再运行，所以 `.env` 和相对路径都能正常解析。
>
> `gla analyze` 运行时会显示「正在调用 LLM 分析工程…」的等待动画与进度；加 `--stream` 可**实时打印模型的推理过程**；加 `-i` 可交互式选择生成选项。默认只产出 **Markdown 报告**（`specs/<工程名>-report.md`），加 `--specs` 才额外导出两份规格供 `generate` 使用。

## 环境要求

- Python ≥ 3.10
- **Godot 4.x**（分析校验与导出服务端需要）。本机为 **Godot 4.7.2**，位于 `C:\D\GodotEngine`；
  在 `.env` 中设置 `GAMELINK_GODOT_BIN` 指向引擎可执行文件即可（建议用 `*_console.exe`）。
- 一台 Windows 云服务器（部署目标）

## 许可证

MIT，见 [`LICENSE`](./LICENSE)。

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
├── tools/
│   └── bootstrap.ps1          # 首次运行引导（Python / venv / 依赖）
├── examples/
│   ├── snake-single/          # 单机贪吃蛇（输入夹具）
│   ├── snake-mp/              # 手工联机版贪吃蛇（Phase 0 产物）
│   └── snake-specs/           # Phase 0 手写规格样例
└── tests/                     # 单元测试
```

## 快速开始

把仓库拉到任意一台 Windows 电脑，在仓库根目录运行 `gla.cmd` 即可。**不需要预先安装 Python，也不需要手动建 venv 或装依赖。**

```bat
git clone https://github.com/yuyi-yutie/GameLinkAgent.git
cd GameLinkAgent
gla.cmd
```

> PowerShell 用户请写 `.\gla.cmd`（PowerShell 不会从当前目录查找命令）。

首次运行会自动完成三件事：

1. **准备 Python**：优先复用系统里已有的 3.10–3.14；找不到就从 python.org 下载官方安装器（校验签名后静默安装一份到仓库内的 `.python/`，不改系统 PATH，也不需要管理员权限）。
2. **创建 `.venv`**：如果 `.venv` 是从别的机器拷来的、已经失效，会自动删除重建。
3. **安装全功能依赖**：CLI + Web 界面（`.[web]`），所以 `gla.cmd web` 首次即可用。

然后进入欢迎界面，首次会提示输入 LLM API key（保存在用户目录，不随仓库走）。之后日常使用：

```bat
gla.cmd                                         # 打开欢迎界面（首次会提示输入 LLM API key）
gla.cmd doctor                                  # 检查环境（Python / Godot / LLM / 部署）
gla.cmd inspect examples/snake-single           # 查看工程摘要
gla.cmd analyze examples/snake-single           # LLM 分析 → 中文报告（写 specs/snake-single-report.md）

# 需要继续生成服务端时，让 analyze 一并导出规格：
gla.cmd analyze examples/snake-single --specs   # 额外写出 protocol.spec.yaml / server-architecture.spec.yaml
gla.cmd generate examples/snake-single --specs specs --out out/snake-gen
gla.cmd verify examples/snake-mp --specs specs  # 规格 ↔ 实现一致性校验
gla.cmd deploy out/snake-gen                    # 导出 headless 服务端 + 部署说明（out/snake-gen/dist）
```

> 首次运行需要网络（下载 Python 和依赖）。**Godot 只有 `verify` / `deploy` 需要**，未配置时其他命令照常可用（用 `gla.cmd config` 配置引擎路径）。
>
> 想手动初始化、或需要跑测试/开发（含 pytest、ruff），先激活环境：`.venv\Scripts\activate`，然后
> `.venv\Scripts\python -m pip install -e ".[dev]"`。

### 欢迎界面

在仓库根目录直接运行 `gla.cmd`（不带参数）会打开欢迎界面：显示版本与**环境状态**（LLM / Godot / 配置文件路径），按「分析 / 生成与部署 / 配置与工具」分组列出全部命令，并在**首次使用时提示你输入 LLM API key**。

- 界面里可直接输入命令，例如 `analyze examples/snake-single`（等价于 `gla.cmd analyze examples/snake-single`）。
- `help` 重看命令列表；`help <命令>` 看某命令的详细用法（用法 / 说明 / 示例），例如 `help analyze`；`exit` 退出。
- 配置保存在**用户目录**，不写入仓库：
  - Windows：`%APPDATA%\GameLinkAgent\config.json`
  - 其他：`~/.config/gamelink/config.json`
- 之后可随时用 `gla config` 重新配置。

> 完整命令参考见 [`docs/commands.md`](./docs/commands.md)；命令行里随时可用 `gla help`、`gla help <命令>` 或 `gla <命令> --help`（后者列出全部选项）。

> `gla.cmd` 会切到仓库根目录再运行，所以 `.env` 和相对路径都能正常解析；激活 `.venv` 后也可以直接使用 `gla` / `gamelink` 命令。
>
> `gla analyze` 运行时会显示「正在调用 LLM 分析工程…」的等待动画与进度；加 `--stream` 可**实时打印模型的推理过程**；加 `-i` 可交互式选择生成选项。默认只产出 **Markdown 报告**（`specs/<工程名>-report.md`），加 `--specs` 才额外导出两份规格供 `generate` 使用。

## 环境要求

- Windows 10/11（启动器为 `gla.cmd`，依赖系统自带的 PowerShell）
- 首次运行需要网络：没有 Python 时会自动下载 3.12 并安装到仓库内，依赖从 PyPI 安装
- **Godot 4.x**：仅 `verify` / `deploy` 需要。用 `gla.cmd config` 选择引擎路径，或设置
  `GAMELINK_GODOT_BIN`（建议用 `*_console.exe`）。
- 一台 Windows 云服务器（部署目标）

## 许可证

MIT，见 [`LICENSE`](./LICENSE)。

# GameLink Agent

**网络语义驱动的游戏服务端自动生成与部署智能体**

把 Godot 单机游戏一键改造成联机游戏：导入工程 → 自动分析 → 选择选项 → 生成 Godot 原生 headless 权威服务端 → 一键部署到 Windows 云服务器。

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
├── docs/                      # 架构与规格说明
├── src/gamelink/              # 智能体本体（Python）
│   ├── cli.py                 # CLI 入口：inspect / analyze / generate / deploy / doctor
│   ├── ingest/                # 代码摄入（Godot 工程解析）
│   ├── analyze/               # LLM 语义分析
│   ├── spec/                  # 规格模型、读写与一致性校验
│   ├── generate/              # Godot 服务端代码生成
│   ├── deploy/                # 部署到 Windows 云服务器
│   ├── schemas/               # 两份规格的 JSON Schema
│   └── templates/godot/       # GDScript 服务端模板
├── examples/
│   ├── snake-single/          # 单机贪吃蛇（输入夹具）
│   ├── snake-mp/              # 手工联机版贪吃蛇（Phase 0 产物）
│   └── snake-specs/           # Phase 0 手写规格样例
├── deploy/                    # Windows 部署脚本与 Dockerfile
└── tests/                     # 单元测试
```

## 快速开始

```bash
# 1. 安装（可编辑模式）
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"

# 2. 检查环境（Python / Godot / LLM / 部署）
gamelink doctor

# 3. 摄入并查看工程摘要
gamelink inspect examples/snake-single

# 4. 分析并生成规格（需要配置 LLM；离线可直接用 examples/snake-specs 的样例规格）
gamelink analyze examples/snake-single --out specs/

# 5. 一键生成服务端（把单机工程改成 headless 权威服务端 + 客户端）
gamelink generate examples/snake-single --specs examples/snake-specs --out out/snake-gen

# 6. 校验规格与实现是否一致（用 Godot 内省做 ground-truth）
gamelink verify examples/snake-mp --specs examples/snake-specs

# 7. 部署（默认 dry-run，不改动服务器）
gamelink deploy out/snake-gen --dry-run
```

## 环境要求

- Python ≥ 3.10
- **Godot 4.x**（分析校验与导出服务端需要）。本机为 **Godot 4.7.2**，位于 `C:\D\GodotEngine`；
  在 `.env` 中设置 `GAMELINK_GODOT_BIN` 指向引擎可执行文件即可（建议用 `*_console.exe`）。
- 一台 Windows 云服务器（部署目标）

## 许可证

MIT，见 [`LICENSE`](./LICENSE)。

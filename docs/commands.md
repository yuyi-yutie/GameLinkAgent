# 命令参考

本文件是 GameLink Agent CLI 的命令参考。**权威来源是代码本身**——欢迎界面与 `gla help` 由 `src/gamelink/ui.py` 里的命令元数据渲染，保持同步。

- 在仓库根目录直接运行 `gla`（不带参数）→ 进入**交互式欢迎界面**。
- `gla help` → 命令列表；`gla help <命令>` → 某个命令的详细用法。
- `gla <命令> --help` → Typer 自动生成的完整选项列表。

## 分析

### `gla inspect <工程目录>`

解析 Godot 工程结构并打印摘要：工程名、主场景、autoload、脚本 / 场景 / 资源数量。**不调用 LLM，无需 API key。**

```bat
gla inspect examples/snake-single
```

### `gla analyze <工程目录> [选项]`

LLM 分析工程，输出**中文 Markdown 报告**；可选导出规格。

| 选项 | 说明 |
| --- | --- |
| `--out <目录>` | 输出目录，默认 `specs/` |
| `--specs` | 额外导出 `protocol.spec.yaml` / `server-architecture.spec.yaml`（供 `generate`） |
| `-i` / `--interactive` | 交互式选择生成选项 |
| `--stream` | 实时打印模型的推理过程 |
| `--authority-model` | `server_authoritative` / `client_authoritative` / `hybrid` |
| `--sync-mechanism` | `state` / `event` / `state+event` / `lockstep` |
| `--transport` | `enet` / `websocket` / `webrtc` |
| `--room-mode` | `single` / `room_list` / `matchmaking` |
| `--max-players` / `--tick-rate` | 人数 / 服务端 tick 率 |
| `--persistence` | `none` / `sqlite` / `redis` |
| `--deploy-target` | `local_docker` / `windows_server` |

默认只写 Markdown 报告：`specs/<工程名>-report.md`。

```bat
gla analyze examples/snake-single
gla analyze examples/snake-single --specs
gla analyze examples/snake-single -i --stream
```

## 生成与部署

### `gla generate <工程目录> --specs <规格目录> [--out <输出目录>]`

按规格生成可运行的 Godot 服务端工程：复制输入工程（保留资源与场景）、写入网络层（`NetworkManager` autoload + 多人主控 + 实体）、给 `project.godot` 补 autoload，并写出 `export_presets.cfg` 与 `gamelink/server.json`（供 `deploy`）。
RPC 函数名取自 `protocol.spec.yaml` 里的 `message.id`；会打印需要人工/后续 LLM 补全的 `refactors` TODO。

```bat
gla generate examples/snake-single --specs specs --out out/snake-gen
```

### `gla verify <工程目录> --specs <规格目录>`

用 headless Godot 内省出真实的 `@rpc` 方法与 autoload，与规格逐条比对；报告「规格里有但工程里没有（疑似幻觉）」与「工程里有但规格漏了（遗漏）」。需要 `GAMELINK_GODOT_BIN`。

```bat
gla verify examples/snake-mp --specs specs
```

### `gla deploy <生成的工程目录> [--out <导出目录>]`

导出 **headless 单文件服务端**并生成部署说明，产出 `<工程>/dist/`：

```
dist/
├── <slug>-server.exe       # 导出的服务端（内嵌资源）
├── 使用说明.md              # 逐步部署说明
└── scripts/
    ├── open_firewall.ps1   # 放通 UDP 端口
    └── install_service.ps1 # 用 NSSM 注册为 Windows 服务
```

**不触碰任何远端服务器**；把 `dist/` 上传服务器后按 `使用说明.md` 操作即可。需要 Godot 引擎与已安装的导出模板。

```bat
gla deploy out/snake-gen
```

## 配置与工具

| 命令 | 说明 |
| --- | --- |
| `gla config` | 配置 LLM（API key / 端点 / 模型），保存到用户目录 |
| `gla doctor` | 检查环境（Python / Godot / LLM / 部署 / 用户配置） |
| `gla shell` | 进入交互式欢迎界面（等价于不带参数运行 `gla`） |
| `gla help [命令]` | 命令列表，或某个命令的详细用法 |
| `gla version` | 显示版本 |

## 配置文件与优先级

LLM 配置保存在**用户目录**，不写入仓库：

| 平台 | 路径 |
| --- | --- |
| Windows | `%APPDATA%\GameLinkAgent\config.json` |
| 其他 | `~/.config/gamelink/config.json` |

配置优先级（高 → 低）：**环境变量 → 用户配置 → 仓库 `.env` → 内置默认**。

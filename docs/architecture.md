# 架构说明

本文档描述 GameLink Agent 的实现结构，与 [`../dev_plan_1.md`](../dev_plan_1.md) §3 的四层架构一一对应。

## 四层与代码模块

| 方案层 | 职责 | 代码位置 |
|---|---|---|
| 代码摄入层 | 解析 Godot 工程，产出可分析的清单 | `src/gamelink/ingest/godot.py` |
| 语义分析层 | LLM 分析网络语义、分类逻辑、建议权威模型 | `src/gamelink/analyze/` |
| 规格生成层 | 产出并校验 `protocol.spec.yaml` / `server-architecture.spec.yaml` | `src/gamelink/spec/` + `src/gamelink/schemas/` |
| 生成与部署层 | 生成 Godot 服务端、导出 headless 服务端并生成部署说明 | `src/gamelink/generate/` + `src/gamelink/deploy/` |

## 数据流

```
Godot 工程
   │  GodotProject.discover()          ingest/godot.py
   ▼
工程清单 (file tree + 文件内容)
   │  Analyzer.analyze()               analyze/analyzer.py + analyze/llm.py
   ▼
AnalysisResult { report, protocol_spec, architecture_spec }
   │  _write_report()                  cli.py       → specs/<工程名>-report.md（默认输出）
   │  write_specs()  (仅 --specs)       spec/io.py   (JSON Schema 校验)
   ▼
specs/<工程名>-report.md   （可选：protocol.spec.yaml / server-architecture.spec.yaml）
   │  verify_consistency()             spec/verify.py  (Godot 内省 ground-truth)
   │  generate_server()                generate/godot.py  (模板渲染)
   ▼
out/snake-gen/  (改写后的 Godot 工程，含 export_presets.cfg 与 gamelink/server.json)
   │  package()                         deploy/windows.py  (Godot CLI 导出 + 打包)
   ▼
out/snake-gen/dist/  (<slug>-server.exe + 使用说明.md + scripts/*.ps1)
```

## 关键设计

- **规格是唯一契约**：代码由 `*.spec.yaml` 派生。规格带 JSON Schema（`src/gamelink/schemas/`），任何不合法输出都会被拦下。生成器连 RPC 函数名都取自规格里的 `message.id`。（`analyze` 默认只产出 Markdown 报告；加 `--specs` 才导出规格。）
- **结构化输出**：调用 LLM 时启用 JSON 模式（`response_format: {"type": "json_object"}`），从源头保证回复是合法 JSON；端点不支持时自动降级并以「字符串感知的括号匹配」提取器兜底（容忍 ```json 围栏、前后散文、字符串内的花括号、尾随逗号）。
- **模板驱动生成**：GDScript 骨架放在 `src/gamelink/templates/godot/`，通过 `{{ key }}` 占位符渲染。生成时复制输入工程（保留资源与场景），再写入网络层并给 `project.godot` 补上 autoload。新增游戏类型 = 新增模板，而非改生成器逻辑。
- **成本极低的可靠性补丁**：`spec/verify.py` 用 headless Godot 内省工程真实存在的 `@rpc`/autoload 等，与规格比对，捕获幻觉与遗漏（见方案 §4.5）。CLI 入口：`gamelink verify`。
- **部署自包含**：`deploy` 用 Godot CLI 导出 headless 服务端，并生成 `使用说明.md` 与配套脚本；不触碰任何远端系统，最后一步交给操作者（见方案 §4.6）。

## 扩展点

| 想做的事 | 改哪里 |
|---|---|
| 支持新引擎（如 Unity） | 新增 `ingest/`、`generate/` 下的引擎适配；新增 `templates/<engine>/` |
| 支持新玩法范式 | 在 `templates/godot/` 增加模板，并在 `generate/godot.py` 注册 |
| 换 LLM 提供商 | `gla config` 或 `GAMELINK_LLM_BASE_URL` 环境变量（OpenAI 兼容即可） |
| 更可靠的分析 | 把 `spec/verify.py` 的内省扩展为结构化提取器 |

## 现状与下一步

- **Phase 0（已完成，Godot 4.7.2 实测）**：`examples/snake-mp` 手工联机化产物，验证了 headless 服务端 + 客户端的连接、生成、状态复制、输入 RPC 全链路。
- **Phase 1（进行中）**：`analyze` 已接入真实 LLM（DeepSeek `deepseek-flash`，OpenAI 兼容）并实测产出报告与通过 Schema 校验的规格；`generate` 是模板驱动 + 规格驱动的真实生成器；`verify` 用真实 Godot 内省做一致性校验；`deploy` 已能导出 headless 单文件服务端并生成部署说明（Godot 4.7.2 实测导出产物可对局）。**已知限制**：生成器目前实现的是“贪吃蛇这一类”的固定模板，会采用规格里的 RPC 名，但尚不会实现规格中列出的每一个消息；`refactors` 以 TODO 输出，交给人工/后续 LLM 补全。远程自动下发留待后续。
- 下一步见方案 §5。

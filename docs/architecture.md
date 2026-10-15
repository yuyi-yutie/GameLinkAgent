# 架构说明

本文档描述 GameLink Agent 的实现结构，与 [`../dev_plan_1.md`](../dev_plan_1.md) §3 的四层架构一一对应。

## 四层与代码模块

| 方案层 | 职责 | 代码位置 |
|---|---|---|
| 代码摄入层 | 解析 Godot 工程，产出可分析的清单 | `src/gamelink/ingest/godot.py` |
| 语义分析层 | LLM 分析网络语义、分类逻辑、建议权威模型 | `src/gamelink/analyze/` |
| 规格生成层 | 产出并校验 `protocol.spec.yaml` / `server-architecture.spec.yaml` | `src/gamelink/spec/` + `src/gamelink/schemas/` |
| 生成与部署层 | 生成 Godot 服务端、部署到 Windows 云服务器 | `src/gamelink/generate/` + `src/gamelink/deploy/` |

## 数据流

```
Godot 工程
   │  GodotProject.discover()          ingest/godot.py
   ▼
工程清单 (file tree + 文件内容)
   │  Analyzer.analyze()               analyze/analyzer.py + analyze/llm.py
   ▼
AnalysisResult { report, protocol_spec, architecture_spec }
   │  write_specs()                    spec/io.py  (JSON Schema 校验)
   ▼
specs/{protocol.spec.yaml, server-architecture.spec.yaml, gamelink.options.yaml}
   │  verify_consistency()             spec/verify.py  (Godot 内省 ground-truth)
   │  generate_server()                generate/godot.py  (模板渲染)
   ▼
out/snake-server/  (改写后的 Godot 工程)
   │  deploy()                         deploy/windows.py
   ▼
Windows 云服务器 (headless 服务端 + UDP 端口)
```

## 关键设计

- **规格是唯一契约**：代码由 `*.spec.yaml` 派生。规格带 JSON Schema（`src/gamelink/schemas/`），任何不合法输出都会被拦下。生成器连 RPC 函数名都取自规格里的 `message.id`。
- **模板驱动生成**：GDScript 骨架放在 `src/gamelink/templates/godot/`，通过 `{{ key }}` 占位符渲染。生成时复制输入工程（保留资源与场景），再写入网络层并给 `project.godot` 补上 autoload。新增游戏类型 = 新增模板，而非改生成器逻辑。
- **成本极低的可靠性补丁**：`spec/verify.py` 用 headless Godot 内省工程真实存在的 `@rpc`/autoload 等，与规格比对，捕获幻觉与遗漏（见方案 §4.5）。CLI 入口：`gamelink verify`。
- **部署可预演**：`deploy` 默认 `--dry-run`，只打印计划；`--apply` 才真正上传与改服务器状态。

## 扩展点

| 想做的事 | 改哪里 |
|---|---|
| 支持新引擎（如 Unity） | 新增 `ingest/`、`generate/` 下的引擎适配；新增 `templates/<engine>/` |
| 支持新玩法范式 | 在 `templates/godot/` 增加模板，并在 `generate/godot.py` 注册 |
| 换 LLM 提供商 | 改 `.env` 的 `GAMELINK_LLM_BASE_URL`（OpenAI 兼容即可） |
| 更可靠的分析 | 把 `spec/verify.py` 的内省扩展为结构化提取器 |

## 现状与下一步

- **Phase 0（已完成，Godot 4.7.2 实测）**：`examples/snake-mp` 手工联机化产物，验证了 headless 服务端 + 客户端的连接、生成、状态复制、输入 RPC 全链路。
- **Phase 1（进行中）**：`generate` 已是模板驱动的真实生成器（产出可运行多人工程，已实测）；`verify` 用真实 Godot 内省做一致性校验（已实测）。仍待完成：接 LLM 让 `analyze` 从任意输入工程自动产出规格（目前需人工编写或用 `examples/snake-specs` 样例）。
- 下一步见方案 §5。

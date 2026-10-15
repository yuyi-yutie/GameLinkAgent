# 规格说明

GameLink Agent 用两份 YAML 规格作为“人机确认”的检查点与代码生成的唯一依据。二者均有 JSON Schema，位于 `src/gamelink/schemas/`。

示例见 [`../examples/snake-specs/`](../examples/snake-specs/)。

## protocol.spec.yaml

描述网络协议：消息与复制状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| `game` | string | 游戏名（必填） |
| `target_engine` | string | 目标引擎，默认 `godot-4.x` |
| `transport` | string | Godot 传输类，如 `ENetMultiplayerPeer` |
| `messages[]` | array | 消息列表（必填） |
| `state[]` | array | 需要复制的状态节点 |

**messages[]**

| 字段 | 取值 | 说明 |
|---|---|---|
| `id` | string | 消息/RPC 名（必填） |
| `direction` | `C2S` / `S2C` | 方向（必填） |
| `rpc_mode` | `authority` / `any_peer` | 对应 Godot `@rpc` 模式 |
| `transfer` | `reliable` / `unreliable` / `unreliable_ordered` | 传输保证 |
| `params[]` | `{name, type}` | 参数 |
| `description` | string | 语义说明 |

**state[]**

| 字段 | 取值 | 说明 |
|---|---|---|
| `node` | string | 节点名（必填） |
| `authority` | `server` / `client` | 权威归属 |
| `replicated[]` | `{name, type}` | 复制的属性（必填） |

## server-architecture.spec.yaml

描述目标服务端架构。

| 字段 | 类型 | 说明 |
|---|---|---|
| `authority_model` | `server_authoritative` / `client_authoritative` / `hybrid` | 权威模型（必填） |
| `tick_rate` | int (1–120) | 服务端模拟频率 |
| `scene` | object | 服务端根场景（必填） |
| `spawns[]` | `{node, spawner}` | 由谁生成哪些节点（`MultiplayerSpawner`） |
| `refactors[]` | `{name, source, action}` | 需要对原工程做的改造 |

**refactors[].action** 取值：`move_to_server`、`convert_to_rpc`、`keep_on_client`、`review`。

## gamelink.options.yaml

记录设计师在选项交互中的选择（见方案 §3.3），随规格一同保存，供 `generate` 复用。

## 校验

```python
from gamelink.spec import read_specs  # 读取并校验
from gamelink.spec import validate_protocol, validate_architecture

protocol, architecture = read_specs("specs/")
```

任何不符合 Schema 的规格都会抛出 `SpecValidationError`。

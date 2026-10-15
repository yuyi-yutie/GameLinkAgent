# Snake MP — Phase 0 手工联机化产物

这是把 [`../snake-single`](../snake-single) **手工**改造成的服务端权威多人贪吃蛇，用来在自动化之前**先证明“Godot 原生 headless 服务端”这条路走得通**。

## 架构

```
              ┌──────────────── 服务端 (headless) ────────────────┐
              │  权威模拟：移动/碰撞/食物/计分（TICK_RATE=10Hz）    │
              │  MultiplayerSpawner 生成/销毁每个玩家的 Snake      │
              │  每个 Snake 上挂 MultiplayerSynchronizer 复制状态  │
              └───────────────┬──────────────────────────────────┘
                              │  ENet(UDP, 默认 7000)
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
   客户端 A                                    客户端 B
   只读复制状态并渲染                        只发送“意图”，不写状态
   发送 submit_direction 意图 RPC            （authority=server）
```

**关键点**

- **权威在服务端**：客户端只发 `submit_direction(dir)` 意图（`@rpc("any_peer")`），服务端校验后推进模拟。客户端从不改 `segments`。
- **状态复制**：每个 `Snake` 节点的 `MultiplayerSynchronizer` 复制 `segments`（`Array[Vector2i]`）与 `score`，权威为服务端（peer 1）。
- **生成/销毁**：`MultiplayerSpawner` 以代码函数 `_spawn_snake` 生成节点（用 `spawn_function`，无需 `snake.tscn`），玩家断线时服务端 `queue_free` 即自动同步销毁。
- **食物**：服务端权威，`sync_food` RPC（`authority + call_local`）广播；新玩家加入时用 `rpc_id` 单播当前食物位置。
- **同工程双形态**：整个场景在 `main.gd` 里用代码构建，所以同一工程既能当渲染客户端，也能 `--headless --server` 当专用服务端。

## 运行

### 本地对局（一个服务端 + 若干客户端）

1. Godot **4.x** 导入本目录（本机为 4.7.2，位于 `C:\D\GodotEngine`）。
2. 运行实例 1 → 点 **Host**（成为服务端，id=1）。
3. 再运行若干实例 → 填地址（本机 `127.0.0.1`）点 **Join**。
4. 方向键控制各自蛇；吃到食物得分，撞墙/撞蛇即重生（Phase 0 先做即时重生）。

### 专用服务端（部署用）

```bash
godot --headless --path examples/snake-mp --server
```

`main.gd` 检测到 `--server` 会自动 Host。要打包成可部署的服务端，用 `gla deploy <工程目录>`（会导出单文件服务端并生成 `使用说明.md`）。

> 注意：**首次**用命令行 `godot --headless --path ...` 从源码运行前，先跑一次
> `godot --headless --path examples/snake-mp --editor --quit` 完成导入；
> 否则全局类 `Snake` 可能尚未注册而报 `Identifier "Snake" not declared`。
> 用编辑器打开工程运行、或运行导出的服务端二进制，都没有这个问题。

### 自动化验收（headless，无需开窗口）

```bash
# 1) 起服务端（后台）
godot --headless --path examples/snake-mp -- --server

# 2) 起一个会自己转向的客户端，观察复制状态
godot --headless --path examples/snake-mp --quit-after 8000 -- --join 127.0.0.1 --debug-net --autopilot
```

`--debug-net` 打印每条蛇的复制状态（长度/蛇头/分数），`--autopilot` 让客户端通过正常的
`submit_direction` RPC 周期性发送转向意图。看到蛇头位置出现**转向**（而非一直直线撞墙），
即证明「客户端输入 → 服务端权威 → 复制回客户端」整条链路成立。

## 与单机版的差异（即 Agent 需要自动完成的改造）

| 单机版 `snake-single` | 联机版 `snake-mp` |
|---|---|
| `main.gd` 里状态与表现混在一起 | 拆成「服务端权威逻辑」+「客户端表现」 |
| 本地直接改 `direction` | 输入变成 `submit_direction` 意图 RPC |
| 本地 `food` 随机 | 服务端权威 + `sync_food` 广播 |
| 单条蛇 | `MultiplayerSpawner` 按玩家生成多条蛇 |
| 无同步 | 每个蛇 `MultiplayerSynchronizer` 复制状态 |

## Phase 0 已知简化（留给 Phase 1）

- 死亡为即时重生，无死亡动画/计时器。
- 蛇的移动意图在同 tick 内的二次转向未做严格排序。
- 无房间列表/匹配，只有单房间直连。
- 无客户端预测/插值（直接渲染复制值）。

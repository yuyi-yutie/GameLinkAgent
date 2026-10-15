# Snake Single — Phase 0 baseline

这是 GameLink Agent 的**输入夹具**：一个纯单机的 Godot 4 贪吃蛇，**不含任何网络代码**。

它的作用有两个：

1. **Phase 0 手工验证**：人工把它改造成“headless 服务端 + N 客户端”的联机版，证明 Godot 原生服务端这条路走得通。
2. **长期测试基线**：之后所有自动分析/生成都拿它当固定输入，作为回归对照。

## 运行

1. 用 Godot **4.3+** 打开本目录（`import` 该文件夹）。
2. 按 `F5` 运行。

## 操作

- 方向键控制移动
- 撞墙或撞到自己即结束
- 结束后按 `R` 重开

## 结构

```
project.godot          # 项目配置（无 autoload、无网络）
scenes/main.tscn       # 主场景：Main(Node2D) + UI/ScoreLabel(Label)
scripts/main.gd        # 游戏控制器：状态 + 表现混在一起（正是要被拆分的部分）
scripts/snake.gd       # Snake 实体：纯状态（segments/direction）
```

## 为什么它适合当基线

- 状态清晰：`segments`、`food`、`score`、`game_over` 一目了然，便于评估 LLM 的抽取质量。
- 混杂明确：权威逻辑与表现逻辑都在 `main.gd` 里，正是“逻辑分类”要解决的典型场景。
- 体量小：分析、生成、部署全链路能快速迭代。

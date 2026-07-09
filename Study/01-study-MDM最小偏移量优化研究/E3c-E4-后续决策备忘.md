# E3c / E4 后续决策备忘

> 日期：2026-07-09  
> 作用：在 E3b existing-grid 结果已封存后，明确 Ch6 是否可以写、E3c 是否需要立即启动、E4 的触发条件是什么。

## 当前决定

**APPROVE Ch6 existing-grid 写作。**

E3b 已足够支撑 Ch6 的当前主张：

> 在本文正式离散网格内，仅凭样本可观测特征可以学习更细的 delta 选择信号，并显著优于 Default/L1/L2 简单可部署层级。

**DEFER E3c。**

当前不启动 continuous-space E3c。原因是 Ch6 现在只主张 formal existing-grid 可达性，不写连续空间部署泛化。若启动 E3c，就必须重新冻结连续参数分布、样本量、计算预算、stop conditions 和新的 provenance 合同；这会把当前任务从 Ch6 写作扩成新的正式实验。

**KEEP E4 AS A SEPARATE GATE.**

E4 不是 Ch6 初稿的前置条件。只有当摘要、Discussion 或 Conclusion 需要写成更宽部署推荐时，才需要启动 E4 边界与稳健性验证。

## 已有证据

E3b 封存点：`bedd65a`

核心结果：

| 项 | 值 |
|----|----|
| `Vector-MLP-L6` pooled J1 | 0.547003 |
| `L2` pooled J1 | 0.632541 |
| `L5-oracle` pooled J1 | 0.571170 |
| `L6-hindsight` pooled J1 | 0.494530 |
| seed 42/2026/3407 pooled J1 | 0.547003 / 0.546133 / 0.544009 |
| contract tests | 11 passed, 0 skipped, 0 failed |

解释边界：

- `Vector-MLP-L6` 超过 L5-oracle 不表示超过理论上界；L5 是组级真参数 oracle，L6 才是逐样本 hindsight benchmark。
- endpoint rate 高不是自动失败；L6-hindsight 本身也高度 endpoint 化，必须结合 selected-loss J1 和 near-optimal/regret 判断。
- E3b 的输入不包含真参数、配置 ID、seed、`repeat_id` 或 candidate `delta`；真参数只用于离线标签和评价。

## 触发 E3c 的条件

只有出现以下写作需求之一，才建议启动 E3c：

1. 摘要或结论想写“连续参数空间可泛化”。
2. 目标期刊或审稿意见要求证明模型不是只适用于 45 个正式离散参数组合。
3. Ch6 需要给出可直接部署到新参数区域的推荐，而不只是展示 existing-grid 可达性。

若启动 E3c，必须另写 plan，至少冻结：

- `beta`、`gamma/eta`、`eta`、`n` 的采样分布；
- train/test 参数空间切分；
- repeats、delta grid、failure penalty；
- 是否继续 vector-output MLP；
- 是否保留 E3b 的全部 diagnostics；
- manifest / summary / contract tests 的新字段。

## 触发 E4 的条件

E4 适合回答边界与稳健性，而不是继续证明 Ch6 的主信号。建议在以下场景启动：

1. 需要说明方法在更小 `n`、更大 `n`、更极端 `beta` 或 `gamma/eta=0` 时是否仍可用。
2. 需要比较计算成本、失败率、endpoint 行为和 near-optimal 行为的边界。
3. 需要给实践推荐分层：何时用 Default，何时用 L2，何时值得用样本自适应模型。

若不启动 E4，Ch7/Discussion 仍可写，但必须是边界说明而不是强推荐。

## 当前下一步

1. 继续打磨 `draft-Ch6-初稿.md`，先服务 existing-grid 主张。
2. 冻结 Ch6 出版级图表/表格命名。
3. 再决定 Ch7 是写成 E4 计划章、边界讨论章，还是启动正式 E4 实验。

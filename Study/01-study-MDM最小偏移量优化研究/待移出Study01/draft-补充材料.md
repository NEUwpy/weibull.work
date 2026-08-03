# 补充材料

> 本文件承载已有正式实验的补充图表草稿。补充编号为投稿准备编号，不改变主文章节和图表编号。

## Supplementary Table S1. `Vector-MLP-L6` 边界选择率的跨 seed 诊断

| seed | extreme/near-boundary rate |
|-----:|---------------------------:|
| 42 | 0.4881 |
| 2026 | 0.4884 |
| 3407 | 0.5624 |

`extreme/near-boundary rate` 定义为 $P(\hat\delta\in\{0,0.02,0.48,0.50\})$。三个 seed 的 pooled $J_1$ 结论方向一致，但 seed 3407 的边界选择率高于其余两个 seed，表明 selected-loss 稳定不等于具体 $\delta$ 选择分布完全稳定。本表是 Ch6 existing-grid 的补充诊断，不代替 Ch7/E4 的正式边界稳健性检查。

数据溯源：`../artifacts/formal/E3b_vector_mlp/seed_stability.csv`。

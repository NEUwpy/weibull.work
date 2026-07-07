# Ch1-Ch5 图表诊断与补齐 — 进度控制

> 评审者任务：补齐"图像解释链"，让读者看懂 δ机制 / n的有限收益 / L2内部异质性 / β主效应 / L6定位。
> 约束：不重跑MC、不改正式数值、不改analyze脚本语义、不把NN写成中心、不把L6写成上限。

## 任务清单

| # | 图 | 数据源 | 目标章节 | 状态 |
|---|------|------|---------|------|
| A | δ mechanism schematic (概念图) | 手绘 profile | Ch3 §1.4 | ✅ |
| B | L2/n heterogeneity 双panel | delta_risk_curve.csv + mc_scan_raw.csv | Ch4 §2 | ✅ |
| C | β×n δ* heatmap | L4_by_beta_n.csv | Ch5 §3 | ✅ |
| D | L5 β×γ/η×n heatmap (supplementary) | L5_by_beta_goe_n.csv | 附录 | ✅ |
| E | L6 margin diagnostic | (skip, 需重扫mc_scan_raw) | report说明 | ✅ skip |

## 正文修订

| # | 文件 | 修订 | 状态 |
|---|------|------|------|
| T1 | draft-Ch3-初稿.md | §1.4后插入Fig A引用+图注 | ✅ |
| T2 | draft-Ch4-初稿.md | §2后插入Fig B引用+图注 | ✅ |
| T3 | draft-Ch5-初稿.md | §3插入Fig C引用+图注；收紧"n越大δ*越大"为"对小β" | ✅ |

## 步骤

1. [ ] 环境+git确认
2. [ ] 写 plot_fig_diagnostics.py (4图)
3. [ ] 运行+QA验证
4. [ ] vision抽查PNG
5. [ ] 轻量正文修订 (T1-T3)
6. [ ] git diff --check
7. [ ] 写报告

# Study01 论文图表与补充材料索引（均值归一化当前路线）

> 投稿图生成脚本：`manuscript/figures/scripts/make_submission_figures.py`；所有数值均回指封存产物，图表可重新生成。

## 正文图表

| 文件 | 内容 | 来源 |
|---|---|---|
| `fig1_method_structure.png` | 方法结构图：排序样本/样本均值→per-n MLP→26 点损失曲线→选 δ→MDM | 03-论文骨架与 E8 方法合同 |
| `fig2_overall_delta_risk.png` | 整体 δ–风险曲线及组合内重复抽样稳定性 | E5 `shared_data` 26 点损失与 160 组合×300 次重复估计 |
| `fig3_per_n_J1.png` | seed 42 的均值归一化 MLP / Default / L6 按 n 的 J1 | E8 `seed42_primary/summary.json` |
| `fig4_selector_mechanism.png` | 代表损失曲线、选点对应和超额损失分布 | E5 折外预测与 `shared_data` 损失 |
| `fig5_decision_mechanism.png` | 同一参数条件下样本实现如何移动经验梯度、低风险区与 L6 偏移量 | E11 `representative_gradient_curves.csv`、`conditional_loss_curves.csv`、`cell_associations.csv` |
| `fig6_support_validation.png` | 未见参数、传统方法和可靠度寿命的支撑验证 | E8 主结果、B1、B3 与 E6 传统方法参照 |
| `table1_l1_l6.md` | L1–L6 规则/协议/结果 | E8 `specialist/crossfit_layers.csv` |
| `table2_main_results.md` | 主方法比较 | E8 `seed42_primary/summary.json` |
| `table4_parameter_metrics.md` | 固定偏移量与自适应选择的逐参数 Bias、SD、RMSE | E5 折外选择与 `shared_data` 相同样本的参数估计 |
| `table3_support_verification.md` | 支撑验证摘要（四问） | E8 主结果 + B1 + E6 传统方法 + E8 分位点 |

## 补充材料

| 文件 | 内容 | 来源 |
|---|---|---|
| `supp_fig_seed_stability.png` | 三 seed 稳定性按 n | E8 `specialist/seed_stability.csv` |
| `supp_fig_unseen_beta.png` | seed 42 主结果及三初始化范围的未见 β 留出验证 | E8 `seed42_primary/unseen_beta.csv` + `unseen_beta/summary.json` |
| `supp_fig_traditional_per_n.png` | 传统方法参照按 n | E6 `traditional_ref/summary.csv` + E8 |
| `supp_fig_quantile_rmse.png` | seed 42 主结果及三初始化范围的分位点相对 RMSE | E8 `seed42_primary/quantiles.csv` + `quantiles/summary.csv` |
| `supp_fig_decision_conditions.png` | 参数条件平均、可观测样本规则与逐样本事后信息的确认风险 | E10 `mechanism_by_cell.csv`、`confirmation_by_method.csv`、`summary.json` |
| `supp_fig_parameter_landscape.png` | 160 个参数条件中的方法改善与局部退化 | E5 逐样本损失与 E8 折外选择 |
| `supp_fig_z_only_learning_curve.png` | 灵活可观测样本规则的数据量敏感性 | E10 `learning_curve.csv` |
| `supp_table_unseen_beta.md` | 每个留出 β 的 J1 | B1 `unseen_beta/beta_holdout.csv` |
| `supp_table_traditional.md` | WMLE/LSE Bias/RMSE | B2 `traditional_ref/summary.json` |
| `supp_table_quantiles.md` | 分位点相对误差指标 | B3 `quantiles/summary.csv` |

## 复现命令

```bash
python manuscript/figures/scripts/make_submission_figures.py
python manuscript/figures/scripts/qa_submission_figures.py
```

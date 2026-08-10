# Study01 论文图表与补充材料索引（Dimensional-RAW 当前路线）

> 生成脚本：`code/generate_paper_figures.py`；所有数值均回指封存产物，图表可重新生成。旧 G5 特征路线图不在此列。

## 正文图表

| 文件 | 内容 | 来源 |
|---|---|---|
| `fig1_method_structure.png` | 方法结构图：排序原始样本→per-n MLP→26 点损失曲线→选 δ→MDM | 03-论文骨架 2.3；本脚本绘制 |
| `fig2_overall_delta_risk.png` | 整体 δ–风险曲线（160 组合 pooled J1） | E5 `shared_data` 26 点损失 |
| `fig3_per_n_J1.png` | Dimensional-RAW / Default / L6 按 n 的 J1 | E6 `specialist/summary.json` |
| `table1_l1_l6.md` | L1–L6 规则/协议/结果 | E6 `specialist/crossfit_layers.csv` |
| `table2_main_results.md` | 主方法比较 | E6 `specialist/summary.json` |
| `table3_support_verification.md` | 旧正文支撑验证摘要表；当前保留为过程材料，不再进入正文 | E6 + B1 + B2 + B3 汇总 |

## 补充材料

| 文件 | 内容 | 来源 |
|---|---|---|
| `supp_fig_seed_stability.png` | 旧 seed 稳定性图；当前保留为过程材料，附录改用表 B2 | E6 `specialist/seed_stability.csv` |
| `supp_fig_unseen_beta.png` | 未见 β 留出验证 | B1 `unseen_beta/summary.json` |
| `supp_fig_traditional_per_n.png` | 传统方法参照按 n | B2 `traditional_ref/summary.csv` + E6 |
| `supp_fig_quantile_rmse.png` | 分位点相对 RMSE | B3 `quantiles/summary.csv` |
| `supp_table_unseen_beta.md` | 每个留出 β 的 J1 | B1 `unseen_beta/beta_holdout.csv` |
| `supp_table_traditional.md` | WMLE/LSE Bias/RMSE | B2 `traditional_ref/summary.json` |
| `supp_table_quantiles.md` | 分位点相对误差指标 | B3 `quantiles/summary.csv` |

## 复现命令

```bash
python code/run_b1_unseen_beta.py
python code/run_b2_traditional_ref.py --workers 8
python code/run_b3_quantiles.py
python code/generate_paper_figures.py
```

# 图表—结论—数据索引

## 正文图

| 稿件编号 | 文件 | 回答的问题 | 当前生成函数 | 直接数据或计算依据 |
|---|---|---|---|---|
| 图 1 | `main/fig1_method_structure.png` | 网络如何从实际损失曲线学习，并在新样本上预测曲线最低点以选择偏移量？ | `figure_1_method_structure()` | 方法结构图；曲线为流程示意而非数值证据，结构依据 E8 方法合同 |
| 图 2 | `main/fig2_overall_delta_risk.png` | 正偏移量首先改变了什么，继续进行样本自适应选择又增加了什么？ | `figure_2_delta_risk()` | E5 shared-data 的 160 组合 Monte Carlo 损失扫描与 seed 42 折外选择；派生表为 `data/derived/fig2_delta_risk.csv` 和 `fig2_three_stage_error_distribution.csv` |
| 图 3 | `main/fig3_per_n_J1.png` | 各样本量下总体误差改善多少，Default–L6 观测差距有多大，以及改善是否覆盖多数样本？ | `figure_3_main_results()` | E8 `seed42_primary/`、E5 封存 seed-42 折外选择与 shared-data 损失扫描；派生表为 `data/derived/fig3_main_results_by_n.csv` 和 `fig3_sample_loss_difference_quantiles.csv` |
| 图 4 | `main/fig4_selector_mechanism.png` | 网络预测的风险曲线如何转化为偏移量选择，实际选择与 hindsight 的差距有多大？ | `figure_4_selector_mechanism()` | E5 封存均值归一化折外预测和 shared-data 逐 $\delta$ 损失 |
| 图 5 | `main/fig5_decision_mechanism.png` | 同一参数条件下，抽样结果为何会改变低风险偏移量？ | `figure_5_decision_mechanism()` | E11 `representative_gradient_curves.csv`、`conditional_loss_curves.csv`、`cell_associations.csv` 和 `summary.json` |
| 图 6 | `main/fig6_support_validation.png` | 未见参数、传统估计方法和可靠度寿命三类验证如何限定主结果？ | `figure_6_support_validation()` | E8 `seed42_primary/`、`unseen_beta/`、`quantiles/` 与 E6 `traditional_ref/`；正文面板均使用 seed 42 |

## 正文表

| 稿件编号 | 文件 | 作用 | 数据来源 |
|---|---|---|---|
| 表 1 | `tables/table1_mc_design.md` / `.csv` | 明确参数空间、候选偏移量和重复规模 | E8 `specialist/manifest.json` 与共享设计合同 |
| 表 2 | `tables/table1_l1_l6.md` / `.csv` | 比较固定规则、参数条件平均和逐样本事后参照；源文件名沿用正式产物名 | E8 `specialist/crossfit_layers.csv` |
| 表 3 | `tables/table2_main_results.md` / `.csv` | 在同一测试样本上比较均值归一化 MLP、Default 和预设 26 点网格的 L6 | E8 `specialist/summary.json` |

## 附录图表

| 附录编号 | 文件 | 回答的问题 | 数据来源 |
|---|---|---|---|
| 表 B3 | `tables/supp_table_parameter_error_decomposition.*` | 汇总 $J_1$ 的改善是否来自单一参数？ | E5 均值归一化折外选择结果与 shared-data 中相同样本、相同偏移量的参数估计 |
| 图 C1 | `supplementary/supp_fig_parameter_guided.png` | 直接把初步参数估计当作真参数做 plug-in 选点，能否保留 L3–L5 的 oracle 收益？ | PG 正式产物 `artifacts/formal/pg_selector/`（`paired_bootstrap.csv`、`summary_by_beta.csv`、`beta_cell_correctness.csv`）。a 为横向森林图（12 规则按初估量分组、配对 CI、正值为 worse），b 为最佳规则分 $\beta$，c 为 MDM-0.1/WMLE 最近 $\beta$ 网格单元正确率（诊断性） |
| 图 D1 | `supplementary/supp_fig_unseen_beta.png` | 逐一留出未参与训练的形状参数水平后汇总收益及局部例外如何？ | E8 `unseen_beta/summary.json` 与 `beta_holdout.csv` |
| 图 E1 | `supplementary/supp_fig_traditional_per_n.png` | 与 WMLE、LSE 的外部参照关系如何？ | E6 `traditional_ref/summary.csv` 与 specialist summary |
| 图 E2 | `supplementary/supp_fig_quantile_rmse.png` | 参数精度改善是否传递到可靠度寿命？ | E8 `quantiles/summary.csv` |
| 图 F1 | `supplementary/supp_fig_decision_conditions.png` | 参数条件平均、可观测样本规则与逐样本事后信息的确认风险有何差别？ | E10 `mechanism_by_cell.csv`、`confirmation_by_method.csv` 和 `summary.json` |
| 图 F2 | `supplementary/supp_fig_parameter_landscape.png` | 总体改善在 160 个参数条件中如何分布，哪些单元出现退化？ | E5 shared-data 损失扫描与均值归一化折外预测的逐样本配对汇总 |
| 图 F3 | `supplementary/supp_fig_z_only_learning_curve.png` | 灵活 $Z$-only 参照的确认风险是否仍对拟合数据量敏感？ | E10 `learning_curve.csv`；固定确认集，不参与选模 |
| 表 C1、C2 | `tables/supp_table_parameter_guided.*` | 参数引导 12 个单步/迭代变体的 J1、配对 CI 与最佳规则分 beta 结果 | PG 正式产物 `artifacts/formal/pg_selector/`（`paired_bootstrap.csv`、`summary_by_beta.csv`、`variant_summary.csv`） |
| 表 D1 | `tables/supp_table_unseen_beta.*` | 每个留出 beta 的结果 | E8 `unseen_beta/beta_holdout.csv` |
| 表 E1 | `tables/supp_table_traditional.*` | 传统方法参数 Bias/RMSE | E6 `traditional_ref/summary.json` |
| 表 E2 | `tables/supp_table_quantiles.*` | 可靠度寿命 x0.90/x0.95/x0.99 的相对误差 | E8 `quantiles/summary.csv` |

## 投稿版状态

图 1–6 和附录图 C1、D1、E1、E2、F1–F3 均已重画，并导出 PNG/SVG/PDF/TIFF。正文图固定使用 seed 42；初始化稳定性由附录表 B2 报告，未在正文图中重复显示。制图源数据位于 `data/derived/`，图注和 Markdown 引用见 `captions-and-citations.md`，自动 QA 结果见 `provenance/submission_figure_qa.json`。被替换的 E6 有量纲主路线图表、旧版图 2 与旧版图 5 均保存在 `archive/replaced/`。

初始七图包完成三轮视觉检查后，又对正文扩充包完成三轮独立检查。E11 机制图加入后，当前包共含 14 张图、56 个导出文件；旧 E10 条件风险图移入附录，均执行数值和格式检查。

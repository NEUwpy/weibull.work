# Study02 投稿图件

当前版本 v2.6.0：正文采用四张主图，表格单独放在正文或附录。三条路线统一使用 P 灰色、Q 蓝色、QCP 绿色及不同标记；既有历史附录图保留原编码，以各图图例为准。

## 正文图

| 图号 | 文件前缀 | 表达任务 |
|---|---|---|
| 图1 | `main/fig1_research_design` | 共同预测流程和 P→Q→发现代价→QCP 的研究递进 |
| 图2 | `main/fig2_parameter_compensation` | 等寿命点几何、贡献分布及同一预测内的抵消 |
| 图3 | `main/fig3_cross_life_performance` | 三个预设寿命点的总体误差和配对效应区间 |
| 图4 | `main/fig4_cell_heterogeneity` | 全部真值单元的效应分布与目标点净收益构成 |

以上均由 `../tools/figures_v260.py` 生成，提供 PNG、PDF、保留文本的 SVG。来源与输出 SHA、逐样本恒等式检验、分位数及模型单元补偿量见 `../../artifacts/manuscript_figures_v260/`。预测数据来自既有600个配对模型文件，未重新训练。图2分布范围不作为置信区间，图3配对区间沿用既有统计分析。

## 附录图

| 图号 | 文件前缀 | 图源 |
|---|---|---|
| 图B1 | `appendix/figB1_common_budget_results` | `../../figures/qcp-main/fig_qcp_main_results` |
| 图B2 | `appendix/figB2_sample_size_equivalence` | `../../figures/qcp-main/fig_qcp_sample_size_equivalence` |
| 图B3 | `appendix/figB3_extended_reliability` | v2.5.1 原图2；`../tools/review_diagnostics_v250.py` |
| 图C1 | `appendix/figC1_target_sensitivity_mechanism` | `../../figures/pq-paper/fig2_mechanism` |
| 图D1 | `appendix/figD1_error_distribution` | `../../figures/pq-paper/fig3_error_distribution` |

v2.5.1 原稿及完整图件见 `../../归档/旧稿/v2.5.1/`；v2.5.0、v2.4.1 快照也原样保留。当前 `main/` 只保留四张正文图的三个输出格式。历史附录图与同预算结果的统计范围按图注区分。

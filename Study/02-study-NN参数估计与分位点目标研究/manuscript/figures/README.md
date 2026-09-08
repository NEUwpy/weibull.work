# Study02 当前图表索引

2026-09-08现场核对：中文Markdown和DOCX使用`word/`的4张主图、6张附图；英文正文图1用`structure-drawio`英文版，其余英文图在`manuscript/submission/figures/`。两套图布局不同，科学数据来源相同；中文最新Word重绘不等于英文也已重绘。本轮不更换任何现用图片。

| 图 | 中文现用图 | 实验 | 直接数据/原理来源 |
|---|---|---|---|
| 1 | [PNG](word/main/fig1_research_design.png)、[SVG](word/main/fig1_research_design.svg) | [S02-02](../../02-实验配置.md#s02-02) | [网络及监督原理](structure-drawio/study02-framework-zh.drawio) |
| 2 | [PNG](word/main/fig2_parameter_compensation.png)、[SVG](word/main/fig2_parameter_compensation.svg) | [S02-02](../../02-实验配置.md#s02-02) | [验证可行性、贡献分位数与补偿](../../artifacts/manuscript_figures_v270/manifest.json) |
| 3 | [PNG](word/main/fig3_cross_life_performance.png)、[SVG](word/main/fig3_cross_life_performance.svg) | [S02-01](../../02-实验配置.md#s02-01) | [三点精度和配对区间](../../artifacts/qcp_cross_quantile_recovery/analysis/summary.json) |
| 4 | [PNG](word/main/fig4_cell_heterogeneity.png)、[SVG](word/main/fig4_cell_heterogeneity.svg) | [S02-03](../../02-实验配置.md#s02-03) | [单元效应和净收益贡献](../../artifacts/manuscript_review_v250/target_cell_contributions.csv) |
| B1 | [PNG](word/appendix/figB1_common_budget_results.png)、[SVG](word/appendix/figB1_common_budget_results.svg) | [S02-02/04](../../02-实验配置.md#s02-04) | [补偿与选定epoch](../../artifacts/qcp_main_analysis/analysis/model_cells.csv) |
| B2 | [PNG](word/appendix/figB2_sample_size_equivalence.png)、[SVG](word/appendix/figB2_sample_size_equivalence.svg) | [S02-04](../../02-实验配置.md#s02-04) | [样本量及等效观测](../../artifacts/qcp_sample_size_analysis/analysis/summary.json) |
| B3 | [PNG](word/appendix/figB3_extended_reliability.png)、[SVG](word/appendix/figB3_extended_reliability.svg) | [S02-03](../../02-实验配置.md#s02-03) | [较宽R曲线和参数RMSE](../../artifacts/qcp_cross_quantile_recovery/analysis/summary.json) |
| B4 | [PNG](word/appendix/figB4_regional_gains.png)、[SVG](word/appendix/figB4_regional_gains.svg) | [S02-03](../../02-实验配置.md#s02-03) | [真值单元热图](../../artifacts/qcp_cross_quantile_recovery/analysis/truth_cell_effects.csv) |
| C1 | [PNG](word/appendix/figC1_target_sensitivity_mechanism.png)、[SVG](word/appendix/figC1_target_sensitivity_mechanism.svg) | [S02-06](../../02-实验配置.md#s02-06) | [早期静态代理及有限误差分解](../../artifacts/pq_mechanism_closure/analysis/summary.json) |
| D1 | [PNG](word/appendix/figD1_error_distribution.png)、[SVG](word/appendix/figD1_error_distribution.svg) | [S02-07](../../02-实验配置.md#s02-07) | [早期P/Q单侧误差](../../artifacts/pq_engineering_audit/summary.json) |

完整表格来源见[证据索引](../../01-证据索引.md)。图B3的曲线由共同预算参数预测计算，图D1从早期逐预测证据读取；汇总只是入口，原始预测链由生成代码定义。

- 中文生成器：[render_word_figures.py](../tools/render_word_figures.py)，复用[figures_v260.py](../tools/figures_v260.py)、[figures_v270.py](../tools/figures_v270.py)和[paper_figures.py](../../code/study02pq/paper_figures.py)。依赖仓库[panel_labels.py](../../../../scripts/documents/panel_labels.py)。
- 英文生成器：[figures_v270.py](../tools/figures_v270.py)和[标签映射](../tools/figure_english_v270.py)；图1可编辑源：[英文drawio](structure-drawio/study02-framework-en.drawio)、[生成器](structure-drawio/build_neural.py)。
- [Word装配清单](word/assembly-manifest.json)保存当时D盘绝对路径；在worktree验收时按Study02相对后缀定位，不把它误解为另一份数据。清单不回写历史哈希。
- [原图来源及输出清单](../../artifacts/manuscript_figures_v270/manifest.json)与[本轮验证](../../snapshots/2026-09-08/)分别记录历史身份和当前结果。

图2平均约束不是逐预测误差上界；贡献分位数不是置信区间；图4/B4是事后收益定位；C1/D1使用早期300/20。旧`main/appendix`中文图仍是Word装配的来源身份及英文布局参照，不按重复文件自动删除。

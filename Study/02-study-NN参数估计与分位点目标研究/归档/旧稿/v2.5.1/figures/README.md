# Study02 投稿图件

当前正文 v2.5.1 沿用 v2.5.0 图件，本轮 Mentor 复审未改图或数据。v2.5.0 全部图件副本随旧稿存于 `../../归档/旧稿/v2.5.0/figures/`。

本目录只收纳当前正文和附录实际引用的成图。项目级 `../../figures/` 仍是生成输出与历史报告共同使用的位置，不因投稿打包而移动或删除。

## 正文图

| 稿件图号 | 文件前缀 | 项目级图源 |
|---|---|---|
| 图1 | `main/fig1_qcp_geometry_and_evidence` | `../../figures/qcp-main/fig_qcp_geometry_and_evidence` |
| 图2 | `main/fig2_cross_quantile_recovery` | `../tools/review_diagnostics_v250.py`；读取既有跨寿命点分析，统一中文标注与图例 |
| 图3 | `main/fig3_resolution_distribution` | `../tools/review_diagnostics_v250.py`；读取真值单元表，展示 P/QCP 配对风险与累计净收益 |

## 附录图

| 稿件图号 | 文件前缀 | 项目级图源 |
|---|---|---|
| 图B1 | `appendix/figB1_common_budget_results` | `../../figures/qcp-main/fig_qcp_main_results` |
| 图B2 | `appendix/figB2_sample_size_equivalence` | `../../figures/qcp-main/fig_qcp_sample_size_equivalence` |
| 图C1 | `appendix/figC1_target_sensitivity_mechanism` | `../../figures/pq-paper/fig2_mechanism` |
| 图D1 | `appendix/figD1_error_distribution` | `../../figures/pq-paper/fig3_error_distribution` |

v2.5.0 已重新绘制正文图2–3，直接输出于本目录；旧项目级图不覆盖。图1沿用已去除路线连接曲线的版本。图2–3提供PNG、PDF与保留文本的SVG；新结果及源文件SHA位于 `../../artifacts/manuscript_review_v250/`。v2.4.1正文、附录和当时全部图件的快照保存在 `../../归档/旧稿/v2.4.1/`。期刊确定后再调整单栏/双栏尺寸及投稿格式。

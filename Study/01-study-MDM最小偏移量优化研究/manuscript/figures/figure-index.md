# 当前图表—实验配置索引

> 2026-09-08：本索引保持现稿17张图片的实际身份；AMDM新稿图位、去向与缺图统一见[09图表规划](../../09-图表规划与资产匹配.md)。本轮未生成新图，不提前替换旧图号。

2026-09-07；从正文 v1.12 与附录 v1.10 的实际图片链接核对。图表编号按稿件首次出现顺序，资产旧名不代表实验编号。每行的实验链接直接打开对应配置。

| 稿件图号 | 当前实际使用图片 | 实验配置 | 图的作用 | 源文件或最后修订入口 |
|---|---|---|---|---|
| 图 1 | [图片](word/main/fig1_adaptive_selection_drawio_v111.png) | [S01-04](../../02-实验配置.md#s01-04) | 方法流程示意；不含新的数值证据 | [来源](drawio/fig1_adaptive_selection_v111/fig1_adaptive_selection.drawio) |
| 图 2 | [图片](word/main/fig2_offset_risk_decomposition_v112.png) | [S01-01](../../02-实验配置.md#s01-01) | 偏移量风险与条件偏差—方差 | [来源](scripts/plot_offset_revision_v112.py) |
| 图 3 | [图片](word/main/fig3_beta_domain_restored_3d.png) | [S01-02](../../02-实验配置.md#s01-02) | 固定宽度参数域的实际风险格点 | [来源](provenance/restored-3d-figures.json) |
| 图 4 | [图片](word/main/fig4_information_spaces_restored_3d.png) | [S01-03](../../02-实验配置.md#s01-03) | L1—L5 参数空间分组示意 | [来源](provenance/restored-3d-figures.json) |
| 图 5 | [图片](word/main/fig5_information_level_results.png) | [S01-03](../../02-实验配置.md#s01-03) | 不同信息条件的交叉评价与事后风险 | [来源](scripts/plot_fig5_information_level_results.py) |
| 图 6 | [图片](word/main/fig6_per_n_J1.png) | [S01-04](../../02-实验配置.md#s01-04) | 主结果分 n 与逐样本配对损失 | [来源](scripts/make_submission_figures.py) |
| 图 7 | [图片](word/main/fig7_sample_columns_v112.png) | [S01-05A](../../02-实验配置.md#s01-05a) | 同三个样本的参数路径与候选损失 | [来源](scripts/plot_fig7_sample_columns.py) |
| 图 A1 | [图片](word/supplementary/supp_fig_offset_sd_v110.png) | [S01-01](../../02-实验配置.md#s01-01) | 逐参数组合内抽样 SD | [来源](scripts/plot_offset_revision_v112.py) |
| 图 B1 | [图片](word/supplementary/fig7_selector_mechanism.png) | [S01-04](../../02-实验配置.md#s01-04) | 预测曲线、选点对应与超额损失 | [来源](scripts/make_submission_figures.py) |
| 图 C1 | [图片](word/supplementary/supp_fig_parameter_guided.png) | [S01-07](../../02-实验配置.md#s01-07) | 初估查表12变体及分层结果 | [来源](scripts/make_submission_figures.py) |
| 图 D1 | [图片](word/supplementary/supp_fig_unseen_beta_v111.png) | [S01-06A](../../02-实验配置.md#s01-06a) | 未见 β 层的参数精度 | [来源](scripts/clean_annotations_v111.py) |
| 图 E1 | [图片](word/supplementary/supp_fig_traditional_per_n.png) | [S01-06B](../../02-实验配置.md#s01-06b) | 传统参照的分 n 结果 | [来源](scripts/make_submission_figures.py) |
| 图 E2 | [图片](word/supplementary/supp_fig_quantile_rmse_v111.png) | [S01-06C](../../02-实验配置.md#s01-06c) | 三个可靠度寿命的相对 RMSE | [来源](scripts/clean_annotations_v111.py) |
| 图 F1 | [图片](word/supplementary/supp_fig_decision_conditions.png) | [S01-05B](../../02-实验配置.md#s01-05b) | 条件风险经验参照 | [来源](scripts/make_submission_figures.py) |
| 图 F2 | [图片](word/supplementary/supp_fig_parameter_landscape_v111.png) | [S01-04](../../02-实验配置.md#s01-04) | 主选择器在160单元的效果分布 | [来源](scripts/clean_annotations_v111.py) |
| 图 F3 | [图片](word/supplementary/supp_fig_z_only_learning_curve_v111.png) | [S01-05B](../../02-实验配置.md#s01-05b) | 经验参照的训练数据量诊断 | [来源](scripts/clean_annotations_v111.py) |
| 图 F4 | [图片](word/supplementary/supp_fig_sample_groups_v110.png) | [S01-05A](../../02-实验配置.md#s01-05a) | 样本分组与单元内关联 | [来源](scripts/plot_offset_revision_v112.py) |

## 正文表格

| 当前表号 | 内容 | 实验配置 | 对应数据 |
|---|---|---|---|
| 表 1 | Monte Carlo 设计 | [共用配置](../../02-实验配置.md#common) | [table1_mc_design.csv](tables/table1_mc_design.csv) |
| 表 2 | 信息条件风险 | [S01-03](../../02-实验配置.md#s01-03) | [table1_l1_l6.csv](tables/table1_l1_l6.csv) |
| 表 3 | 主比较及分 n 结果 | [S01-04](../../02-实验配置.md#s01-04) | [table2_main_results.csv](tables/table2_main_results.csv) |
| 表 4 | 汇总标准化参数误差 | [S01-04](../../02-实验配置.md#s01-04) | [table4_parameter_metrics.csv](tables/table4_parameter_metrics.csv) |

附录表格跟随[正文—证据索引](../../01-证据索引.md)中相应章节的实验。表 4 的 SD 是混合设计误差 SD，不能代替图 2/图 A1 的单元内抽样方差。

## 重绘与来源

上表列的是最后修订或恢复入口，不承诺任一脚本独立生成整套当前图件。基础数值图来自 make_submission_figures.py；注释修订、三维恢复、图 2 与图 7 的专用程序共同形成当前版本。排版版本由 [render_word_figures.py](scripts/render_word_figures.py)处理。[figure_sources.json](figure_sources.json)保留原始机器来源，旧编号不回写。

当前共有 7 张正文图和 10 张附图。历史图和复核图不计入当前稿件；已清理的旧 TIFF 不再视为当前必备资产。本轮没有重绘或改变图像内容。

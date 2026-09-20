# 新稿 v2.0 图表索引

更新：2026-09-20。按[新稿](../Study01论文新稿-v2.0.md)的章节与论证用途编排。F01—F06 是新稿规划图位，不表示六张成图已经完成；当前正文仍嵌入六张旧图素材，标题中的旧图号暂保留为来源标识，定稿时再统一连续编号。

## 正文图位

| 新图位／章节 | 用途 | 保留素材及实验 | 完成状态与缺项 | 生成／来源入口 |
|---|---|---|---|---|
| F01 · [2.2 方法流程](../Study01论文新稿-v2.0.md#sec-2-2) | 样本输入、损失预测、选偏移与MDM求解 | [旧图1](word/main/fig1_adaptive_selection_drawio_v111.png)；[S01-04](../../02-实验配置.md#s01-04) | 已有流程图；需统一AMDM名称、核定模型身份后修订 | [可编辑源](drawio/fig1_adaptive_selection_v111/fig1_adaptive_selection.drawio) |
| F02 · [4.1 固定偏移](../Study01论文新稿-v2.0.md#sec-4-1) | 风险分解及参数域变化 | [旧图2](word/main/fig2_offset_risk_decomposition_v112.png)、[旧图3](word/main/fig3_beta_domain_restored_3d.png)；[S01-01](../../02-实验配置.md#s01-01)、[S01-02](../../02-实验配置.md#s01-02) | 两张素材均已有，尚未合并或重排 | [风险图程序](scripts/plot_offset_revision_v112.py)、[三维图来源](provenance/restored-3d-figures.json) |
| F03 · [4.2 实际选点](../Study01论文新稿-v2.0.md#sec-4-2) | 同条件样本路径、固定点与实际AMDM点 | [旧图7](word/main/fig7_sample_columns_v112.png)；[S01-05a](../../02-实验配置.md#s01-05a) | 部分已有：现图只有固定点与L6；缺折外AMDM点和样本匹配诊断，不能把L6当AMDM | [现图程序](scripts/plot_fig7_sample_columns.py)、[P01](../../04-后续实验计划.md#p01) |
| F04 · [4.3 方法比较](../Study01论文新稿-v2.0.md#sec-4-3) | AMDM与基准的总体及分n表现 | [旧图6](word/main/fig6_per_n_J1.png)、[旧附图E1](word/supplementary/supp_fig_traditional_per_n.png)；[S01-04](../../02-实验配置.md#s01-04)、[S01-06b](../../02-实验配置.md#s01-06b) | 旧共同样本结果已有；冻结后的共同独立确认尚缺，素材尚未合并 | [旧结果绘图程序](scripts/make_submission_figures.py)、[P03](../../04-后续实验计划.md#p03) |
| F05 · [4.4 精度与稳定性](../Study01论文新稿-v2.0.md#sec-4-4) | AMDM单元内Bias、SD、RMSE与尾部 | 尚无符合本图目的的成图；既有[参数汇总表](tables/table4_parameter_metrics.csv)只供对照 | 待分析、待绘；混合设计SD不能替代单元内SD，也不能以固定偏移分解代替AMDM分析；可并入T03 | [P02](../../04-后续实验计划.md#p02) |
| F06 · [4.5 范围与退化](../Study01论文新稿-v2.0.md#sec-4-5) | 单元异质性、β留出及适用范围 | [旧附图D1](word/supplementary/supp_fig_unseen_beta_v111.png)、[旧附图F2](word/supplementary/supp_fig_parameter_landscape_v111.png)；[S01-04](../../02-实验配置.md#s01-04)、[S01-06a](../../02-实验配置.md#s01-06a) | 旧离散设计素材已有，尚未嵌入本节；新确认及获准的范围扩展未完成 | [现图修订程序](scripts/clean_annotations_v111.py)、[扩展取舍](../../04-后续实验计划.md#p04) |

## 附录与讨论的保留素材

这些是新稿仍可调用的证据素材；附录编号尚未重编。旧名用于定位文件，不表示新稿另有一套已定稿图序。

| 新稿用途 | 保留图片（旧号） | 实验 | 生成／来源入口 |
|---|---|---|---|
| 3.2、5.2 信息条件说明，附录候选 | [旧图4](word/main/fig4_information_spaces_restored_3d.png) | [S01-03](../../02-实验配置.md#s01-03) | [三维图来源](provenance/restored-3d-figures.json) |
| 3.2、5.2 信息条件风险，附录候选 | [旧图5](word/main/fig5_information_level_results.png) | [S01-03](../../02-实验配置.md#s01-03) | [程序](scripts/plot_fig5_information_level_results.py) |
| 4.1 固定偏移的单元内SD支撑 | [旧附图A1](word/supplementary/supp_fig_offset_sd_v110.png) | [S01-01](../../02-实验配置.md#s01-01) | [程序](scripts/plot_offset_revision_v112.py) |
| 2.2、4.2 损失预测与选点诊断 | [旧附图B1](word/supplementary/fig7_selector_mechanism.png) | [S01-04](../../02-实验配置.md#s01-04) | [程序](scripts/make_submission_figures.py) |
| 5.2 简单查表的负结果 | [旧附图C1](word/supplementary/supp_fig_parameter_guided.png) | [S01-07](../../02-实验配置.md#s01-07) | [程序](scripts/make_submission_figures.py) |
| 5.3 可靠度寿命与参数收益的区别 | [旧附图E2](word/supplementary/supp_fig_quantile_rmse_v111.png) | [S01-06c](../../02-实验配置.md#s01-06c) | [修订程序](scripts/clean_annotations_v111.py) |
| 5.2 可观测信息的经验参照 | [旧附图F1](word/supplementary/supp_fig_decision_conditions.png) | [S01-05b](../../02-实验配置.md#s01-05b) | [程序](scripts/make_submission_figures.py) |
| 5.2 经验参照训练量诊断 | [旧附图F3](word/supplementary/supp_fig_z_only_learning_curve_v111.png) | [S01-05b](../../02-实验配置.md#s01-05b) | [修订程序](scripts/clean_annotations_v111.py) |
| 4.2 样本分组与路径关联支撑 | [旧附图F4](word/supplementary/supp_fig_sample_groups_v110.png) | [S01-05a](../../02-实验配置.md#s01-05a) | [程序](scripts/plot_offset_revision_v112.py) |

## 新稿表位

| 表位／章节 | 内容及已有来源 | 尚需补充 |
|---|---|---|
| T01 · 3.1 | 数据设计；[旧表1](tables/table1_mc_design.csv)、[共用配置](../../02-实验配置.md#common) | 开发与新确认的区别；最终确认设计尚待确定 |
| T02 · 2.2、3.2 | 方法与信息定义；[旧信息层级表](tables/table1_l1_l6.csv)、[配置](../../02-实验配置.md) | 原始MDM身份、最终模型、基准名单与失败评分；见[P00](../../04-后续实验计划.md#p00) |
| T03 · 4.3、4.4 | 参数性能；[旧主结果](tables/table2_main_results.csv)、[旧参数误差](tables/table4_parameter_metrics.csv) | 共同独立确认、AMDM单元内误差与尾部；旧混合SD不充当稳定性结论 |

## 资产与复现

共保留17个图主题的排版PNG/SVG及已有基础导出；其中8个主题为正文规划素材、9个供附录或讨论调用。实际新稿目前插入6张图片，不以保留数量冒充完成数量。

`word/` 是稿件引用图；`main/`、`supplementary/` 保存这些主题的基础导出；`drawio/` 保留可编辑源及必要依赖；`data/`、`tables/` 和历史CSV保持不变。本轮只清理旧图与更新映射，没有重绘或重跑实验。

[figure_sources.json](figure_sources.json)的 `current_manuscript` 记录新稿映射；旧字段供原生成器和来源追溯使用，不是新稿图序。[清理记录](provenance/figure-cleanup-20260920.md)说明移除范围和Git恢复版本。生成器各有职责，不能假定任一旧脚本能一次恢复所有当前修订。

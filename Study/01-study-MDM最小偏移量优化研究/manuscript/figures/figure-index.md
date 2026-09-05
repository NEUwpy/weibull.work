# 图表—结论—数据索引

当前版本：正文 v1.11、附录 v1.9。稿件图号按首次出现排序；资产文件名保留原名，文件名中的数字不再代表当前稿件图号。

| 稿件图号 | 图像资产 | 职责与数据 |
|---|---|---|
| 图 1 | `main/fig1_adaptive_selection_drawio_v111.png` | 样本自适应偏移量选择方法；方法定义（示意曲线不作为数值证据） |
| 图 2 | `main/fig2_offset_baseline_combined.png` | 正偏移量对估计稳定性和联合误差的影响；共享扫描，160 组合内重复抽样 SD 与 26 点风险 |
| 图 3 | `main/fig3_beta_domain_sensitivity.png` | 固定宽度参数域对统一偏移量的影响；E13：11 个参数域 × 26 个候选实际风险 |
| 图 4 | `main/fig5_information_level_results.png` | 不同信息条件下的估计风险；L1—L6 交叉评价与事后参照 |
| 图 5 | `main/fig6_per_n_J1.png` | 不同样本量下的总体与逐样本结果；E8 seed 42 折外结果及逐样本配对损失 |
| 图 6 | `main/fig8_decision_mechanism.png` | 有限样本波动与 MDM 偏移量选择；E11：20 单元、2,000 样本的轨迹与相关 |
| 图 B1 | `main/fig7_selector_mechanism.png` | 从损失曲线预测到偏移量选择；折外曲线预测、行内归一化选点对应与超额损失 |
| 图 C1 | `supplementary/supp_fig_parameter_guided.png` | 利用初估参数选择偏移量的评价；plug-in 12 变体 |
| 图 D1 | `supplementary/supp_fig_unseen_beta_v111.png` | 未见形状参数水平验证；E8 未见形状参数留出 |
| 图 E1 | `supplementary/supp_fig_traditional_per_n.png` | 传统方法的分样本量参照；同样本 WMLE/LSE |
| 图 E2 | `supplementary/supp_fig_quantile_rmse_v111.png` | 可靠度寿命误差；三个可靠度寿命的相对 RMSE |
| 图 F1 | `supplementary/supp_fig_decision_conditions.png` | 不同决策条件下的确认风险；同域确认风险与信息条件 |
| 图 F2 | `supplementary/supp_fig_parameter_landscape_v111.png` | 参数条件下的效果分布；160 单元效果分布 |
| 图 F3 | `supplementary/supp_fig_z_only_learning_curve_v111.png` | $Z$-only 经验参照的数据量诊断；同域经验参照的数据量诊断 |

原图 A1 的分组定义已改为可编辑表 A2；图像资产 `fig4_information_spaces` 仅留作复核。

正文表 1—4 依次为设计、信息条件风险、主比较和汇总标准化参数误差。表 4 的 SD 为混合设计误差 SD，不是逐条件抽样 SD。

来源路径由 `figure_sources.json` 管理，数值与导出清单见 `provenance/`。稳定资产 `fig9_support_validation` 和 `supp_fig_seed_stability` 仅供复核，不进入当前稿件。

修订前完整稿件、图表、生成器和来源清单见 `archive/replaced/pre-v1.8-20260905/`。

v1.9 仅调整叙述与证据位置，图像未改动；完整上一版本快照见 `archive/replaced/pre-v1.9-20260905/`。v1.10 补回必要论述，图件仍未改动；当前修订说明见 [修订说明-v1.10](../shelve/修订记录/修订说明-v1.10.md)。

图 1 于 2026-09-05 按作者要求改用 draw.io 重绘；[可编辑源文件](drawio/fig1_adaptive_selection/fig1_adaptive_selection.drawio)。原 fig2_adaptive_selection_method 图件保留，其他图不变。

图 2 合并原 a、b：当前 a 为完整候选误差曲线及最低点/固定值标注，当前 b 为原 c 的组合内抽样波动分布；删除局部放大，原图保留。

## v1.11 注释清理

当前图 1 的可编辑源文件为 `drawio/fig1_adaptive_selection_v111/fig1_adaptive_selection.drawio`。图 1 及附图 D1、E2、F2、F3 删除重复备注；符号、阴影和误差线的含义集中写入图注。F3 横轴修正为每个样本量模型的训练样本数。旧版资产保留，当前映射见 `figure_sources.json`。图 2 沿用两面板合并版，其余数据图沿用原文件。

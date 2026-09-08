# 当前图表索引

中文正文/附录v0.2，2026-09-08。全部图件由[同一绘图程序](../../code/render_manuscript_figures.py)读取9个封存CSV生成；PNG用于Markdown，PDF/SVG用于排版。原图及源CSV字节保持不变。

| 图号 | 实验 | 图件 | 直接源CSV |
|---|---|---|---|
| 图1 | [R04-01](../../02-实验配置.md#r04-01) | [PNG](fig1_domain_risk.png) / [PDF](fig1_domain_risk.pdf) / [SVG](fig1_domain_risk.svg) | [beta_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/beta_summary.csv)、[paired_bootstrap_contrasts.csv](../../artifacts/study01_aligned_generalization_v1/analysis/paired_bootstrap_contrasts.csv) |
| 图2 | [R04-02](../../02-实验配置.md#r04-02) | [PNG](fig2_centered_width.png) / [PDF](fig2_centered_width.pdf) / [SVG](fig2_centered_width.svg) | [width_common_beta_summary.csv](../../artifacts/training_domain_width_location_v1/analysis/width_common_beta_summary.csv) |
| 图3 | [R04-03](../../02-实验配置.md#r04-03) | [PNG](fig3_parameter_rmse.png) / [PDF](fig3_parameter_rmse.pdf) / [SVG](fig3_parameter_rmse.svg) | [beta_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/beta_summary.csv) |
| 图4 | [R04-03](../../02-实验配置.md#r04-03) | [PNG](fig4_mdm_diagnostic.png) / [PDF](fig4_mdm_diagnostic.pdf) / [SVG](fig4_mdm_diagnostic.svg) | [beta_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/beta_summary.csv)、[mdm_identifiability_sensitivity.csv](../../artifacts/study01_aligned_generalization_v1/analysis/mdm_identifiability_sensitivity.csv) |
| 图5 | [R04-03](../../02-实验配置.md#r04-03) | [PNG](fig5_sample_size.png) / [PDF](fig5_sample_size.pdf) / [SVG](fig5_sample_size.svg) | [n_domain_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/n_domain_summary.csv)、[paired_bootstrap_contrasts.csv](../../artifacts/study01_aligned_generalization_v1/analysis/paired_bootstrap_contrasts.csv) |
| 图A1 | [R04-03](../../02-实验配置.md#r04-03) | [PNG](figS1_n_by_beta.png) / [PDF](figS1_n_by_beta.pdf) / [SVG](figS1_n_by_beta.svg) | [n_beta_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/n_beta_summary.csv) |
| 图A2 | [R04-04](../../02-实验配置.md#r04-04) | [PNG](figS2_nested_tradeoff.png) / [PDF](figS2_nested_tradeoff.pdf) / [SVG](figS2_nested_tradeoff.svg) | [common_core_bootstrap.csv](../../artifacts/training_domain_width_v1/analysis/common_core_bootstrap.csv) |
| 图A3 | [R04-04](../../02-实验配置.md#r04-04) | [PNG](figS3_nested_extrapolation.png) / [PDF](figS3_nested_extrapolation.pdf) / [SVG](figS3_nested_extrapolation.svg) | [beta_summary.csv](../../artifacts/training_domain_width_v1/analysis/beta_summary.csv)、[beta_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/beta_summary.csv) |
| 图A4 | [R04-06](../../02-实验配置.md#r04-06) | [PNG](figS4_input_geometry.png) / [PDF](figS4_input_geometry.pdf) / [SVG](figS4_input_geometry.svg) | [sample_geometry_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/sample_geometry_summary.csv) |

图1/5的CI属于基础三方案、图A2的CI属于先行嵌套设计；图2没有CI。图A4阴影为IQR。完整来源哈希、行数、字节副本见[source-data-manifest.json](source-data-manifest.json)，原技术/视觉核验见[figure-qa.json](figure-qa.json)。本轮未重绘图像。

## 表格来源

| 表号 | 实验 | 来源 |
|---|---|---|
| 表1 | [R04-01](../../02-实验配置.md#r04-01) | [manifest.json](../../artifacts/study01_aligned_generalization_v1/manifest.json) |
| 表2 | [R04-01](../../02-实验配置.md#r04-01) | [combined_domain_summary.csv](../../artifacts/traditional_aligned_v1/combined_domain_summary.csv) |
| 表3 | [R04-02](../../02-实验配置.md#r04-02) | [width_common_beta_summary.csv](../../artifacts/training_domain_width_location_v1/analysis/width_common_beta_summary.csv) |
| 表4 | [R04-03](../../02-实验配置.md#r04-03) | [combined_domain_summary.csv](../../artifacts/traditional_aligned_v1/combined_domain_summary.csv) |
| 表A1 | [R04-01](../../02-实验配置.md#r04-01) | [combined_beta_summary.csv](../../artifacts/traditional_aligned_v1/combined_beta_summary.csv) |
| 表A2 | [R04-03](../../02-实验配置.md#r04-03) | [n_domain_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/n_domain_summary.csv) |
| 表A3 | [R04-03](../../02-实验配置.md#r04-03) | [large_beta_summary.csv](../../artifacts/study01_aligned_generalization_v1/analysis/large_beta_summary.csv) |
| 表A4 | [R04-02](../../02-实验配置.md#r04-02) | [location_aligned_summary.csv](../../artifacts/training_domain_width_location_v1/analysis/location_aligned_summary.csv) |
| 表A5 | [R04-05](../../02-实验配置.md#r04-05) | [pooled_scale_summary.csv](../../artifacts/scale_equivariance_v1/pooled_scale_summary.csv) |

表1为设计表；其余8表201个显示数值由[数值检查](../v0.2-numeric-verification.json)核对。[章节对应](../../01-证据索引.md)和[统一配置](../../02-实验配置.md)提供返回正文/附录的直接锚点。

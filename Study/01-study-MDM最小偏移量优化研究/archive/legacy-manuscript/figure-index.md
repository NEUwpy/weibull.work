# G5 Manuscript Figure Index

> 冻结日期：2026-07-26
> 基线：P10 APPROVE @ `8ef74b8`
> 状态：图 1–9 与补充图 S1–S8 均已生成并通过数据口径核对；生成结果保证数据与视觉逻辑可复现，不承诺跨环境字节完全一致。

## 主图

| # | 标题 | 主张 | 位置 | 来源 | 数据提交 | 文件 | 核对 |
|---|------|------|------|------|---------|------|------|
| 1 | MDM offset mechanism | δ改变搜索判据并系统性改变估计分布 | §2 | E1 MC, W(2,1,1)等价 | `21876c79` | fig_offset_mechanism.{png,svg,pdf} | ✅ |
| 2 | L1 global delta risk curve | L1最优δ依赖β和n；固定0.1非全局最优 | §3.1 | E1 baseline | `21876c79` | fig2_delta_risk_curve.{png,svg,pdf} | ✅ |
| 3 | L2 delta by n heterogeneity | L2按n查表提升极小 | §3.1 | E1/E2-CF | `8d88b789` | fig_l2_n_heterogeneity.{png,svg,pdf} | ✅ |
| 4 | L3-L6 oracle ladder | L2→L5组级信息增益与L5→L6 hindsight gap应分开解释 | §3.2 | E2 oracle layers | `21876c79` | fig3_ladder.{png,svg,pdf} | ✅ |
| 5 | Vector-MLP-L6 workflow | 样本自适应选择方法 | §3.3 | E3b | `bedd65a8` | fig_ch6_vector_mlp_workflow.{png,svg,pdf} | ✅ |
| 6 | Feature ablation | scale_quantile子集保留了full的大部分表现 | §3.4 | E4a | `86d3f8d6` | fig6_feature_ablation.{png,svg,pdf} | ✅ |
| 7 | Boundary/off-grid extrapolation | Boundary轨道退化，off-grid轨道相对接近主网格表现 | §3.4 | E4d/R1 | `25cf7e2` | fig7_boundary_offgrid.{png,svg,pdf} | ✅ |
| 8 | Delta upper bound audit | 端点cohort 94.66%迁移至δ>0.50 | §3.4 | R2 | `7d6e99f` | fig8_upper_bound_audit.{png,svg,pdf} | ✅ |
| 9 | Real data: Default/L2/NN | NN在该数据集上未优于Default/L2 | §3.5 | P6-P8 | `7946108` | fig9_real_data_comparison.{png,svg,pdf} | ✅ |

## 补充图

| # | 标题 | 补充 | 来源 | 文件 | 核对 |
|---|------|------|------|------|------|
| S1 | Cross-fit sensitivity | §3.1-3.2 | E1/E2-CF | fig_s1_crossfit.{png,svg,pdf} | ✅ |
| S2 | Beta-profile audit | §3.2 | E2 beta profile | fig_s2_beta_profile.{png,svg,pdf} | ✅ |
| S3 | Three-seed stability | §3.3 | E3b | fig_s3_seed_stability.{png,svg,pdf} | ✅ |
| S4 | Feature ablation by fold | §3.4 | E4a | fig_s4_ablation_folds.{png,svg,pdf} | ✅ |
| S5 | Boundary/off-grid by fold/seed | §3.4 | E4d | fig_s5_boundary_folds.{png,svg,pdf} | ✅ |
| S6 | R2 full conditional distribution | §3.4 | R2 | fig_s6_upper_bound_dist.{png,svg,pdf} | ✅ |
| S7 | NN 15-model per-n distribution | §3.5 | P6-P8 | fig_s7_nn_15model_dist.{png,svg,pdf} | ✅ |
| S8 | Support-set violation details | §3.5 | P6-P8 | fig_s8_support_set.{png,svg,pdf} | ✅ |

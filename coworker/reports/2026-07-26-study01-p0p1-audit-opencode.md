# Study01 P0-P1 审计与证据重分析报告

> 执行者：OpenCode
> 日期：2026-07-26
> 分支：study01xu @ ad4dbdb4
> 状态：READY_FOR_INDEPENDENT_REVIEW

## P0. 基线与合同审计

### 0.1 正式产物清单（全部存在且 manifest 可读）

| 模块 | Run ID | Git Commit | 状态 |
|------|--------|------------|------|
| shared_data | E1E2_mc_scan_v1 | 9fad6af | done (1.17M rows) |
| E1_baseline | E1_baseline_v1 | 3a35abc | done |
| E2_oracle_layers | E2_oracle_layers_v1 | 713ba48 | done |
| E3b_vector_mlp | E3b_vector_mlp_v1 | 04e99c5 | done |
| E4_robustness (a) | E4_formal_validation_v1 | 0147baa | FORMAL |
| E4_robustness (b/c) | E4_formal_validation_v1 | 831a8b4 | FORMAL |
| E4_robustness (d) | E4d_selector_extrapolation | seal: 5c63a690 | FORMAL, E3b gate PASS |
| delta_upper_bound | delta_upper_bound_audit | 76906a98 | done |
| P8 NIST | real_data_holdout | 3330523 | done (25,500 rows, gate PASS) |

### 0.2 传统方法实现

MLE (`python/methods/mle.py`)、LSE (`python/methods/lse.py`)、WMLE (`python/methods/wmle.py`) 均已实现。运行接口: `method = MLE(data); result = method.run()`，返回 `[beta, eta, gamma, r2, converged]`。

### 0.3 工程分位点实现

`python/studies/common/metrics.py` 提供 `quantile_est(beta, eta, gamma, R)`、`quantile_true(beta, eta, gamma, R)`、`quantile_relative_error(est, true)`。可用于 P5 从逐样本三参数估计派生工程寿命分位点。

### 0.4 E4d 泛化标签机械分类

对 `E4d_selector_extrapolation.csv`（295,000 行）按冻结协议 §5.2 规则生成标签：

| 标签 | 行数 | % | 来源 |
|------|------|---|------|
| p_interp（参数插值） | 34,500 | 11.7% | E4c_offgrid |
| n_interp（样本量插值） | **0** | **0.0%** | — |
| p_extrap（参数外推） | 107,500 | 36.4% | E4b_boundary + E4c_offgrid |
| n_extrap（样本量外推） | 59,500 | 20.2% | E4b_boundary + E4c_offgrid |
| multi_extrap（多轴外推） | 93,500 | 31.7% | E4b_boundary + E4c_offgrid |

## P1. 现有证据重分析

### 1.1 E4a 特征组消融（内部可信性）

| 特征组 | mean J1 | sd | delta vs full |
|--------|---------|-----|---------------|
| full (13特征) | **0.5456** | 0.0102 | baseline |
| scale_quantile (9特征) | 0.5506 | 0.0119 | +0.9% |
| shape (3特征) | 0.5816 | 0.0211 | +6.6% |
| n_only (仅n) | 0.6378 | 0.0195 | +16.9% |

**Seed 稳定性（full组）**: max spread 0.003 (seed=42 → 0.5469, 2026 → 0.5460, 3407 → 0.5439)。

**结论**：现有 E4a 证据足以回答内部可信性问题——去除尺度/分位特征仅有 0.9% 退化，去除形状特征退化 6.6%，仅凭 n 不可用。seed 稳定性良好。

### 1.2 E4d 分轴泛化（Vector-MLP-L6 在每轴的表现）

| 轴 | rows | J1 | regret_mean | 相对主域 0.547 的变化 |
|----|------|-----|-------------|---------------------|
| p_interp | 30,000 | **0.4830** | 0.0456 | -11.7%（表现更优） |
| n_interp | **0** | — | — | **无数据** |
| p_extrap | 90,000 | 0.5661 | 0.0555 | +3.5% |
| n_extrap | 52,500 | 0.6023 | 0.0873 | +10.1% |
| multi_extrap | 82,500 | 0.5917 | 0.0954 | +8.2% |

### 1.3 与参考方法的配对比较（同轴）

Vector-MLP-L6 在所有有数据的轴上均优于 Default/L1/L2：

| 轴 | Default | L1 | L2 | L6-hindsight | Vector-MLP-L6 |
|----|---------|-----|-----|-------------|---------------|
| p_interp | 0.5452 | 0.5659 | 0.5237 | 0.4333 | **0.4830** |
| p_extrap | 0.6841 | 0.6433 | 0.5834 | 0.5147 | **0.5661** |
| n_extrap | 0.6803 | 0.6413 | 0.6238 | 0.5249 | **0.6023** |
| multi_extrap | 0.6600 | 0.6249 | 0.6116 | 0.5047 | **0.5917** |

## 结论：现有证据能回答哪些问题

| 问题 | 证据来源 | 状态 |
|------|----------|------|
| 内部可信性（特征组+seed） | E4a, 60 rows, 4 groups × 15 models | **充分** |
| 参数插值泛化 | E4d p_interp, 4 combos | **不足**（4个组合不够独立判断） |
| 样本量插值泛化 | 无 | **完全缺失**（n=15 仅有 E4c_offgrid 非 on-grid 参数） |
| 参数外推 | E4d p_extrap, 12 combos + E4b reference | **充分** |
| 样本量外推 | E4d n_extrap, 7 combos + E4b reference | **充分** |
| 多轴外推 | E4d multi, 11 combos + E4b reference | **充分** |

## P2 最小补点建议

### 必须（否则无法回答）

**n_interp**: 在所有 45 个训练网格组合上增加 `n=15`：
- 参数空间：`beta∈{1.5,2.0,2.5,4.0,5.0} × gamma/eta∈{0.1,0.5,1.0} × n=15`
- 每个组合 1000 repeats
- 总计 45,000 MDM 估计
- 复用现有 `code/generate_mc_data.py` 和确定性 seed 合同

### 建议（增强独立性）

**p_interp**: 增加 6-8 个非网格参数组合（`n∈{7,10,20}`）：
- 在 `beta∈[1.5,5.0]`、`gamma/eta∈[0.1,1.0]` 范围内均匀分布
- 每个组合 1000 repeats
- 总计 18,000-24,000 MDM 估计

### 不需要补的

**p_extrap、n_extrap、multi_extrap**：E4b_boundary + E4c_offgrid 已有充分覆盖。

## 审计脚本与产物

- `scripts/audit_study01_p0p1.py` — 主审计脚本
- `scripts/audit_study01_generalization.py` — 泛化标签分类脚本

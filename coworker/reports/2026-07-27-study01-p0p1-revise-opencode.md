# Study01 P0-P1 REVISE 审计与证据重分析报告

> 执行者：OpenCode
> 日期：2026-07-27
> 分支：study01xu
> 状态：READY_FOR_INDEPENDENT_REVIEW

## P0. 实质核验

### 0.1 Manifest SHA256 验证

11 个正式 manifest 全部存在，SHA256 已记录（见 `scripts/audit_study01_p0p1_v2.py` 输出）。

### 0.2 样本键验证

- 每 fold×seed 有 17,000 个唯一 `(beta,ge,n,repeat)` 键
- 15 个模型使用完全相同的样本键集（fold/seed cross 一致性通过）
- 重复键 = 15（每键对应 15 个模型的预测），符合预期

### 0.3 Model Count

15 个 model (5 folds × 3 seeds [42, 2026, 3407]) — 确认。

### 0.4 E3b Gate

| Gate | 状态 |
|------|------|
| gate1_fold_partition | — |
| gate2_seed42_per_sample | — |
| gate3_three_seed_summary | — |
| **overall_pass** | **PASS** |

### 0.5 E3b 输入产物

- `manifest.json` ✓
- `summary.json` ✓
- `vector_mlp_results.csv` ✓

### 0.6 P8 NIST Gate

- `real_data_manifest.json` ✓
- `real_holdout_results.csv` ✓ (25,500 rows, expected 25,500)
- `real_holdout_summary.json` ✓
- Failure rate: 0.0%（全合法估计）
- gate PASS（R²=0.995）

## P1. 正交分类与分层分析

### 1.1 分类方法

正交分解 `parameter_state ∈ {on_grid, interp, extrap} × n_state ∈ {on_grid, interp, extrap}`，9 种状态组合。

代码：`code/gen_labels.py`，fail-closed 单元测试：`tests/test_gen_labels.py`（29 tests passed）。

### 1.2 E4d 正交分类分布

| param_state | n_state | rows | % | 纯轴？ |
|---|---|---|---|---|
| extrap | extrap | 82,500 | 32.4% | mixed |
| extrap | interp | 7,500 | 2.9% | mixed |
| extrap | on_grid | 82,500 | 32.4% | **pure p_extrap** |
| interp | extrap | 22,500 | 8.8% | mixed |
| interp | interp | 22,500 | 8.8% | mixed |
| interp | on_grid | 7,500 | 2.9% | **pure p_interp** |
| on_grid | extrap | 30,000 | 11.8% | **pure n_extrap** |
| on_grid | interp | **0** | **0.0%** | **MISSING** |
| on_grid | on_grid | 0 | 0.0% | (training grid) |

### 1.3 15-Model 分层分析（Vector-MLP-L6）

每个 combound label 按 15 个 fold×seed 模型分别计算 J1，报告 min/Q1/median/Q3/max/mean/SD：

| compound | rows | mean J1 | SD | vs Default win | vs L1 win |
|----------|------|---------|-----|---------------|-----------|
| p_extrap_n_extrap | 82,500 | 0.5916 | 0.0126 | 15/0/0 | 15/0/0 |
| p_extrap_n_interp | 7,500 | 0.5717 | 0.0144 | 15/0/0 | 15/0/0 |
| p_extrap_n_on_grid | 82,500 | 0.5655 | 0.0075 | 15/0/0 | 15/0/0 |
| p_interp_n_extrap | 22,500 | 0.5842 | 0.0118 | 15/0/0 | 15/0/0 |
| p_interp_n_interp | 22,500 | 0.4429 | 0.0046 | 15/0/0 | 15/0/0 |
| p_interp_n_on_grid | 7,500 | 0.5870 | 0.0072 | 15/0/0 | 15/0/0 |
| p_on_grid_n_extrap | 30,000 | 0.6153 | 0.0140 | 15/0/0 | **14/1/0** |

### 1.4 纯轴覆盖

| 纯轴 | combos | 证据状态 |
|------|--------|----------|
| pure_p_interp (p=interp, n=on_grid) | 1 combo | 不足 |
| **pure_n_interp** (p=on_grid, n=interp) | **0** | **完全缺失** |
| pure_p_extrap (p=extrap, n=on_grid) | 11 combos | 可覆盖 |
| pure_n_extrap (p=on_grid, n=extrap) | 4 combos | 可覆盖 |

### 1.5 与 Default/L1 配对比较结论

Vector-MLP-L6 在**所有有数据的轴**上均优于 Default 和 L1（14-15/15 模型级 wins）。仅在 `p_on_grid_n_extrap` 轴上有 1/15 模型对 L1 为 tie。

## P2 修正建议

### 必须（否则无法回答 pure_n_interp）

**n=15 纯样本量插值**：
- 参数空间：45 个训练网格组合（`beta∈{1.5,2.0,2.5,4.0,5.0} × gamma/eta∈{0.1,0.5,1.0}`）
- 样本量：`n=15`（单值）
- **口径区分**：15 个参数组合 × 1 个 n 值 = **15 个组合**；每个组合 1000 repeats = **15,000 个抽样样本**；每个样本运行 26 个 delta 值 = **390,000 次 MDM 评估**
- 复用现有 `code/generate_mc_data.py`，不新增 LSE/LRE/WMLE

### 建议（增强 pure_p_interp 独立性）

**参数插值补点**：
- 6-8 个新参数组合，参数在域内但不在训练格点上
- 每个组合在 `n∈{7,10,20}` 三个样本量下各 1000 repeats
- 总计 6-8 个参数对 × 3 个 n = **18-24 个组合**，18,000-24,000 个抽样样本

### 不需要补

**pure_p_extrap、pure_n_extrap、混合轴**：E4b_boundary + E4c_offgrid 已有充分覆盖。

## 修复项

1. ✅ 分类改为正交 parameter_state × n_state（9 种组合）
2. ✅ fail-closed 单元测试 29 passed
3. ✅ 15 模型分层分析（min/Q1/med/Q3/max/mean/SD）+ Default/L1 逐模型配对
4. ✅ P0 实质核验（manifest SHA256、样本键、split/fold/seed、E3b/E4d gate）
5. ✅ 修正 P2 建议（口径区分：参数组合数 vs 样本数 vs delta 评估次数）
6. ✅ 不自行声称 SUFFICIENT
7. ✅ DtypeWarning 处理、n_only→n 命名修复
8. ✅ git diff --check clean

## 产物清单

| 路径 | 说明 |
|------|------|
| `code/gen_labels.py` | 正交分类函数 |
| `tests/test_gen_labels.py` | 29 个 fail-closed 单元测试 |
| `scripts/audit_study01_p0p1_v2.py` | P0-P1 综合审计脚本 |
| `coworker/reports/2026-07-26-study01-p0p1-audit-opencode.md` | 原报告（保留） |
| `coworker/reports/2026-07-27-study01-p0p1-revise-opencode.md` | 本报告 |

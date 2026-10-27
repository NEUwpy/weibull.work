# Study01 P0-P1 最终审计与证据重分析报告

> 执行者：OpenCode
> 日期：2026-07-27
> 分支：study01xu
> 最终执行提交：`study01xu@be8d7b81`
> 独立复核：Codex `APPROVE P0–P1`
> 后续状态：P2 最小补点设计已转入 `02-实验协议.md` v2.1；P2 尚未执行

## P0. 实质核验

### 0.1 Manifest SHA256 验证

11 个正式 manifest 全部存在。`output_provenance` 中 7 项预期 SHA256 与对应文件逐项匹配；`SHA256SUMS_e4d` 7/7、`SHA256SUMS_p8a` 5/5 通过。

### 0.2 样本键验证

- 每 fold×seed 有 17,000 个唯一基础 `(beta,ge,n,repeat)` 键
- 15 个模型使用完全相同的样本键集（fold/seed cross 一致性通过）
- 加入模型标识后共有 255,000 个完整键，全部唯一

### 0.3 Model Count

15 个 model (5 folds × 3 seeds [42, 2026, 3407]) — 确认。

### 0.4 E3b Gate

| Gate | 状态 |
|------|------|
| gate1_fold_partition | PASS |
| gate2_seed42_per_sample | PASS |
| gate3_three_seed_summary | PASS |
| **overall_pass** | **PASS** |

审计器递归检查 gate 报告中的 dict/list 嵌套结构；所有 `.pass` 与 `overall_pass` 均为真。

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

代码：`code/gen_labels.py`；最终 fail-closed 审计入口为 `scripts/audit_study01_p0p1_v4.py`。分类及负向场景共 31 tests passed。

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
| pure_p_interp (p=interp, n=on_grid) | 1 combo | 客观计数：1 |
| **pure_n_interp** (p=on_grid, n=interp) | **0** | **证据缺口：必须补点** |
| pure_p_extrap (p=extrap, n=on_grid) | 11 combos | 客观计数：11 |
| pure_n_extrap (p=on_grid, n=extrap) | 4 combos | 客观计数：4 |

### 1.5 与 Default/L1 配对比较结论

Vector-MLP-L6 在**所有有数据的轴**上均优于 Default 和 L1（14-15/15 模型级 wins）。仅在 `p_on_grid_n_extrap` 轴上有 1/15 模型对 L1 为 tie。

## P2 冻结设计

### 必须（否则无法回答 pure_n_interp）

**P2-NI：n=15 纯样本量插值**：
- 参数空间：15 个训练网格参数对（`beta∈{1.5,2.0,2.5,4.0,5.0} × gamma/eta∈{0.1,0.5,1.0}`）
- 样本量：`n=15`（单值）
- **口径区分**：15 个参数组合 × 1 个 n 值 = **15 个组合**；每个组合 1000 repeats = **15,000 个抽样样本**；每个样本运行 26 个 delta 值 = **390,000 次 MDM 评估**
- `eta=1`，`gamma=(gamma/eta)×eta`

### 同轮执行（增强 pure_p_interp 独立性）

**P2-PI：参数插值补点**：
- `beta∈{1.75,2.25,3.25,4.50}`
- `gamma/eta∈{0.30,0.75}`
- 每个参数对在 `n∈{7,10,20}` 三个已训练样本量下各 1000 repeats
- 总计 8 个参数对 × 3 个 n = **24 个组合**，24,000 个抽样样本，624,000 次 MDM 评估

两个轨道合计 **39 个组合、39,000 个抽样样本、1,014,000 次 MDM 评估**，seed namespace 固定为 `study01_p2_v1`。点位由训练格点中点机械确定，禁止按结果追加点位。

**本轮不补** pure_p_extrap、pure_n_extrap 和混合轴；这是一项范围冻结，不解释为这些轴已经获得连续空间充分覆盖。

## 修复项

1. ✅ 分类改为正交 parameter_state × n_state（9 种组合）
2. ✅ fail-closed 分类及负向场景测试 31 passed
3. ✅ 15 模型分层分析（min/Q1/med/Q3/max/mean/SD）+ Default/L1 逐模型配对
4. ✅ P0 实质核验（manifest SHA256、样本键、split/fold/seed、E3b/E4d gate）
5. ✅ 修正 P2 建议（口径区分：参数组合数 vs 样本数 vs delta 评估次数）
6. ✅ 删除 "充分覆盖" 判定，改为客观计数
7. ✅ DtypeWarning 消除（dtype=str 读取后转换）
8. ✅ git diff --check clean
9. ✅ win/loss/tie 容差 `0.001` 声明为描述性规则，非统计显著性
10. ✅ P0 全部改为 fail-closed assertions（v3 脚本）
11. ✅ SHA256SUMS_e4d + SHA256SUMS_p8a 验证通过
12. ✅ E3b gate 递归子检查全部 PASS
13. ✅ P8 gate R^2=0.995, failure rate 0

## 产物清单

| 路径 | 说明 |
|------|------|
| `code/gen_labels.py` | 正交分类函数 |
| `tests/test_gen_labels.py` | 正交分类与 fail-closed 单元测试 |
| `scripts/audit_study01_p0p1_v2.py` | 前一版审计脚本（保留） |
| `scripts/audit_study01_p0p1_v3.py` | 前一版 fail-closed 审计脚本（保留） |
| `scripts/audit_study01_p0p1_v4.py` | **当前权威审计脚本** |
| `coworker/reports/2026-07-26-study01-p0p1-audit-opencode.md` | 原报告（保留） |
| `coworker/reports/2026-07-27-study01-p0p1-revise-opencode.md` | 本报告 |

## 注记

- win/loss/tie 容差 `0.001` 为本次描述性规则，不暗示统计显著性。
- manifest `output_provenance` 的 7 项 SHA256 与当前文件逐项匹配；同时独立验证 `SHA256SUMS_e4d` 7/7 和 `SHA256SUMS_p8a` 5/5。
- 文本中不使用 "充分覆盖" 判定；覆盖状态仅报告客观计数（combo 数、行数）。
- `P1_EVIDENCE=GAP_REQUIRES_P2` 是科学证据状态而非完整性失败，因此审计正常退出；`P0_INTEGRITY=PASS`。

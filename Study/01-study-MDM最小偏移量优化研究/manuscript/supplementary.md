# Supplementary Materials

本文档是正文的补充材料。每项均说明它补充正文的哪个判断。

---

## S1 正式实验网格与合同

完整参数网格：β∈{1.5, 2.0, 2.5, 4.0, 5.0}、γ/η∈{0.1, 0.5, 1.0}、n∈{7, 10, 20}，共45个参数组合。δ∈{0.00, 0.02, ..., 0.50}共26个点。每组合R=1000个独立repeat。基于尺度等变性固定η=1。

**补充正文§2.5。** 来源：`code/config.py`。

---

## S2 Cross-Fit敏感性 (Figure S1)

E1/E2的层级收益可能来自同一数据上的择优→评价偏差。为检验此可能性，采用5折repeat-level cross-fit：fold = repeat_id mod 5。在训练折上选择最优δ，在测试折上评价J₁。

主要发现：跨折选择的L2最优δ与pooled结果一致（多数投票n=7,10选0.10，n=20选0.08）；L3-L5的cross-fit J₁与pooled J₁差异<0.01；层级间相对改善的结构在cross-fit下保持稳定。

**补充正文§3.1-3.2。** 来源：`artifacts/formal/E1_E2_crossfit/`。

---

## S3 β-Profile审计 (Figure S2)

对β=1.5, 2.0, 2.5, 4.0, 5.0共5个β值、n=7/10/20共3个样本量、每格20个repeat，总计5×3×20=300个正式seed样本（每个β合计60个），计算每个样本的J₁与δ的profile曲线。在正式参数网格内，不同β值的profile曲线几何存在系统性差异。此关联限于现有5个β值的观察，不构成因果机制证明或任意β的外推。

**补充正文§3.2。** 来源：`artifacts/formal/E2_beta_profile_audit/`。

---

## S4 三Seed稳定性 (Figure S3)

Vector-MLP-L6的三个seed（42, 2026, 3407）的pooled和分n J₁，直接从`seed_stability.csv`获取：

| Seed | n=7 | n=10 | n=20 | Pooled |
|------|-----|------|------|--------|
| 42 | 0.657558 | 0.549815 | 0.403679 | 0.547003 |
| 2026 | 0.657899 | 0.549735 | 0.399680 | 0.546133 |
| 3407 | 0.657170 | 0.545974 | 0.397339 | 0.544009 |

跨seed最大pooled差异为0.003（均值的0.55%）。

**补充正文§3.3。** 来源：`artifacts/formal/E3b_vector_mlp/seed_stability.csv`。

---

## S5 特征集对比明细 (Figure S4)

E4a的retained-subset comparison结果，15-run mean±SD（从`summary_e4a.json`和`E4a_feature_ablation.csv`获取）：

| 特征集 | n_features | Pooled J₁ (mean) | SD |
|--------|-----------|------------------|-----|
| full | 13 | 0.545628 | 0.010152 |
| scale_quantile | 10 | 0.550596 | 0.011898 |
| shape | 4 | 0.581578 | 0.021119 |
| n | 1 | 0.637761 | 0.019518 |

scale_quantile已保留full的大部分表现；shape-only明显弱于full；n-only最弱（甚至弱于L1/L2基线）。完整特征集总体最好。

**补充正文§3.4。** 来源：`artifacts/formal/E4_robustness/summary_e4a.json`，`E4a_feature_ablation.csv`。

---

## S6 Boundary/Off-grid分层结果 (Figure S5)

E4d/R1的15个模型在boundary和off-grid上的per-model true loss。详细数据见`E4d_paired_comparisons_by_model.csv`。15个模型之间的一致性：boundary上CV约4-5%，off-grid上约3-4%。

**补充正文§3.4。** 来源：`artifacts/formal/E4_robustness/E4d_selector_extrapolation.csv`。

---

## S7 R2完整条件分布 (Figure S6)

在原最优δ=0.50的2,958个端点cohort样本中，扩展网格（δ=0.52-1.00）中的新最优5-bin分区，直接从`cohort_summary.csv`的`extended_best_delta_distribution`字段读取：

| 区间 | 样本数 | 占比 |
|------|--------|------|
| δ=0.50 | 158 | 5.3% |
| δ=0.52–0.70 | 1,218 | 41.2% |
| δ=0.72–0.90 | 682 | 23.1% |
| δ=0.92–0.98 | 157 | 5.3% |
| δ=1.00 | 743 | 25.1% |
| **合计** | **2,958** | **100%** |

**补充正文§3.4。** 来源：`artifacts/formal/delta_upper_bound_audit/cohort_summary.csv`。

---

## S8 NN 15模型Per-n分布 (Figure S7)

P6-P8真实数据验证中15个NN selector的per-model中位数D分布。所有15个模型的完整中位数和分布统计见正文Figure 9和`real_nn_model_stability.csv`。

CV为1.2-3.7%，远小于NN与Default/L2之间的差距——模型不确定性不是NN未优于Default的主要原因。

**补充正文§3.5。** 来源：`artifacts/formal/real_data/nist-6061-t6-fatigue/real_holdout_results.csv`。

---

## S9 支持集违规明细 (Figure S8)

P6-P8中支持集违规的完整汇总。Default和L2为pooled值；NN为15模型中位数。详细数据见正文§3.5表格。

**补充正文§3.5。** 来源：`real_holdout_results.csv`。

---

## S10 失败处理与Provenance

### 失败处理合同

按P6冻结合同§5，MDM估计失败行保留在结果中，D=1，failed=True，failure_reason非空。禁止使用dropna()静默删除。NIST 6061-T6实验中所有25,500次MDM估计均成功收敛（0失败行）。

### P8a Provenance

四个数据输出文件（CSV, summary JSON, stability CSV, run log）与artifact commit `7946108`完全一致。`real_data_manifest.json`在P8b REVISE中修正（recovery_attempts, output_hashes）。`SHA256SUMS_p8a`为P8b REVISE新增的外部封存文件，绑定全部5个最终文件的SHA256。

生成提交：`3330523`。产物提交：`7946108`。最终批准：P8b Codex APPROVE @ `1d11a6a`。

---

## S11 完整Case Sensitivity

本次实验无失败行，完整案例分析结果与主分析完全一致。此表仅用于合同完整性。

| 方法 | n | n_complete | Mean D | Median D |
|------|---|-----------|--------|----------|
| Default | 7 | 500 | 0.2065 | 0.1881 |
| Default | 10 | 500 | 0.1779 | 0.1630 |
| Default | 20 | 500 | 0.1399 | 0.1276 |
| L2 | 7 | 500 | 0.2065 | 0.1881 |
| L2 | 10 | 500 | 0.1779 | 0.1630 |
| L2 | 20 | 500 | 0.1401 | 0.1263 |

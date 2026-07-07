# Study/01 Ch1-Ch5 图表诊断与补齐 — 执行报告

> Executor: hermes
> Date: 2026-07-06
> Task: coworker figure diagnostics — 补齐 Ch1-Ch5 图像解释链
> Status: ✅ 完成（4 图实现 + 3 处正文修订 + 1 图 skip）

## 1. 执行概要

本次任务在现有 Ch1-Ch5 草稿基础上，补齐评审者指定的 5 张图中可低成本实现的 4 张，并做 3 处轻量正文修订。图5（L6 margin diagnostic）按 escape hatch 跳过。所有新增图均使用现有正式 artifacts 生成，未重跑任何 MC 数据。

## 2. Changed Files

### 新增
| 文件 | 用途 |
|------|------|
| `code/plot_fig_diagnostics.py` | 4 张诊断图的绘图脚本（约 470 行） |
| `artifacts/formal/figures/fig_offset_mechanism.{svg,pdf,png}` | Fig A: δ 机制概念示意图 |
| `artifacts/formal/figures/fig_l2_n_heterogeneity.{svg,pdf,png}` | Fig B: L2/n 异质性双 panel |
| `artifacts/formal/figures/fig_l4_beta_n_heatmap.{svg,pdf,png}` | Fig C: β×n δ* 热力图 |
| `artifacts/formal/figures/fig_l5_heatmap.{svg,pdf,png}` | Fig D: L5 β×γ/η×n 热力图（附录） |
| `progress-figure-diagnostics.md` | 进度控制文档 |

### 修改（轻量正文修订）
| 文件 | 修订内容 |
|------|---------|
| `draft-Ch3-初稿.md` | §1.4 末尾插入 Figure 5（δ 机制示意图）引用 + 图注 |
| `draft-Ch4-初稿.md` | §2 插入 Figure 6（L2/n 异质性）引用 + 图注；§4 小结收紧"n 不是主要决定因素"→"n 强烈影响 J₁ 水平但单独按 n 选 δ 边际收益极小" |
| `draft-Ch5-初稿.md` | §3 L4 段插入 Figure 7（β×n 热力图）引用 + 图注；收紧"对固定 β，n 越大 δ* 越大"→"对小 β n 越大 δ* 略大，对大 β n 几乎不影响 δ*" |

## 3. Generated Figure Files（数据来源 / 解释目的 / 建议章节）

### Figure 5 — δ mechanism schematic (`fig_offset_mechanism`)
- **数据来源**: 概念示意图（matplotlib 手绘 profile 曲线），不来自 MC 数据
- **解释目的**: 让读者直观看到 zero-gradient 判据（∂σ/∂γ=0）vs offset-δ 判据（∂σ/∂γ=δ）的几何差异——前者选中远离真实 γ 的假谷底，后者更接近真实 γ
- **建议章节**: Ch3 §1.4（梯度偏移判据定义后）— **主文**
- **QA 验证**: zero-gradient 误差 0.352, offset-δ 误差 0.042（概念示意，offset 判据更接近真实 γ）
- **注意**: 图注已明确标注"曲线形态为示意，不来自特定 MC 样本"，避免过度声称

### Figure 6 — L2/n heterogeneity diagnostic (`fig_l2_n_heterogeneity`)
- **数据来源**:
  - Panel A: `E1_baseline/delta_risk_curve.csv`（已聚合的 J1_n7/n10/n20 列）
  - Panel B: 从 `shared_data/mc_scan_raw.csv` 按 (n, β, δ) 聚合，规则与 analyze_E1.py 完全一致（先 mean(j1_sq) 再 sqrt）
- **解释目的**: Panel A 展示 n=7/10/20 的 pooled δ-risk（δ* 几乎不移动）；Panel B 展示同一 n 内不同 β 的 δ* 方向相反。两层合起来说明"n 决定 J₁ 水平，但不决定 δ* 方向"
- **建议章节**: Ch4 §2 — **主文**
- **QA 验证**:
  - Panel A δ* by n = {7→0.10, 10→0.10, 20→0.08}，与 table_L2_by_n.csv 一致 ✓
  - Panel B δ* by (n,β) 极端值：n=7 β=1.5→0.30 vs β=5.0→0.02；n=20 β=1.5→0.50 vs β=5.0→0.04 ✓

### Figure 7 — β×n δ* heatmap (`fig_l4_beta_n_heatmap`)
- **数据来源**: `E2_oracle_layers/L4_by_beta_n.csv`（15 行，5β×3n）
- **解释目的**: 用热力图直观展示 β 是 δ* 的主效应、n 是调节项
- **建议章节**: Ch5 §3 — **主文**
- **QA 验证**:
  - β 平均跨度 0.373（列方向，固定 n 变 β）
  - n 平均跨度 0.080（行方向，固定 β 变 n）
  - 两者比 ≈ 4.7:1，量化支撑"β 主效应"结论 ✓
  - 与 L3_by_beta.csv 一致性：β=1.5→L3 δ*=0.36, L4(n=10) δ*=0.42；β=5.0→L3 δ*=0.04, L4(n=10) δ*=0.04 ✓

### Figure S1 — L5 β×γ/η×n heatmap (`fig_l5_heatmap`)
- **数据来源**: `E2_oracle_layers/L5_by_beta_goe_n.csv`（45 行，5β×3γ/η×3n）
- **解释目的**: 展示 γ/η 有细节影响但边际收益小（L4→L5 平均改善仅 1.78%）
- **建议章节**: 附录 / supplementary — **附录图**
- **QA 验证**: L4→L5 mean improvement 1.78%（range 0.00%–4.72%）✓

## 4. Commands Run and Exact Results

```bash
# 1. 运行绘图脚本
cd "Study/01-study-MDM最小偏移量优化研究"
python code/plot_fig_diagnostics.py

# 结果：4 图 × 3 格式 = 12 文件全部生成，exit=0
# QA 数值全部与源 CSV 一致
```

关键 QA 输出：
```
[Fig A] QA: γ_true=0.15, γ_hat_0=0.502 (zero-grad), γ_hat_δ=0.192 (offset)
         |error zero-grad| = 0.352, |error offset| = 0.042
[Fig B] Panel A δ* by n: n=7→0.10, n=10→0.10, n=20→0.08
         Panel B δ* by (n, β): n=7 β=1.5→0.30, β=5.0→0.02
[Fig C] β平均跨度: 0.373, n平均跨度: 0.080
[Fig D] L4→L5 mean improvement: 1.78%
```

```bash
# 2. git diff --check（无空白错误）
git diff --check -- "Study/01-study-MDM最小偏移量优化研究"
# exit=0（仅 LF/CRLF 换行符警告，Windows 正常）
```

## 5. Skipped Optional Figures

### Figure — L6 best-second margin diagnostic（跳过）
- **评审者 escape hatch**: "只有在不需要重跑 MC、可直接从现有聚合 CSV 低成本计算时才做"
- **跳过原因**: 逐样本 margin 需要比较每个 MC 样本的 best δ 和 second-best δ 的 J₁ 差距。`L6_per_sample_delta.csv`（45000 行）只记录了每个样本的 `delta_star_L6`，**没有 second-best δ 及其 J₁ 信息**。要算 margin 必须回到 `mc_scan_raw.csv`（117 万行）对每个样本的 26 个 δ 点重新比较——属于"需要读取超大 mc_scan_raw.csv"的成本情况。
- **替代证据**: 当前 Ch5 §4 已有 Figure 4（L6 分布）展示 47.5% δ*=0 的堆积 + δ=0.5 有 2958 个边界堆积样本（6.6%），这些间接证据已支撑"L6 含大量逐样本噪声、不宜作为训练标签主目标"的结论。
- **建议**: 逐样本 margin diagnostic 留作 future work（如 E3/E4 阶段需要更精细的 L6 噪声量化时再做）。

## 6. Wording Risks Found in Ch3-Ch5

### Risk 1（已在本次修复）— Ch4 §2 "n 不是 δ 最优值的主要决定因素"
- **位置**: draft-Ch4-初稿.md §2 原文 + §4 小结
- **问题**: 原表述"样本量 n 不是 δ 最优值的主要决定因素"虽不错学，但容易被误读为"n 对 δ 决策毫无影响"。task 的 Not allowed 明确警告：不要把"n 对估计误差有强影响"误写成"n 对 δ* 决策没有影响"。
- **修复**: 改为"样本量 n 强烈影响 J₁ 的水平（n=20 的 J₁ ≈ 0.49 vs n=7 的 0.74），但单独按 n 选 δ 的边际收益极小，因为同一 n 内不同 β 的最优 δ 方向相反、pooled 后互相抵消"。
- **状态**: ✅ 已修复（§2 + §4 小结同步）

### Risk 2（已在本次修复）— Ch5 §3 "对固定 β，n 越大 δ* 往往略大"
- **位置**: draft-Ch5-初稿.md §3 L4 段
- **问题**: 以偏概全。核对 L4_by_beta_n.csv：β=1.5 确实 n=7→0.30, n=20→0.50 有趋势；但 β=4.0 各 n 均为 0.04-0.06，β=5.0 均为 0.02-0.04，几乎无 n 效应。原表述"对固定 β"一概而论不准确。
- **修复**: 改为"对小 β（β=1.5-2.0），n 越大 δ* 略大；对大 β（β=4.0-5.0），n 几乎不影响 δ*"。
- **状态**: ✅ 已修复

### Risk 3（观察，未修改）— Figure 5 概念图的过度声称风险
- **位置**: fig_offset_mechanism 图注
- **说明**: δ 机制概念图天然有"把假说画成事实"的风险。上一轮 P2 评审已要求把 profile 机理改为"可能的解释"。本次图注已明确写"曲线形态为示意，不来自特定 MC 样本"+"仅说明两种判据在概念上的几何差异"，与上一轮修复口径一致。
- **建议**: 投稿时若审稿人质疑 profile 形态，可考虑在 Ch3 §1.4 补一句"该图为判据定义的概念示意，实际 profile 形态因样本而异"。当前不修改，留待投稿版定稿。
- **状态**: ⚠️ 已在图注对冲，暂不修改正文

## 7. Recommendation: Main Text vs Supplementary

| 图 | 建议 | 理由 |
|----|------|------|
| Figure 5 (δ mechanism) | **主文** (Ch3) | 填补当前最大的解释缺口——δ=0 vs δ>0 的几何差异无可视化。对非 MDM 领域读者尤其重要 |
| Figure 6 (L2/n heterogeneity) | **主文** (Ch4) | 直接支撑 Ch4 核心论点"L2 收益微小"+"全局平坦是 β 抵消"。双 panel 信息密度高 |
| Figure 7 (β×n heatmap) | **主文** (Ch5 §3) | 用一张图替代原文字描述的 L4 δ* 表，直观展示 β 主效应 |
| Figure S1 (L5 heatmap) | **附录/supplementary** | L5 的 γ/η 效应是细节性的（边际 1.78%），正文已有 L4→L5 改善 1.9% 的数字，图放附录供深读读者参考 |

## 8. 图编号说明

本次新增图编号为 Figure 5/6/7（顺延现有 Fig1-4）。Figure S1 为附录图不编号。E3 解冻后会新增 Fig8+（NN 相关），届时需要统一重编号。当前草稿阶段的顺延编号是常规做法。

## 9. 约束遵守确认

- ✅ 未运行 generate_mc_data.py，未重跑 MC 数据生成
- ✅ 未修改 analyze_E1.py / analyze_E2.py 的实验语义（plot_fig_diagnostics.py 只读 CSV）
- ✅ 未修改正式实验数值（所有图来自现有 artifacts）
- ✅ 未把 NN 写成论文中心（本次修订未涉及 NN 内容）
- ✅ 未把 L6 写成理论上限或可部署目标（图5 skip，未新增 L6 相关图）
- ✅ n 的表述严格遵循"n 强烈影响 J₁ 水平，但单独按 n 选 δ 边际收益小"（Risk 1 已修复）
- ✅ J₁ 聚合规则与 analyze_E1.py 一致（先 mean(j1_sq) 再 sqrt）

## 10. 遗留 / 后续

1. **E3 解冻后重编号**: Figure 5/6/7 可能需要调整为 Figure 8/9/10（如果 E3 的图插在前面）
2. **vision API 不可用**: 本次 visual QA 用程序化检查（内容密度/色彩/边缘/关键颜色像素数）替代，4 图均通过。投稿前建议人工目视复核。
3. **L6 margin diagnostic**: 留作 future work，当前用 L6 分布的 δ*=0 堆积比例（47.5%）作为噪声间接证据已足够。

# Figure 1 (fig_offset_mechanism) 样本溯源报告

> 生成时间：2026-07-10（rev 5：Panel B 改为 ECDF，Panel C 改为严格配对误差散点）
> 图：`artifacts/formal/figures/fig_offset_mechanism.{png,svg,pdf}`
> 脚本：`code/plot_fig_diagnostics.py` → `plot_fig_offset_mechanism()`

## 三 Panel 总览

本图从 rev 3 的单 panel 梯度判据图升级为三子图机制/波动诊断。三 panel 共享代表配置 β=2.0, η=1000, γ=1000, n=7（贴近 182-046 原文语境 W(2.0,1000,1000), n=7）。

- **Panel A**：真实 MDM γ profile / 梯度判据图。横轴 γ，纵轴 profile gradient；两条水平判据线 y=0（zero-grad）与 y=0.1（offset δ）；三个代表样本的真实 grad_gamma_curve 和对应搜索位置 marker。
- **Panel B**：δ=0 与 δ=0.1 的 γ̂ ECDF（MC R=1000）。横轴 γ̂（乘 1000 对齐 Panel A 语境），纵轴经验累积概率；直接显示 δ=0 在 γ̂=0 处的边界质量。
- **Panel C**：同一 `repeat_id` 下绝对归一化误差的配对散点。横轴为 δ=0，纵轴为 δ=0.1；对角线下方为改善，上方为变差。

## Figure 1 论证合同（2026-07-10 确认）

- **核心结论**：`delta` 会改变 `gamma` 搜索判据并系统性改变有限样本估计分布；`delta=0.1` 总体上能够缓解部分不稳定情况，但并非每个样本都改善，因此 `delta` 应被视为需要正式优化的决策变量。
- **图形类型**：quantitative grid；Panel A 承担机制主证据，后续 panel 承担总体分布与逐样本异质性证据。
- **证据边界**：本图不证明 `delta=0.1` 全条件最优，不替代 Ch4 的 E1 正式比较，也不把代表曲线选择写成总体效果证据。
- **必须保留**：真实 MDM trace、`y=0` 与 `y=0.1` 判据、总体分布信息，以及改善/变差样本同时存在的可视证据。
- **已处理的审稿风险**：Panel B/C 信息重复已通过 ECDF + 配对散点消除；边界质量不再被密度尖峰遮蔽；内部 `repeat_id` 已移出主图；高梯度曲线裁切已在图注中说明。
- **仍需复核**：代表曲线只能承担机制示例，不能承担总体效果证据；最终投稿格式确定后复核 SVG/PDF/位图导出规格。

---

## Panel A 数据来源

本 panel **不是** 182-046 原图复刻。曲线、marker、交点全部来自当前 MDM 实现（`python/methods/mdm.py`）和本项目 `generate_sample()` 的真实计算。

视觉语境参考 182-046 图4（梯度-γ 曲线 + 水平判据线），但样本、参数、实现均为本项目独立计算。

### 参数

- `beta=2.0, eta=1000, gamma=1000, n=7`（贴近 182-046 原文图5语境 W(2.0,1000,1000), n=7）
- `delta=0.1`（182-046 经验值，本文 baseline）
- `gamma_steps=200`（trace 网格密度）
- `seed=None`（项目默认 namespace，种子由 generate_sample 内部 sha256 确定）

### 样本选择规则（可复现，不手工挑图）

扫描 `repeat_id=0-99`（共 100 个样本），对每个样本：
1. 跑 `MDM(sample).run(trace=True, offset=0.1, gamma_steps=200)`
2. 从 `grad_gamma_curve` 计算 curve-derived zero marker（y=0 sign-change 插值，
   或曲线 gradient 最接近 0 的点）
3. solver root 作为 offset marker（γ_offset）

从 100 个样本中按以下规则选 3 条代表曲线：
- **closest-to-true**: `|err_zero|` 最小
- **largest-improvement**: `|err_zero| - |err_offset|` 最大
- **mild-worsening**: 从 worsening 样本池（`|err_offset| > |err_zero|`）中，
  按 worsening 增量（`|err_offset| - |err_zero|`）升序排列后取中位数附近的样本。
  避免极端 worsening 样本（如 rid=99，+69.8pp）拉满纵轴，保持判据区间可读。

### Panel A 扫描结果摘要（β=2.0, n=7, 100 样本）

这些扫描统计数字是诊断性的，不作为论文正式结果（论文正式数字来自 E1/E2）。

| 统计量 | zero-gradient (curve) | offset δ=0.1 (solver) |
|--------|----------------------|----------------------|
| err 中位数 | −55.3% | +2.8% |
| \|err\| 中位数 | 62.4% | 22.0% |
| worsening 数 | — | 36/100 |

offset=0.0 的 solver 行为：43/100 截断到 γ=0（g(0)>=0），因此**不用**
offset=0.0 solver 作为 zero marker，改用 curve-derived。

### Panel A 选中样本详情

#### rid=26 (closest-to-true)

- sample (n=7): [1205.0, 1544.9, 1571.6, 1648.5, 1927.9, 2171.7, 3399.9]
- γ_zero(curve) = 1000.7 (err +0.1%, y=0 sign-change 插值)
- γ_offset(solver δ=0.1) = 1033.3 (err +3.3%)
- **δ 效果**：轻微变差（|err| 0.1% → 3.3%）

#### rid=77 (largest-improvement)

- sample (n=7): [1289.5, 1326.8, 1637.6, 1946.4, 2215.7, 2360.2, 2408.8]
- γ_zero(curve) = 0.0 (err −100.0%, 曲线 gradient 全程 >0，min=0.0087 在 γ=0 边界)
- γ_offset(solver δ=0.1) = 991.9 (err −0.8%)
- **δ 效果**：大幅改善（|err| 100% → 0.8%）
- 注：此样本的 zero-gradient 曲线不过零（gradient 始终为正），
  说明零梯度判据在此样本下无有效域内解，curve-derived zero 退到 γ=0 边界

#### rid=93 (mild-worsening, 按 worsening 增量中位数选取)

- sample (n=7): [1313.8, 1485.9, 1517.8, ...]
- γ_zero(curve) = 1177.9 (err +17.8%, y=0 sign-change 插值)
- γ_offset(solver δ=0.1) = 1199.4 (err +19.9%)
- **δ 效果**：轻微变差（|err| 17.8% → 19.9%，worsening 增量 +2.1pp）
- 对比：最大 worsening 样本 rid=99 的增量为 +69.8pp（+6.7%→+76.5%），
  会让纵轴被尖峰拉满，故不放入主图

### Panel A 曲线验证

每条曲线 201 个点（gamma_steps=200 + 1 个 solver_root 点），
source 字段包含 `trace_grid`（真实计算网格点）和 `solver_root`（求解器根）。
不是手工构造。

### Panel A 纵轴范围说明

Panel A 纵轴聚焦 `[-0.2, 0.6]`，让 y=0 和 y=0.1 两条判据线的差异可读。
曲线在 γ→t_min 时梯度趋向大正值（rid=77/93 可达 2.7+），这些尖峰被
裁切以保持判据区间的视觉可读性，不影响 marker 和交点的准确性。

---

## Panel B/C 数据来源

Panel B/C 的数据**不是**新跑的 MC，而是直接从正式实验数据 `artifacts/formal/shared_data/mc_scan_raw.csv` 筛选，与 Panel A 等价配置。

### 数据筛选

```
beta == 2.0
eta == 1.0
gamma_over_eta == 1.0   # 即 gamma = 1.0（eta=1 尺度）
n == 7
delta ∈ {0.0, 0.1}
converged == True
```

筛选结果：delta=0.0 有 1000 行，delta=0.1 有 1000 行（全部 converged=True，无失败样本）。

### 尺度等价性

mc_scan_raw.csv 用的参数是归一化尺度（eta=1.0, gamma=1.0），与 Panel A 的 W(2.0, 1000, 1000) 是同一 Weibull 分布的尺度变换。MDM 在 Weibull 尺度族下不变（尺度参数可分离），因此 eta=1/gamma=1 的 MC 结果与 eta=1000/gamma=1000 等价。

显示时 Panel B 把 `gamma_hat` 乘 1000，使横轴对齐 Panel A 的 γ=1000 语境；真值标记为 γ=1000。Panel C 在原始归一化尺度上计算绝对误差 `|(gamma_hat-gamma)/eta|`，并用 `repeat_id` 将 δ=0 与 δ=0.1 一一配对。缺失或重复配对会直接报错，不做隐式删行。

### Panel B/C 诊断数字（mc_scan_raw.csv 筛选后）

| 配置 | γ̂ 中位数 | \|err\| 中位数 |
|------|---------|---------------|
| δ=0（zero-grad） | 811.6 | 0.463 |
| δ=0.1（offset） | 1103.1 | 0.226 |

严格配对的 1000 个样本中，δ=0.1 的绝对归一化误差低于 δ=0 的比例为 55.9%，高于 δ=0 的比例为 44.1%，无并列；δ=0 在 γ̂=0 处的边界质量为 34.0%。这些数字与 Panel A 的 trace 机制一致：δ=0.1 在该配置下把 γ̂ 中位数从 811.6 移到 1103.1，并把 |err| 中位数从 0.463 降到 0.226，但逐样本并非必然改善。

注意：这些 Panel B/C 数字是同一参数组合下的 pooled 描述性统计，不是论文正式 J₁ 结论。论文正式数字仍来自 E1/E2 的全网格聚合（见 `artifacts/formal/E1_baseline/summary.json` 等）。

### Panel B/C 复现

Panel B/C 随 Panel A 一并由 `plot_fig_offset_mechanism()` 生成。若 mc_scan_raw.csv 缺失，脚本会报错并打印重建指令（`python code/generate_mc_data.py --merge-only`），不会自动重跑 MC。

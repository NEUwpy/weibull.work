# Figure 1 (fig_offset_mechanism) 样本溯源报告

> 生成时间：2026-07-07（rev 3：mild worsening 选择 + y 轴聚焦判据区间）
> 图：`artifacts/formal/figures/fig_offset_mechanism.{png,svg,pdf}`
> 脚本：`code/plot_fig_diagnostics.py` → `plot_fig_offset_mechanism()`

## 数据来源

本图**不是** 182-046 原图复刻。曲线、marker、交点全部来自当前 MDM 实现
（`python/methods/mdm.py`）和本项目 `generate_sample()` 的真实计算。

视觉语境参考 182-046 图4（梯度-γ 曲线 + 水平判据线），但样本、参数、
实现均为本项目独立计算。

## 参数

- `beta=2.0, eta=1000, gamma=1000, n=7`（贴近 182-046 原文图5语境 W(2.0,1000,1000), n=7）
- `delta=0.1`（182-046 经验值，本文 baseline）
- `gamma_steps=200`（trace 网格密度）
- `seed=None`（项目默认 namespace，种子由 generate_sample 内部 sha256 确定）

## 样本选择规则（可复现，不手工挑图）

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

## 扫描结果摘要（β=2.0, n=7, 100 样本）

这些扫描统计数字是诊断性的，不作为论文正式结果（论文正式数字来自 E1/E2）。

| 统计量 | zero-gradient (curve) | offset δ=0.1 (solver) |
|--------|----------------------|----------------------|
| err 中位数 | −55.3% | +2.8% |
| \|err\| 中位数 | 62.4% | 22.0% |
| worsening 数 | — | 36/100 |

offset=0.0 的 solver 行为：43/100 截断到 γ=0（g(0)>=0），因此**不用**
offset=0.0 solver 作为 zero marker，改用 curve-derived。

## 选中样本详情

### rid=26 (closest-to-true)

- sample (n=7): [1205.0, 1544.9, 1571.6, 1648.5, 1927.9, 2171.7, 3399.9]
- γ_zero(curve) = 1000.7 (err +0.1%, y=0 sign-change 插值)
- γ_offset(solver δ=0.1) = 1033.3 (err +3.3%)
- **δ 效果**：轻微变差（|err| 0.1% → 3.3%）

### rid=77 (largest-improvement)

- sample (n=7): [1289.5, 1326.8, 1637.6, 1946.4, 2215.7, 2360.2, 2408.8]
- γ_zero(curve) = 0.0 (err −100.0%, 曲线 gradient 全程 >0，min=0.0087 在 γ=0 边界)
- γ_offset(solver δ=0.1) = 991.9 (err −0.8%)
- **δ 效果**：大幅改善（|err| 100% → 0.8%）
- 注：此样本的 zero-gradient 曲线不过零（gradient 始终为正），
  说明零梯度判据在此样本下无有效域内解，curve-derived zero 退到 γ=0 边界

### rid=93 (mild-worsening, 按 worsening 增量中位数选取)

- sample (n=7): [1313.8, 1485.9, 1517.8, ...]
- γ_zero(curve) = 1177.9 (err +17.8%, y=0 sign-change 插值)
- γ_offset(solver δ=0.1) = 1199.4 (err +19.9%)
- **δ 效果**：轻微变差（|err| 17.8% → 19.9%，worsening 增量 +2.1pp）
- 对比：最大 worsening 样本 rid=99 的增量为 +69.8pp（+6.7%→+76.5%），
  会让纵轴被尖峰拉满，故不放入主图

## 曲线验证

每条曲线 201 个点（gamma_steps=200 + 1 个 solver_root 点），
source 字段包含 `trace_grid`（真实计算网格点）和 `solver_root`（求解器根）。
不是手工构造。

## 纵轴范围说明

主图纵轴聚焦 `[-0.2, 0.6]`，让 y=0 和 y=0.1 两条判据线的差异可读。
曲线在 γ→t_min 时梯度趋向大正值（rid=77/93 可达 2.7+），这些尖峰被
裁切以保持判据区间的视觉可读性，不影响 marker 和交点的准确性。

---
id: "case-9"
name: "案例9: β步长对估计结果的影响"
description: "研究β步长从0.01到0.1对MDM参数估计结果的影响"
architecture: "case9"
processName: "偏移量"
processSymbol: "δ"
csvFile: "/case-studies/mdm/case9/data.json"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1330
  sampleSize: 7
  process: 0.1
params:
  - id: "beta_step"
    name: "β步长"
    symbol: "Δβ"
    state: "discrete"
    discreteValues: [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    isVariable: true
    isDisplayDimension: true
  - id: "gamma"
    name: "位置参数"
    symbol: "γ"
    state: "continuous"
    range: [0, 1430]
    isVariable: true
    isDisplayDimension: false
  - id: "eta"
    name: "尺度参数"
    symbol: "η"
    state: "dependent"
    isVariable: false
    isDisplayDimension: false
---

## 案例9: β步长对估计结果的影响

### 研究目的

研究 β 搜索步长对 MDM 参数估计结果的影响机制：

| 因素 | 影响路径 |
|------|----------|
| β步长 | → σ-β 曲线采样密度 → σ_min 精度 |
| β步长 | → σ_min-γ 曲线形态 → ∇(γ) 计算 |
| β步长 | → ∇(γ)-γ 曲线 → 最优 γ 交点 |
| β步长 | → 最终 β, η 估计值 |

### 数据来源

实际样本 (n=7): 1430.7, 2632.9, 1463.4, 1469.5, 2020.0, 1620.9, 1811.3

### 实验设计

- **β步长**: 0.01, 0.02, 0.03, ..., 0.1 (共10种)
- **偏移量**: δ = 0.1, 0.15
- **γ搜索**: 统一60次迭代（消除γ步长的干扰）

### 关键问题

1. β步长越大，最优 β 值的误差如何变化？
2. β步长对 σ-β 曲线的最低点位置有何影响？
3. β步长对 σ_min-γ 曲线的形态有何影响？
4. β步长如何传导影响最终的 γ 估计值？

### 可视化图表

1. **汇总对比表**: 不同 β 步长下的估计结果
2. **β步长 vs 估计误差**: 展示步长与精度的关系
3. **多 β 步长的 σ-β 曲线叠加**: 对比曲线形态差异
4. **多 β 步长的 σ_min-γ 曲线叠加**: 对比 σ_min 曲线差异
5. **β步长 vs γ 估计值**: 展示步长对 γ 的影响

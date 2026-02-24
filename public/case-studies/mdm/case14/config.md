---
id: "case-14"
name: "案例14: MDM vs WMLE 方法对比 (多尺度参数)"
description: "在案例12基础上增加尺度参数选择，研究分散性对两种方法的影响"
architecture: "case14"
processName: "尺度参数"
processSymbol: "η"
csvFile: "/case-studies/mdm/case14/data.json"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1
true_params:
  beta: 2.0
  eta_values: [200, 1000, 5000]
  gamma: 1000
  sampleSizes: [7, 9, 10, 12, 15, 20]
research_type: "method_comparison_multi_eta"
params:
  - id: "eta"
    name: "尺度参数"
    symbol: "η"
    state: "discrete"
    discreteValues: [200, 1000, 5000]
    isVariable: true
    isDisplayDimension: true
  - id: "sample_size"
    name: "样本量"
    symbol: "n"
    state: "discrete"
    discreteValues: [7, 9, 10, 12, 15, 20]
    isVariable: true
    isDisplayDimension: true
  - id: "method"
    name: "估计方法"
    symbol: "Method"
    state: "discrete"
    discreteValues: ["mdm", "wmle"]
    isVariable: true
    isDisplayDimension: true
  - id: "gamma"
    name: "位置参数"
    symbol: "γ"
    state: "continuous"
    range: [0, 1500]
    isVariable: false
    isDisplayDimension: false
---

## 案例14: MDM vs WMLE 方法对比研究 (多尺度参数)

### 研究目的

在案例12的基础上，扩展研究**尺度参数 η** 对两种威布尔三参数估计方法的影响：

| 方法 | 全称 | 核心思想 |
|------|------|----------|
| **MDM** | Minimum Discrepancy Method | 通过最小化 η 的标准差确定参数，梯度交点确定 γ |
| **WMLE** | Weighted Maximum Likelihood | 在 MLE 基础上引入权重修正小样本偏差 |

### 尺度参数的物理意义

| η 值 | 分散性 | 失效时间分布 |
|------|--------|--------------|
| 200 | 小 | 数据集中，失效时间差异小 |
| 1000 | 中 | 基准 |
| 5000 | 大 | 数据分散，失效时间差异大 |

### 研究方法

- **尺度参数**: η = 200, 1000, 5000
- **样本量**: n = 7, 9, 10, 12, 15, 20
- **蒙特卡洛模拟**: 各1000次/方法
- **真实参数**: β=2.0, γ=1000
- **MDM偏移量**: δ=0.1

### 关键问题

1. 尺度参数（分散性）对 MDM 和 WMLE 的估计精度有何影响？
2. 小尺度（η=200）和大尺度（η=5000）下，哪种方法更稳定？
3. 分散性变化时，γ (位置参数) 的估计精度如何变化？

### 方法简介

**MDM (Minimum Discrepancy Method)**
- 基于 Weibull 概率纸的几何方法
- 通过搜索梯度曲线与偏移值 δ 的交点确定 γ
- 使用 Brent 优化找到使 σ_η 最小的 β

**WMLE (Weighted Maximum Likelihood)**
- 在 MLE 对数似然函数基础上引入三个权重
- W1: 修正 η 的估计偏差
- W2: 修正 β 的估计偏差
- W3: 修正 γ 的估计偏差
- 通过 Nelder-Mead 优化求解

### 可视化图表

1. **尺度参数选择器**: 切换 η=200/1000/5000
2. **统计汇总表**: 偏差、标准差、MSE、收敛率对比
3. **参数估计概率密度分布**: β、η、γ 的 KDE 分布对比

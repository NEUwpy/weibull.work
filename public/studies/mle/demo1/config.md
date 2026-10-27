---
id: demo-1
name: '示例1: MLE多维度研究'
description: 研究 MLE 方法在不同参数设置下的估计性能（单变量+双变量模式）
method: mle
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 10
simulation:
  mcRuns: 1000
  seedFormula: "seed = sim_id + Σ(param_value × 1000)"
  mode: partial_cross  # 单变量 + 双变量模式（非全交叉）
  totalCombinations: 77
  totalRuns: 77000
charts:
  univariate:
    boxplot:
      container: grid
      params:
      - beta
      - eta
      - gamma
      titles:
        beta: β估计值分布
        eta: η估计值分布
        gamma: γ估计值分布
    density:
      container: tab
      params:
      - beta
      - eta
      - gamma
      titles:
        beta: β估计值概率密度分布
        eta: η估计值概率密度分布
        gamma: γ估计值概率密度分布
  bivariate:
    heatmap:
      container: grid
      params:
      - beta
      - eta
      - gamma
      titles:
        beta: β参数偏差热力图
        eta: η参数偏差热力图
        gamma: γ参数偏差热力图
params:
- id: beta
  name: 形状参数
  symbol: β
  state: discrete
  discreteValues:
  - 1.5
  - 2
  - 3
  - 5
  - 7
  isVariable: true
  isDisplayDimension: false
- id: eta
  name: 尺度参数
  symbol: η
  state: discrete
  discreteValues:
  - 200
  - 1000
  - 5000
  isVariable: true
  isDisplayDimension: false
- id: gamma
  name: 位置参数
  symbol: γ
  state: fixed
  fixedValue: 1000
  isVariable: false
  isDisplayDimension: false
- id: sampleSize
  name: 样本量
  symbol: n
  state: discrete
  discreteValues:
  - 3
  - 5
  - 7
  - 10
  - 20
  - 30
  isVariable: true
  isDisplayDimension: false
---



# MLE 示例1: 多维度研究

## 研究背景

使用 MLE（极大似然估计）估计三参数威布尔分布参数，评估不同因素对估计精度的影响。

本研究采用"单变量+双变量"模式，避免全交叉组合带来的数据爆炸。

## 研究目标

1. 评估 MLE 算法在不同参数组合下的估计性能
2. 分析 MLE 的偏差特性（注意：当 β<1 时 MLE 可能无界）
3. 对比不同 β、η、n 组合下的偏差和标准差

## 参数设置

**单变量研究**（14 组）：
- β 变化: {1.5, 2, 3, 5, 7}，固定 η=1000, n=10 → 5 组
- η 变化: {200, 1000, 5000}，固定 β=2, n=10 → 3 组
- n 变化: {3, 5, 7, 10, 20, 30}，固定 β=2, η=1000 → 6 组

**双变量研究**（63 组）：
- β × η: 5 × 3 = 15 组（n=10 固定）
- β × n: 5 × 6 = 30 组（η=1000 固定）
- η × n: 3 × 6 = 18 组（β=2 固定）

**总计**: 14 + 63 = 77 组
**每组模拟**: 1000 次
**总模拟次数**: 77,000 次

**位置参数**: γ=1000 (固定)

## 数据说明

结果文件包含每个模拟的：
- 真实参数值（`beta_true`, `eta_true`, `sample_size`）
- 估计参数值（`est_beta`, `est_eta`, `est_gamma`）
- 偏差值（`bias_beta`, `bias_eta`, `bias_gamma`）
- 拟合优度（`r_squared`）

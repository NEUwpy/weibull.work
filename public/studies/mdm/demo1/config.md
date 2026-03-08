---
id: demo-1
name: '示例1: MDM多维度研究'
description: 研究形状参数、尺度参数、样本量、偏移量对MDM三参数估计结果的影响。
method: mdm
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1
simulation:
  mcRuns: 1000
  seedFormula: "seed = sim_id + Σ(param_value × 1000)"
  totalCombinations: 450
  totalRuns: 450000
calculation:
  gammaSteps: 60
  rankMethod: bernard
  betaBounds:
  - 0.1
  - 15.0
  gammaRangeRound1:
  - 0
  - 0.99
  gammaRangeRound2:
  - 0.99
  - 0.999999
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
- id: process
  name: 偏移量
  symbol: δ
  state: discrete
  discreteValues:
  - 0
  - 0.05
  - 0.1
  - 0.15
  - 0.2
  isVariable: true
  isDisplayDimension: false
---



# MDM 示例1: 多维度研究

## 研究背景

使用 MDM（最小差异法）估计三参数威布尔分布参数，评估不同因素对估计精度的影响。

## 研究目标

1. 评估 MDM 算法在不同参数组合下的估计性能
2. 分析无解（no_intersection）现象的发生率及其与参数的关系
3. 对比不同 β、η、n、δ 组合下的偏差和标准差

## 参数设置

- **形状参数**: β∈{1.5, 2.0, 3, 5, 7} (5个值)
- **尺度参数**: η∈{200, 1000, 5000} (3个值)
- **位置参数**: γ=1000 (固定)
- **样本量**: n∈{3, 5, 7, 10, 20, 30} (6个值)
- **偏移值**: δ∈{0, 0.05, 0.1, 0.15, 0.2} (5个值)
- **总组合数**: 5×3×6×5 = 450种
- **每种组合**: 1000次模拟
- **总模拟次数**: 450,000次

## 数据说明

结果文件包含每个模拟的：
- 真实参数值（`beta_true`, `eta_true`, `sample_size`, `offset_value`）
- 估计参数值（`est_beta`, `est_eta`, `est_gamma`）
- 偏差值（`bias_beta`, `bias_eta`, `bias_gamma`）
- 拟合优度（`r_squared`）
- **无解标记**: 当MDM无解时，所有估计值和统计量为 `NaN`

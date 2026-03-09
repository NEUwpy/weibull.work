---
id: demo-2
name: '示例2: 仿真设置'
description: 研究不同样本量和蒙特卡洛重复次数下MDM估计的收敛特性。
method: mdm
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1
simulation:
  mcRunsList:
    - 1000
    - 2000
    - 3000
    - 4000
    - 5000
  maxMcRuns: 5000
  seedFormula: "seed = sim_id + sample_size * 1000 + base_seed"
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
    convergence:
      container: tab
      statTypes:
      - mean
      - median
      - std
      params:
      - beta
      - eta
      - gamma
params:
- id: beta
  name: 形状参数
  symbol: β
  state: fixed
  fixedValue: 2
  isVariable: false
  isDisplayDimension: false
- id: eta
  name: 尺度参数
  symbol: η
  state: fixed
  fixedValue: 1000
  isVariable: false
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
  - 4
  - 5
  - 6
  - 7
  - 8
  - 9
  - 10
  - 15
  - 20
  - 30
  isVariable: true
  isDisplayDimension: true
- id: process
  name: 偏移量
  symbol: δ
  state: fixed
  fixedValue: 0.1
  isVariable: false
  isDisplayDimension: false
---

# MDM 示例2: 蒙特卡洛收敛性研究

## 研究背景

研究 MDM 方法在不同样本量和蒙特卡洛重复次数下的估计收敛特性。

## 研究目标

1. 评估样本量对估计精度的影响
2. 分析蒙特卡洛重复次数增加时估计值的收敛趋势
3. 观察不同统计量（均值、中位数、标准差）的收敛特性

## 参数设置

- **形状参数**: β=2 (固定)
- **尺度参数**: η=1000 (固定)
- **位置参数**: γ=1000 (固定)
- **偏移值**: δ=0.1 (固定)
- **样本量**: n∈{3,4,5,6,7,8,9,10,15,20,30} (变量)

## 蒙特卡洛设置
- **重复次数切片**: 1000, 2000, 3000, 4000, 5000
- **说明**: 每个样本量运行5000次仿真，统计时按不同切片计算

## 图表说明
1. **箱型图**: 展示不同样本量下参数估计的分布（当前选择的重复次数）
2. **概率密度图**: 使用 KDE 展示估计值的分布（当前选择的重复次数）
3. **收敛图**: 展示估计值随重复次数增加的收敛趋势

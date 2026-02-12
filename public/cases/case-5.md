---
id: "case-5"
name: "案例5: 30组实际样本的MDM估计分析"
description: "30组真实失效数据（每组7个观测值）来自威布尔分布(β=2, η=1000, γ=1000)，使用MDM方法进行三参数估计，分析估计偏差与梯度曲线特性。"
processName: "偏移量"
processSymbol: "δ"
csvFile: "/cases/mdm_case5_results.csv"
architecture: "case5"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1
params:
  - id: "beta"
    name: "形状参数"
    symbol: "β"
    state: "fixed"
    fixedValue: 2.0
    isVariable: false
    isDisplayDimension: false
  - id: "eta"
    name: "尺度参数"
    symbol: "η"
    state: "fixed"
    fixedValue: 1000
    isVariable: false
    isDisplayDimension: false
  - id: "gamma"
    name: "位置参数"
    symbol: "γ"
    state: "fixed"
    fixedValue: 1000
    isVariable: false
    isDisplayDimension: false
  - id: "sampleSize"
    name: "样本量"
    symbol: "n"
    state: "fixed"
    fixedValue: 7
    isVariable: false
    isDisplayDimension: false
  - id: "process"
    name: "偏移量"
    symbol: "δ"
    state: "fixed"
    fixedValue: 0.1
    isVariable: false
    isDisplayDimension: false
---

# MDM 案例5: 30组实际样本的MDM估计分析

## 研究背景

本案例使用 **30组真实失效数据** 来验证 MDM 算法的实际估计性能。所有数据样本均来自已知参数的威布尔分布：
- **形状参数**: β = 2
- **尺度参数**: η = 1000
- **位置参数**: γ = 1000
- **样本量**: n = 7（每组）

## 研究目标

1. 评估 MDM 算法在小样本（n=7）下的估计精度
2. 分析估计偏差的统计特性（均值、标准差）
3. 可视化梯度曲线，展示算法收敛过程

## 参数设置

- **真实参数**: β=2, η=1000, γ=1000
- **样本量**: n=7
- **偏移值**: δ=0.1
- **总样本数**: 30组（6组 × 每组5个样本）

## 数据说明

结果文件包含每个模拟的：
- 样本编号（Sample-X-Y）
- 估计参数值（est_beta, est_eta, est_gamma）
- 偏差值（bias_beta, bias_eta, bias_gamma）

## 关键发现

1. **β估计系统性偏差**: 所有30个样本的β估计值均约为1.75，与真实值2.0相差约-0.25，表明MDM算法在小样本下对β存在系统性低估。

2. **η与γ估计波动较大**: η的偏差范围为[-686, +481]，γ的偏差范围为[-483, +621]，标准差均超过300，说明小样本下尺度参数和位置参数估计不稳定。

3. **梯度收敛性**: 所有样本的梯度曲线在δ=0.1附近均存在交点，表明MDM算法具有良好的收敛特性。

## 方法说明

**MDM（最小差异法）**通过最小化对数项与求和项的差异来估计威布尔分布参数：

```
目标函数 = |(β-1) × Σln(x-γ) - n × (mean((x-γ)/η)^β - 1)|
```

其中 x 为观测数据，γ 的搜索范围设为 [0.5×t_min, 0.999999×t_min]，偏移量 δ = 0.1 控制搜索下限。

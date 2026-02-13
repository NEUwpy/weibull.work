---
id: "case-4"
name: "案例4: 新MDM算法多维度研究 (125,000组)"
description: "研究形状参数、样本量、偏移量对新MDM三参数估计结果的影响。基于125,000次蒙特卡洛模拟（25种参数组合 × 1000次重复），其中无解情况被保留并标记为NaN。"
processName: "偏移量"
processSymbol: "δ"
csvFile: "/cases/mdm_case4_full.csv"
# 默认基准值（当某个参数作为变量时，其他参数固定在此值）
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
    state: "discrete"
    discreteValues: [1.5, 2.0, 3, 5, 7]
    isVariable: true
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
    state: "discrete"
    discreteValues: [5, 7, 10, 20, 30]
    isVariable: true
    isDisplayDimension: false
  - id: "process"
    name: "偏移量"
    symbol: "δ"
    state: "discrete"
    discreteValues: [0, 0.05, 0.1, 0.15, 0.2]
    isVariable: true
    isDisplayDimension: false
---

# MDM 案例4: 新MDM算法多维度研究

## 研究背景

**新MDM算法**相比老方法的改进：
1. 扩展梯度搜索范围至 `0.999999 × t_min`
2. 即使无交点也不返回 `γ=0`，而是标记为 `no_intersection`
3. 数据生成时保留所有模拟记录，无解情况用 `NaN` 标记

## 研究目标

1. 评估新MDM算法在不同参数组合下的估计性能
2. 分析无解（no_intersection）现象的发生率及其与参数的关系
3. 对比不同 β、n、δ 组合下的偏差和标准差

## 参数设置

- **真实参数**: β∈{1.5,2.0,3,5,7}, η=1000, γ=1000
- **样本量**: n∈{5,7,10,20,30}
- **偏移值**: δ∈{0,0.05,0.1,0.15,0.2}
- **总组合数**: 5×5×5 = 125种
- **每种组合**: 1000次模拟
- **总模拟次数**: 125,000次

## 数据说明

结果文件包含每个模拟的：
- 真实参数值（`beta_true`, `sample_size`, `offset_value`）
- 估计参数值（`est_beta`, `est_eta`, `est_gamma`）
- 偏差值（`bias_beta`, `bias_eta`, `bias_gamma`）
- 拟合优度（`r_squared`）
- **无解标记**: 当MDM无解时，所有估计值和统计量为 `NaN`

## 无解统计

根据数据生成结果，各β值的无解率：

| β | 无解数 | 无解率 |
|---|---------|--------|
| 1.5 | 848 | 3.4% |
| 2.0 | 1,133 | 4.5% |
| 3 | 1,624 | 6.5% |
| 5 | 2,113 | 8.5% |
| 7 | 1,707 | 6.8% |
| **总计** | **7,425** | **5.9%** |

## 关键发现

1. **无解率随β变化**: β=5时无解率最高(8.5%)，β=1.5时最低(3.4%)
2. **小样本更易无解**: n=5时无解率明显高于n=30
3. **大偏移值更易无解**: δ=0.2时无解率高于δ=0

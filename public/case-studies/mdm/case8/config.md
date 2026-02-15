---
id: "case-8"
name: "案例8: β搜索方式对比研究"
description: "对比β使用固定步长0.05遍历与Brent优化的差异"
architecture: "case8"
processName: "偏移量"
processSymbol: "δ"
csvFile: "/case-studies/mdm/case8/data.json"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1330
  sampleSize: 7
  process: 0.1
params:
  - id: "beta"
    name: "形状参数"
    symbol: "β"
    state: "discrete"
    discreteValues: [0.1, 0.15, 0.20, 0.25, 0.30]
    isVariable: true
    isDisplayDimension: false
  - id: "gamma"
    name: "位置参数"
    symbol: "γ"
    state: "continuous"
    range: [0, 1430]
    isVariable: true
    isDisplayDimension: true
  - id: "eta"
    name: "尺度参数"
    symbol: "η"
    state: "dependent"
    isVariable: false
    isDisplayDimension: false
---

## 案例8: β搜索方式对比研究

### 研究目的

对比两种β搜索方式对MDM参数估计结果的影响：

| 方式 | 描述 | 特点 |
|------|------|------|
| **Brent优化** (案例7) | 连续优化，自动收敛 | 精度高，计算量小 |
| **固定步长0.05** (案例8) | 离散遍历 β=0.10, 0.15, 0.20, ... | 直观，精度受步长限制 |

### 数据来源

实际样本 (n=7): 1430.7, 2632.9, 1463.4, 1469.5, 2020.0, 1620.9, 1811.3

### 测试策略

1. **60次迭代** (γ等距60点)
2. **30次迭代** (γ等距30点)
3. **15次迭代** (γ等距15点)
4. **离散搜索** (γ间隔100)

每种策略测试 δ=0.1 和 δ=0.15 两个偏移值。

### 关键问题

1. β步长0.05的精度是否足够？
2. 与Brent优化相比，结果差异有多大？
3. 在什么情况下固定步长会漏掉最优解？

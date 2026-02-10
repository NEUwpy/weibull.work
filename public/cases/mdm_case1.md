---
id: "case-1"
name: "案例1: 多维度参数影响研究"
description: "研究形状参数、样本量、偏移量对MDM三参数估计结果的影响。基于100次蒙特卡洛模拟的预设分析结果。"
processName: "偏移量"
processSymbol: "δ"
csvFile: "/cases/mdm_case1_full.csv"
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

# MDM 案例1: 多维度参数影响研究

研究形状参数、样本量、偏移量对MDM三参数估计结果的影响。基于100次蒙特卡洛模拟的预设分析结果。

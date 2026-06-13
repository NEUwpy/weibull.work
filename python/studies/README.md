# 方法示例通用仿真程序

> 当前状态（2026-06）：本文件描述的是旧的“每个方法一个 simulate.py”的适用范围分片生成流程。该流程仍用于兼容旧 `public/studies/*` 数据。新的蒙特卡洛、真值抽样、API 现场模拟和实验产物保存，应优先阅读并使用 `python/studies/common/README.md`。
> 新实验不要复制 `mdm/mle/wmle/simulate.py`；应走 `python/studies/common/{sample.py, runner.py, simulation.py, experiment.py, metrics.py}`。

## 概述

本目录包含各参数估计方法的通用仿真脚本，用于生成蒙特卡洛模拟数据。

## 目录结构

```
python/studies/
├── README.md           # 本说明文档
├── mdm/                # MDM 方法
│   └── simulate.py     # MDM 通用仿真脚本
├── wmle/               # WMLE 方法（待添加）
│   └── simulate.py
└── ...                 # 其他方法
```

## 使用方法

### 基本用法

```bash
cd python/studies/mdm
python simulate.py <study_id>
```

例如：
```bash
python simulate.py demo1
```

### 前置条件

1. 配置文件位于 `public/studies/mdm/<study_id>/config.md`
2. 配置文件必须包含 YAML front matter，定义参数和仿真设置

## 配置文件格式

### 完整示例

```yaml
---
id: "demo-1"
name: "示例1: MDM多维度研究"
description: "研究形状参数、样本量、偏移量对MDM三参数估计结果的影响。"
method: "mdm"

# 默认基准值（当某个参数作为变量时，其他参数固定在此值）
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1

# 仿真设置
simulation:
  mcRuns: 1000              # 每组参数组合的蒙特卡洛重复次数

# MDM 计算设置
calculation:
  gammaSteps: 60            # 每轮迭代步数 (默认 60)
  rankMethod: "bernard"     # 中位秩方法: "bernard" 或 "exact" (默认 "bernard")
  betaBounds: [0.1, 15.0]   # beta 搜索范围 (可选)
  gammaRangeRound1: [0, 0.99]     # 第一轮 gamma 搜索范围 (可选)
  gammaRangeRound2: [0.99, 0.999999]  # 第二轮 gamma 搜索范围 (可选)

# 参数配置
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
```

### 参数说明

#### params 参数配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 参数标识 (beta, eta, gamma, sampleSize, process) |
| `name` | string | 参数名称 |
| `symbol` | string | 参数符号 (用于显示) |
| `state` | string | 参数状态: `fixed`, `discrete`, `range` |
| `fixedValue` | number | 固定值 (state=fixed 时) |
| `discreteValues` | array | 离散取值列表 (state=discrete 时) |
| `range` | object | 范围 {min, max} (state=range 时) |
| `isVariable` | bool | 是否为变量（参与参数组合） |
| `isDisplayDimension` | bool | 是否为显示维度 |

#### simulation 仿真设置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `mcRuns` | int | 1000 | 每组参数组合的蒙特卡洛重复次数 |

#### calculation 计算设置 (MDM)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `gammaSteps` | int | 60 | 每轮迭代步数 |
| `rankMethod` | string | "bernard" | 中位秩计算方法 |
| `betaBounds` | [min, max] | [0.1, 15.0] | beta 搜索范围 |
| `gammaRangeRound1` | [min, max] | [0, 0.99] | 第一轮 gamma 搜索范围 (相对 t_min) |
| `gammaRangeRound2` | [min, max] | [0.99, 0.999999] | 第二轮 gamma 搜索范围 (相对 t_min) |

### 中位秩方法

| 方法 | 公式 | 说明 |
|------|------|------|
| `bernard` | `(i - 0.3) / (n + 0.4)` | Bernard 近似法，计算简单 |
| `exact` | `betaincinv(i, n-i+1, 0.5)` | 精确中位秩，使用逆不完全 Beta 函数 |

## 输出文件

### data.csv

仿真结果数据，包含以下列：

| 列名 | 说明 |
|------|------|
| 变量参数列 | 配置中 isVariable=true 的参数 |
| `sim_id` | 模拟序号 |
| `est_beta` | 估计的 β 值 |
| `est_eta` | 估计的 η 值 |
| `est_gamma` | 估计的 γ 值 |
| `bias_beta` | β 偏差 (估计值 - 真实值) |
| `bias_eta` | η 偏差 |
| `bias_gamma` | γ 偏差 |
| `r_squared` | R² 拟合优度 |

### summary.json

汇总统计信息：

```json
{
  "config": "demo-1",
  "total_combinations": 125,
  "mc_runs": 1000,
  "total_runs": 125000,
  "no_solution_count": 7425,
  "gamma_steps": 60,
  "rank_method": "bernard",
  "variable_params": ["beta", "sampleSize", "process"],
  "param_values": {
    "beta": [1.5, 2.0, 3, 5, 7],
    "sampleSize": [5, 7, 10, 20, 30],
    "process": [0, 0.05, 0.1, 0.15, 0.2]
  }
}
```

## 设计原则

### 1. 配置驱动

所有仿真参数从 `config.md` 读取，不在代码中硬编码。

### 2. 通用复用

一个方法维护一个 `simulate.py`，通过参数配置支持多种示例场景。

### 3. 与前端一致

配置格式与前端 `UniversalStudyViewer` 组件一致，实现前后端参数共享。

## 添加新示例

1. 在 `public/studies/mdm/` 下创建新目录（如 `demo2/`）
2. 创建 `config.md` 配置文件
3. 运行仿真：`python simulate.py demo2`
4. 在前端选择新示例即可展示

## 故障排查

### 常见问题

1. **配置文件找不到**
   - 检查路径是否正确
   - 确认 `study_id` 与目录名一致

2. **无解记录过多**
   - 检查偏移量 `process` 设置是否合理
   - 尝试增加 `gammaSteps` 提高精度

3. **运行时间过长**
   - 减少 `mcRuns` 进行快速测试
   - 减少变量参数的取值数量

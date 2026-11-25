# 旧示例仿真工具

这份说明用于维护旧适用范围示例的 `simulate.py`。新实验、真值抽样和 API 现场模拟使用[统一蒙特卡洛流水线](common/README.md)。网页查看登记批次见[结果分析开发说明](../../docs/development/applicability.md#现行工作簿入口)，旧 CSV 的位置和接口见[外部运行数据](../../docs/data/README.md#旧研究分片)。

## 查看旧示例状态

在软件仓根目录执行下列命令查看 [MLE demo1](../../public/studies/mle/demo1/config.md)。旧工具按方法和示例读取仓内 YAML 配置，结果写入[外部数据根](../../docs/data/README.md#当前目录与读取)。本仓跟踪的示例配置可在 [public/studies](../../public/studies/README.md) 查找。

```powershell
.\python\.venv\Scripts\python.exe -X utf8 .\python\studies\mle\simulate.py demo1 --status
```

复跑旧示例前先核对原配置、算法版本和外部输出目录。下面保留 MDM 的配置结构与输出字段，供解释既有记录。

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

## 故障排查

### 常见问题

1. **配置文件找不到**
   - 检查路径是否正确
   - 确认 `study_id` 与目录名一致

2. **无解记录过多**
   - 检查偏移量 `process` 设置是否合理
   - 按原配置核对 `gammaSteps` 和求解器版本

3. **运行时间过长**
   - 减少 `mcRuns` 进行快速测试
   - 减少变量参数的取值数量

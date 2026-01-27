---
method_id: "template"
method_name: "算法名称"
short_name: "CODE"
category: "类别名称"

# 核心信息
formula: "核心公式LaTeX代码"
description: "算法简短描述，1-2句话说明核心特点和用途"

# 变量说明
variables:
  - symbol: "β"
    description: "形状参数"
    range: "β > 0"
  - symbol: "η"
    description: "尺度参数（特征寿命）"
    range: "η > 0"
  - symbol: "γ"
    description: "位置参数（最小寿命）"
    range: "γ ≥ 0"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入数据 X] --> B[数据预处理<br/>排序、确定范围]
    B --> C[参数估计<br/>计算 β, η, γ]
    C --> D{收敛?}
    D -->|否| C
    D -->|是| E[输出结果<br/>β, η, γ]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true

# 相关文献
references:
  - id: "000-000"
    title: "文献标题"
    author: "作者姓名"
    year: "年份"
    publication: "期刊名称"
---

# {method_name} ({short_name})

## 算法原理

[简要描述算法的核心思想和原理...]

**核心思想**：[一句话概括核心创新点或优势]

## 威布尔分布基础

概率密度函数（PDF）：

$$
f(x | \beta, \eta, \gamma) = \frac{\beta}{\eta} \left( \frac{x - \gamma}{\eta} \right)^{\beta - 1} \exp\left[ -\left( \frac{x - \gamma}{\eta} \right)^\beta \right]
$$

累积分布函数（CDF）：

$$
F(x | \beta, \eta, \gamma) = 1 - \exp\left[ -\left( \frac{x - \gamma}{\eta} \right)^\beta \right]
$$

## 估计方程

[在此详细描述算法的估计方程和求解方法]

$$
\text{估计方程}
$$

### 变量说明

| 符号 | 说明 | 单位/范围 |
|------|------|----------|
| $\beta$ | 形状参数 | $\beta > 0$ |
| $\eta$ | 尺度参数（特征寿命） | $\eta > 0$ |
| $\gamma$ | 位置参数（最小寿命） | $\gamma \geq 0$ |

## 算法流程详解

### 输入
- 失效数据数组 X = [x₁, x₂, ..., xₙ]
- 样本量 n ≥ 3

### 步骤

1. **数据预处理**
   - 排序数据
   - 确定参数搜索范围

2. **参数估计**
   - [步骤描述]

3. **结果验证**
   - [验证方法]

### 输出
```python
{
    "beta": 形状参数估计值,
    "eta": 尺度参数估计值,
    "gamma": 位置参数估计值,
    "success": 是否成功,
    "message": 状态信息
}
```

## 适用场景详解

| 场景 | 说明 |
|------|------|
| **完全样本** | [说明是否支持及注意事项] |
| **截尾样本** | [说明是否支持及注意事项] |
| **小样本** | [说明是否支持及注意事项] |
| **大样本** | [说明是否支持及注意事项] |

## 优缺点分析

### 优点
- 优点1
- 优点2

### 缺点
- 缺点1
- 缺点2

## 与其他方法对比

| 方法 | 小样本偏差 | 计算复杂度 | 其他特点 |
|------|----------|-----------|---------|
| 本方法 | - | - | - |
| MLE | 高 | 中 | 大样本最优 |
| LRE | 低 | 低 | 简单易用 |

## 参考文献

[1] 作者. 文献标题. *期刊名称*, 年份, 卷(期): 页码.

---

**相关文献**：详见 [000-000](/library/000-000) 完整论文

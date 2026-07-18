---
method_id: "lse"
method_name: "最小二乘估计"
short_name: "LSE"
category: "极小化适配法"

# 核心信息
formula: '\log(t_i - \mu) = \alpha + \beta X_i, \quad X_i = E[W_{(i:n)}], \quad \hat{\mu} = \arg\max_{\mu} F(\mu)'
description: "最小二乘估计（Least Squares Estimation, LSE）将威布尔分布线性化后用最小二乘回归求参数。本实现采用 White (1969) 的对数威布尔顺序统计量期望作为回归自变量，并按 Soman & Misra (1992) 的三参数扩展：对位置参数 μ 做一维搜索，以 Fisher F 比最大的 μ 为估计值。适用于形状参数 0~3 等 MLE 失效的场合。"

# 变量说明
variables:
  - symbol: "c (β)"
    description: "形状参数（论文符号 c，系统符号 β）"
    range: "c > 0"
  - symbol: "b (η)"
    description: "尺度参数（论文符号 b，系统符号 η）"
    range: "b > 0"
  - symbol: "μ (γ)"
    description: "位置参数（论文符号 μ，系统符号 γ；平台工程约束 μ ≥ 0）"
    range: "0 ≤ μ < min(t)"
  - symbol: "X_i"
    description: "reduced Log-Weibull 分布 i 阶顺序统计量的期望（White 1969）"
    range: "-"
  - symbol: "F"
    description: "Fisher F 比 = S_y²/S_res²，衡量回归直线拟合优度"
    range: "F > 0"
  - symbol: "n"
    description: "样本量"
    range: "n ≥ 3"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入数据 t] --> B[计算 X_i = E W_i:n]
    B --> C[对候选 μ 回归<br/>log t-μ = α + βX]
    C --> D[计算 F 比]
    D --> E{F 最大?}
    E -->|否| C
    E -->|是| F[输出 c=1/β, b=e^α, μ]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true

# 相关文献
references:
  - id: "182-104"
    title: "A Least Square Estimation of Three Parameters of a Weibull Distribution"
    author: "Soman, K. P., Misra, K. B."
    year: "1992"
    publication: "Microelectronics Reliability"
  - id: "182-096"
    title: "Comparison of Estimators of the Weibull Distribution"
    author: "Akram, M., Hayat, A."
    year: "2014"
    publication: "Journal of Statistical Theory and Practice"
---

# 最小二乘估计 (LSE)

## 1. 基本思想

对两参数威布尔分布，分布函数取对数可线性化：

$$
\log(t_i) = \log(b) + \frac{1}{c}\log[-\log\{1 - F(t_i)\}]
$$

记 $Y_i = \log(t_i)$、$X_i = \log[-\log\{1-F(t_i)\}]$，即直线关系 $Y_i = \alpha + \beta X_i$，其中 $\alpha = \log(b)$、$\beta = 1/c$。

$X_i$ 未知，但它们是 **reduced Log-Weibull 分布**（密度 $h(w) = e^{w-e^w}$）的顺序统计量。White (1969) 建议用其 i 阶顺序统计量的**期望** $E[W_{(i:n)}]$ 代替 $X_i$，再做最小二乘回归：

$$
\hat{b} = e^{\hat{\alpha}}, \qquad \hat{c} = 1/\hat{\beta}
$$

本实现用数值积分精确计算 $E[W_{(i:n)}]$（对数密度域积分，避免大样本二项式交替求和的数值抵消），不依赖外部数表。

## 2. 三参数扩展（Soman & Misra 1992）

对三参数分布，位置参数 $\mu$ 通过一维搜索确定：

1. 取候选 $\hat\mu$（从 $t_{(1)}$ 附近向 0 递减）；
2. 对每个 $\hat\mu$，用平移数据 $t_i - \hat\mu$ 做 White 回归，得 $\hat{b}$、$\hat{c}$；
3. 计算 Fisher F 比

$$
F = \frac{S_y^2}{S_{res}^2}, \quad
S_y^2 = \frac{1}{n-1}\sum(Y_i - \bar{Y})^2, \quad
S_{res}^2 = \frac{1}{n-2}\sum(Y_i - \hat{Y}_i)^2
$$

4. 取使 $F$ 最大的 $(\hat\mu, \hat{c}, \hat{b})$ 为最终估计。

F 比越大说明直线拟合越好，即该 $\mu$ 下变换后的数据最接近两参数威布尔。

本实现在 $[0, t_{(1)})$ 上用几何加密网格扫描 $F(\mu)$ 并做局部精化，等价于论文的"逐步缩减 μ、取 F 最大"过程，但分辨率更高。

## 3. 适用范围

论文指出该方法在形状参数 $0 < c < 3$ 时模拟效果很好——这恰是 MLE 不适用的区域（$c<1$ 似然无界、$1<c<2$ 非正则）。对 $c > 3$ 论文另有两种近似方法（基于一阶顺序统计量均值-3.3 倍标准差），本实现不包含；实测 White 回归的 F 最大化在 $c>3$ 时仍可给出合理估计，但精度下降。

## 4. 边界与失败语义

- 平台工程约束 $0 \leq \mu < t_{(1)}$（与 MLE/WMLE/MDM 一致）；无约束最优若在 $\mu<0$，估计将停在 $\mu=0$ 边界并记录 `location_at_zero_boundary` 诊断。
- $n < 3$：回归与 F 比无自由度，显式失败 `insufficient_sample`。
- 退化样本（对数寿命极差低于浮点噪声级）：显式失败 `degenerate_sample`，不输出伪结果。
- 回归斜率非正（理论上仅退化样本发生）：显式失败 `invalid_fit`。

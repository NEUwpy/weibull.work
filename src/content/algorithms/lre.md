---
method_id: "lre"
method_name: "线性回归估计"
short_name: "LRE"
category: "线性回归法"

# 核心信息
formula: '\hat{\gamma} = \arg\max_\gamma \rho^2(\gamma), \quad \rho = \mathrm{corr}(\ln(t-\gamma), \ln(-\ln(1-\hat{F})))'
description: "线性回归估计（Linear Regression Estimation, LRE）是工程最基础的威布尔参数估计方法。通过最大化相关系数平方确定位置参数 γ，再用最小二乘回归解出形状和尺度。本实现基于 Li (1994) 的变换 (2-4)（等同 Park (2017) 的 Weibull 图相关系数法确定 γ 的思想），不要求迭代交点求解，也与 Park 建议的 2P MLE 后一步不同——LRE 用 OLS 一次给出全部三参数。"

# 变量说明
variables:
  - symbol: "β"
    description: "形状参数（回归斜率）"
    range: "β > 0"
  - symbol: "η"
    description: "尺度参数"
    range: "η > 0"
  - symbol: "γ"
    description: "位置参数（平台工程约束 γ ≥ 0）"
    range: "0 ≤ γ < t_(1)"
  - symbol: "ρ"
    description: "Pearson 相关系数（平方值作为目标函数）"
    range: "ρ ∈ [0, 1]"
  - symbol: "F̂"
    description: "中位秩估计（默认 Bernard 近似）"
    range: "(0, 1)"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入数据 t] --> B[计算中位秩 v=ln-ln 1-F]
    B --> C[优化 γ 使相关系数平方最大]
    C --> D[OLS 回归<br/>ln t-γ 对 v]
    D --> E[β = 斜率, η = e^{-截距/β}]
    E --> F[输出 β, η, γ, R²]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: true
  small_sample: true
  large_sample: true

# 相关文献
references:
  - id: "182-107"
    title: "A General Linear-Regression Analysis Applied to the 3-Parameter Weibull Distribution"
    author: "Li, Y.-M."
    year: "1994"
    publication: "IEEE Transactions on Reliability"
  - id: "182-106"
    title: "A Note on the Existence of the Location Parameter Estimate of the Three-Parameter Weibull Model Using the Weibull Plot"
    author: "Park, C."
    year: "2018"
    publication: "Mathematical Problems in Engineering"
---

# 线性回归估计 (LRE)

## 1. 线性化变换

三参数威布尔 CDF 经双对数变换（Li 1994 式(2-4)，或称 Weibull 图坐标）：

$$
Y = \ln(-\ln(1 - \hat{F})), \qquad X = \ln(t - \gamma)
$$

有直线关系 $Y = \beta X - \beta \ln \eta$。因此：
- $\hat{\beta} = \mathrm{slope}(Y \sim X)$
- $\hat{\eta} = \exp(-\mathrm{intercept}/\hat{\beta})$

## 2. γ 确定：相关系数最大化

$\gamma$ 未知时，遍历候选 $\gamma$ 使 $Y \sim \ln(t-\gamma)$ 的 Pearson 相关系数平方 $\rho^2$ 最大（Li 1994 §4, (4a)；Park 2017 将此思想系统化为 Weibull 图相关系数法，Park 2018 进一步证明位置参数估计必存在于有界区间）。

本实现用数值优化器（L-BFGS-B，界 $0 \leq \gamma < t_{(1)}$）直接最大化 $\rho^2(\gamma)$，得到最优 $\gamma$ 后再做一次 OLS 回归解 $\beta$ 和 $\eta$。

## 3. 与其他方法的关系

| 方法 | γ 确定 | β, η 确定 |
|---|---|---|
| **本 LRE** | 优化 $\rho^2$ (Li/Park) | 同 $\gamma$ 下的 OLS |
| Park (2017) 全方法 | 优化 $\rho^2$ | **后一步 2P MLE** |
| Li (1994) §5 精确法 | $g_1(\gamma)$ 与 $g_2(\beta)$ 迭代交点 | 同上 |

本 LRE 是 Li (1994) §4 近似分析式(4a) 的直接实现——Park 的贡献在于 $\rho^2$ 最优化的通用性与存在性证明，不改变该方法的参数恢复合同。

## 4. 边界与失败语义

- $\gamma \geq 0$（平台工程约束）。
- 退化样本（$\ln(t-\gamma)$ 方差为零）→ 斜率分母为零 → 返回 $\beta=1$（应继续诊断，不视为成功估计；退化样本通常在 γ 优化阶段因相关系数无法定义而提前失败）。
- n < 2 时中位秩和相关系数未定义（L-BFGS-B 需要可行域，由调用层保护）。

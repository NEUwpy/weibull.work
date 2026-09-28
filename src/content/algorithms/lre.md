---
method_id: "lre"
method_name: "线性回归估计"
short_name: "LRE"
category: "线性回归法"

# 核心信息
formula: '\hat{\gamma} = \arg\max_\gamma \rho^2(\gamma), \quad \rho = \mathrm{corr}(\ln(t-\gamma), \ln(-\ln(1-\hat{F})))'
description: "本项目 LRE 与 Park（2017）的 Proposed+Plot 采用相同的估计结构：相关系数定位，再在 Weibull 概率图坐标上用 OLS 回归恢复形状和尺度。当前使用 Bernard 绘图位置，与 Park 原文不同；另有项目自己的数值搜索设置。"

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
    range: "ρ ∈ [-1, 1]"
  - symbol: "F̂"
    description: "中位秩估计（默认 Bernard 近似）"
    range: "(0, 1)"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入数据 t] --> B[计算中位秩 v=ln-ln 1-F]
    B --> C[优化 γ 使相关系数平方最大]
    C --> D[OLS 回归<br/>v 对 ln t-γ]
    D --> E["β = 斜率, η = e^{-截距/β}"]
    E --> F[输出 β, η, γ, R²]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true

# 相关文献
references:
  - id: "182-115"
    url: "https://doi.org/10.23055/ijietap.2017.24.4.2848"
    relation: "估计结构的对应文献：第5节 Proposed+Plot 使用相关系数定位加概率图线性回归；当前采用相同回归方向，但替换了绘图位置。另一个 Proposed+MLE2 分支未用于本 LRE。"
    title: "Weibullness Test and Parameter Estimation of the Three-Parameter Weibull Model Using the Sample Correlation Coefficient"
    author: "Park, C."
    year: "2017"
    publication: "International Journal of Industrial Engineering: Theory, Applications and Practice"
  - id: "182-107"
    relation: "线性化背景：式(2–4)解释 Weibull 图的直线关系；未实现其第4节位置近似或第5节联立迭代法。"
    title: "A General Linear-Regression Analysis Applied to the 3-Parameter Weibull Distribution"
    author: "Li, Y.-M."
    year: "1994"
    publication: "IEEE Transactions on Reliability"
  - id: "182-106"
    relation: "理论补充：讨论相关系数法的位置估计存在性；不是当前 OLS 步骤的唯一来源，存在性结论须在原文条件下使用。"
    title: "A Note on the Existence of the Location Parameter Estimate of the Three-Parameter Weibull Model Using the Weibull Plot"
    author: "Park, C."
    year: "2018"
    publication: "Mathematical Problems in Engineering"

# 当前实现与论文的关系
implementation:
  status: "相关系数定位与OLS的项目实现"
  summary: "估计结构对应 Park（2017）的 Proposed+Plot：相关系数定位加概率图上的线性回归。当前主要统计设置差异是采用 Bernard 绘图位置，另有数值搜索与容差差异；Li 仅作线性化背景引用。"
  differences:
    - "未实现 Li（1994）第4节的位置近似构造或第5节联立迭代算法，不能称为 Li 原方法复现。"
    - "Park（2017）同时给出 Proposed+Plot 与 Proposed+MLE2；当前回归方向与 Plot 相同，但 Bernard 绘图位置不同。Park（2018）使用的分段绘图位置也与当前不同。"
    - "Park（2017）与本实现均采用非负位置范围；本项目的线性及几何网格、局部精化和绝对数值容差是具体数值设置，不应把非负位置本身列为二者差异。"
  validation: "已有当前相关目标、OLS回代、退化样本和接口身份测试；测试文件名含 li1994 并不证明实现了 Li 算法。"
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

$\gamma$ 未知时，搜索使 $Y$ 与 $\ln(t-\gamma)$ 的 Pearson 相关系数平方 $\rho^2$ 最大的位置。该路线与 Park (2018) 讨论的 Weibull 图相关系数估计相关，但绘图位置和位置约束须单独核对；不能把原文的存在性结论直接套用于任意工程约束。

当前代码合并201点线性网格和201点几何网格，在最佳点邻域做有界标量精化，然后回归 $Y$ 对 $X$。候选位置非负；目标函数拒绝 $\gamma\geq t_{(1)}-10^{-5}$，网格另有相对最小间隔保护。这里的绝对容差依赖数据单位，不能描述为完全尺度无关。旧版 L-BFGS-B 已不代表当前实现。

默认绘图位置为 $\hat F_i=(i-0.3)/(n+0.4)$。Park (2018) 式(4)对 n≤10 使用 $(i-3/8)/(n+1/4)$，对 n≥11 使用 $(i-1/2)/n$，与本项目默认值不同。

## 3. 与其他方法的关系

**Plot 与 LRE 并不矛盾。** Plot 指 Weibull 概率图坐标；Park 的 Proposed+Plot 在这些坐标上做普通线性回归，由斜率和截距恢复形状与尺度。因此它属于概率图线性回归路线，不是仅凭肉眼画图，也不是与回归无关的另一种算法。

以 Park 原版为复现目标时，当前使用 Bernard 公式属于**绘图位置不一致**，应恢复原文设置后再核验。Bernard 本身是一种可用的绘图位置公式；保留它则须注明这是变体，不能把它称为 Park 原版，也不能据此认定它优于或劣于原版。

| 方法 | γ 确定 | β, η 确定 |
|---|---|---|
| **本 LRE** | Bernard分数下优化 $\rho^2$ | $Y$ 对 $X$ 的OLS |
| 本项目LS（Soman–Misra分支） | 次序统计量期望分数下最大化F比 | $X$ 对分数的OLS，斜率取倒数 |
| 相关法位置＋2P MLE组合 | 指定分数和可行域的相关系数法 | 固定位置后求2P MLE；是另一组合 |
| Li (1994) §4、§5 | 位置近似构造或联立曲线求解 | 应按对应原文算法实现，不能与本LRE等同 |

Li (1994) 式(2-4)支持线性化关系，但其第4节采用有限差分等构造推导位置近似，不是当前相关系数优化器的直接来源。Park (2017) 原文182-115的§2、§5和表1已核对：明确给出相关系数选位置后的Proposed+Plot与Proposed+MLE2两种组合。当前实现与Plot的回归方向相同，但使用不同绘图位置；后续2P MLE不是原文唯一版本。数值核验及原表细微差异见Research09附录B。

对于相同分数和位置，带截距OLS的F比与 $\rho^2$ 单调对应；当前LS与LRE的主要差别是分数及回归方向。版本证据、公式推导和实际样本诊断见[四方法实现核查](../../../Research/09-Weibull参数估计方法谱系与比较基线/附录B-方法实现与版本.md)。

## 4. 边界与失败语义

- $\gamma \geq 0$（平台工程约束）。
- 全等或近退化样本返回 `degenerate_sample`，不将形状1作为有效估计返回。
- n < 3 返回 `insufficient_sample`。
- 本类只接收完整样本，没有实现删失观测的秩调整或似然扩展。
- 返回的R²由基础类在双对数变换后的概率图上计算，不是原始CDF残差的R²，也不是参数估计误差。

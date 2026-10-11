---
method_id: mdm
method_name: 最小差异法
short_name: MDM
category: 极小化适配法
formula: '\beta^*(\gamma)=\arg\min_\beta\sigma_\eta(\beta,\gamma),\quad g(\gamma)=\frac{d\sigma_{\eta,\min}(\gamma)}{d\gamma},\quad g(\hat\gamma)=\delta,\quad\hat\beta=\beta^*(\hat\gamma),\quad\hat\eta=\frac1n\sum_i\eta_i(\hat\beta,\hat\gamma)'
description: 最小差异法 (MDM) 构造逐观测的伪尺度参数。当前正偏移版本先在固定位置 γ 下最小化伪尺度标准差，得到条件形状 β*(γ)，再用条件最小标准差的梯度达到 δ（如 0.1）来定位，最终尺度取伪尺度均值。该判据不同于直接对 β、γ 联合最小化标准差；当前工程实现另有非负位置处理和右端回退，回退值不等同于已验证的梯度交点。
variables:
  - symbol: t_i
    description: 第 i 个样本值
  - symbol: n
    description: 样本量
  - symbol: β
    description: 形状参数
  - symbol: η
    description: 尺度参数
  - symbol: η_i
    description: 基于第 i 个样本点估计的伪尺度参数
  - symbol: "η̄"
    description: 伪尺度参数的均值
  - symbol: γ
    description: 位置参数
  - symbol: F(t)
    description: 累积分布函数
  - symbol: σ_η
    description: 伪尺度参数的标准差
  - symbol: σ_{η,min}(γ)
    description: 固定位置γ、对形状取最小值后的条件标准差
  - symbol: β*(γ)
    description: 固定位置γ时使伪尺度标准差最小的形状
  - symbol: ∇γ
    description: 条件最小标准差关于位置参数的梯度，本文也记为g(γ)
  - symbol: δ
    description: 梯度偏移值
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true
references:
  - id: 182-030
    relation: "最小差异方法的早期研究背景；本页现行偏移判据主要对照2025年论文。"
    title: 威布尔分布参数估计的最小差异法
    author: Liyang Xie, et al.
    year: 2022
    publication: International Journal of Structural Stability and Dynamics
  - id: 182-046
    relation: "当前核心依据：伪尺度、最小差异与梯度偏移；默认秩和数值搜索存在项目改写。"
    title: 基于统计最小差异原理的Weibull分布参数估计方法
    author: 谢里阳, 朱文慧, 吴宁祥, 杨小玉
    year: 2025
    publication: 东北大学学报（自然科学版）

# 当前实现与论文的关系
implementation:
  status: "核心结构实现，默认求解经过改写"
  summary: "采用谢里阳等（2025）的最小差异与梯度偏移结构；默认改用 Bernard 秩、连续求解及非负位置处理，属于工程改写，未逐样本复现论文算例。"
  differences:
    - "默认绘图位置为 Bernard 近似；可选精确中位秩与论文式(3)对应，使用默认配置时不可称为精确秩版本。"
    - "以连续形状优化、梯度探测、Brent定根及右端回退处理位置求解，替代论文离散搜索；形状范围0.1–15，位置非负，g(0)≥δ时按项目规则返回零位置。右端回退使用虚拟梯度，未验证回退位置满足梯度判据。"
  validation: "已有精确中位秩公式、理想样本、尺度回代与偏移方向测试；论文未给出完整数值的样本A/B不能据此声称已逐样本复现。"
---

# 算法原理

## 1. 基本思想

最小差异法（MDM）的核心思想是：如果所选择的形状参数 $\beta$ 和位置参数 $\gamma$ 是真实的，那么利用样本中每一个数据点 $t_i$ 及其对应的累积失效概率 $F(t_i)$ 反算出来的尺度参数 $\eta_i$ 之间的差异应该最小。

对于三参数威布尔分布，累积分布函数 (CDF) 为

$$
F(t) = 1 - \exp \left[ - \left(\frac{t - \gamma}{\eta}\right)^{\beta} \right]
$$

由此可构造尺度参数的**伪估计量**

$$
\eta_i = \frac{t_i - \gamma}{\left(-\ln(1 - F(t_i))\right)^{1/\beta}}
$$

其中 $F(t_i)$ 可使用中位秩公式估计。精确形式基于 F 分布中位数

$$
\hat{F}(t_{(i)}) = \frac{i}{i + (n + 1 - i) \cdot F_{2(n+1-i), 2i, 0.5}}
$$

式中 $F_{2(n+1-i), 2i, 0.5}$ 是自由度为 $2(n+1-i)$ 和 $2i$ 的 F 分布的中位数。

工程中常采用如下近似形式

$$
F(t_i) \approx \frac{i - 0.3}{n + 0.4}
$$

## 2. 最小差异准则

由于样本的随机性，计算出的 $n$ 个 $\eta_i$ 值不可能完全相等。我们用它们的标准差 $\sigma_\eta$ 来衡量这种差异

$$
\sigma_\eta(\beta, \gamma) = \sqrt{\frac{1}{n-1} \sum_{i=1}^n (\eta_i - \bar{\eta})^2}
$$

原始最小差异准则是对 $\beta$、$\gamma$ 搜索，使 $\sigma_\eta$ 最小。当前采用的正偏移版本保留固定位置下的形状极小化：

$$
\beta^*(\gamma)=\arg\min_\beta\sigma_\eta(\beta,\gamma),\qquad
\sigma_{\eta,\min}(\gamma)=\sigma_\eta(\beta^*(\gamma),\gamma).
$$

位置随后按下一节的梯度偏移判据确定，不能将这个版本概括为 $\beta$、$\gamma$ 联合最小化标准差。

## 3. 梯度偏移补偿

研究表明（[文献 182-046](/library/182-046)），由于样本的统计不确定性，尺度参数估计值标准差的条件最小值 $\sigma_{\eta,\min}(\gamma)$ 的梯度在位置参数的真实值处**未必等于零**。基于某一样本得到的梯度在真实位置参数点的值可能大于零，也可能小于零。如果简单地应用极值判据（梯度为零），对于某些样本，位置参数估计值的误差可能非常大。

为了提高稳健性，引入**偏移值 $\delta$**，即寻找位置参数 $\gamma$，使得条件最小标准差的梯度等于一个大于零的值而非零。记 $g(\gamma)=d\sigma_{\eta,\min}(\gamma)/d\gamma$；原文式(7)用前向差分评价该梯度：

$$
\nabla \gamma = \frac{\sigma_{\eta,\min}(\gamma + \Delta\gamma) - \sigma_{\eta,\min}(\gamma)}{\Delta\gamma}
$$

确定有效交点 $g(\hat\gamma)=\delta$ 后，回代条件形状并取伪尺度均值：

$$
\hat\beta=\beta^*(\hat\gamma),\qquad
\hat\eta=\frac1n\sum_{i=1}^n\eta_i(\hat\beta,\hat\gamma).
$$

当前程序在内部点用中心差分，零位置附近用前向差分，最小观测附近用后向差分；它们是上述梯度的数值评价规则。

根据 [文献 182-046](/library/182-046) 的研究（基于 120 个参数估计案例，以及形状参数 $\beta$ 在 2~5 范围内的近千个样本），偏移值取 $\delta = 0.1$ 效果良好。

> **注**：偏移值的最优取法可能与样本特征和样本量有关，仍需进一步研究。

## 4. 当前数值求解与回退

当前系统的默认 MDM 保留 182-046 的“廓线 + 偏移判据”思想。系统仍然生成从接近 $t_{(1)}$ 向 0 展开的几何加密 $\gamma$ 采样点，用于记录 $\sigma_{\eta,\min}(\gamma)$、$\beta^*(\gamma)$ 和廓线梯度。这里的梯度曲线与后端求解器使用同一个 $g(\gamma)$ 计算函数；最终返回点及其求解分支也会写入 trace。

当前求解器的实际分支为：

1. 探测 $\gamma=0$ 处的廓线梯度 $g(0)$；
2. 若 $g(0)\ge\delta$，按项目的非负位置处理规则返回

$$
\hat{\gamma}=0
$$

并标记为 `truncated_at_zero`。梯度非单调时，仅凭 $g(0)$ 不能证明所有无约束交点都在负半轴；
3. 若 $g(0)<\delta$，系统探测接近 $t_{(1)}$ 的右端锚点。锚点梯度达到阈值时，与零位置形成变号括弧，使用 Brent 定根求解

$$
g(\hat{\gamma})=\delta,\quad \hat{\gamma}\in(0,t_{(1)})
$$

并标记为 `brent_root`。如果右端锚点梯度仍低于 $\delta$，当前程序直接返回紧邻 $t_{(1)}$ 的浮点位置，并把虚拟梯度记录为 $\delta$，标记 `root_solver=right_edge_fit`。这是右端回退，未验证该位置满足 $g(\hat\gamma)=\delta$；内部可能仍有被探测遗漏的交点。

项目此前约定多个交点时取最靠近 $t_{(1)}$ 的有效交点（见[既有选根定义](../../../Research/02-MDM根存在条件与稳健求解/history/对MDM方法有解性的证明/full.md)第2.2节）；182-046没有明确规定多根的选择规则。当前离散诊断遵循该约定，但默认 Brent 括弧与右端回退尚不能保证按该规则返回。有效梯度交点、零位置处理和右端回退应分别解释，不能统一声称为“始终有方程解”。

`gamma_steps` 仍然是有意义的参数，它表示后端过程曲线的采样密度。为了避免旧均匀网格在靠近 $t_{(1)}$ 的位置漏掉交点，S4.9 起默认 trace 采样使用几何加密：

$$
\gamma_j = t_{(1)} - d_j,\quad d_j \in \operatorname{geomspace}(\epsilon, t_{(1)})
$$

这样既保留了原文的离散过程，也提高了靠近最小样本点区域的分辨率。
计算过程记录保留 `solution_strategy`、`root_solver` 及 `legacy_grid_crossing`。解释结果时需结合这些字段区分 Brent 定根、零位置处理与右端回退；`right_edge_fit` 的虚拟梯度不能作为交点核验值。


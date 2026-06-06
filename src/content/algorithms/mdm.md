---
method_id: mdm
method_name: 最小差异法
short_name: MDM
category: 极小化适配法
formula: \min_{\beta, \gamma} \sigma_\eta \quad \text{其中} \quad \eta_i = \frac{t_i - \gamma}{\left(-\ln(1-F(t_i))\right)^{1/\beta}}
description: 最小差异法 (MDM) 是一种基于统计最小差异原理的参数估计方法。该方法通过构造尺度参数的伪估计量，寻找使各个样本点估计的尺度参数之间差异（标准差）最小的形状参数和位置参数。为了克服小样本下的不确定性，MDM 引入梯度偏移判据（如一阶导数等于 0.1 而非 0）；当前工程实现使用 g(0) 探测、右端近 t_min 括弧和 Brent 定根，并在 gamma>=0 约束下处理负半轴交点的边界截断。
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
  - symbol: ∇γ
    description: 标准差关于位置参数的梯度
  - symbol: δ
    description: 梯度偏移值
applicability:
  complete_sample: true
  censored_sample: true
  small_sample: true
  large_sample: true
references:
  - id: 182-030
    title: 威布尔分布参数估计的最小差异法
    author: Liyang Xie, et al.
    year: 2022
    publication: International Journal of Structural Stability and Dynamics
  - id: 182-046
    title: 基于统计最小差异原理的Weibull分布参数估计方法
    author: 谢里阳, 朱文慧, 吴宁祥, 杨小玉
    year: 2025
    publication: 东北大学学报（自然科学版）
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

MDM 方法通过二维搜索寻找 $\hat{\beta}$ 和 $\hat{\gamma}$，使得 $\sigma_\eta$ 最小。

## 3. 梯度偏移补偿

研究表明（[文献 182-046](/library/182-046)），由于样本的统计不确定性，尺度参数估计值标准差的条件最小值 $\sigma_{\eta,\min}(\gamma)$ 的梯度在位置参数的真实值处**未必等于零**。基于某一样本得到的梯度在真实位置参数点的值可能大于零，也可能小于零。如果简单地应用极值判据（梯度为零），对于某些样本，位置参数估计值的误差可能非常大。

为了提高稳健性，引入**偏移值 $\delta$**，即寻找位置参数 $\gamma$，使得标准差的梯度等于一个大于零的值而非零。梯度的离散定义为

$$
\nabla \gamma = \frac{\sigma_{\eta,\min}(\gamma + \Delta\gamma) - \sigma_{\eta,\min}(\gamma)}{\Delta\gamma}
$$

根据 [文献 182-046](/library/182-046) 的研究（基于 120 个参数估计案例，以及形状参数 $\beta$ 在 2~5 范围内的近千个样本），偏移值取 $\delta = 0.1$ 效果良好。

> **注**：偏移值的最优取法可能与样本特征和样本量有关，仍需进一步研究。

## 4. 离散 trace 与始终有解求解器

当前系统的默认 MDM 保留 182-046 的“廓线 + 偏移判据”思想。系统仍然生成从接近 $t_{(1)}$ 向 0 展开的几何加密 $\gamma$ 采样点，用于记录 $\sigma_{\eta,\min}(\gamma)$、$\beta^*(\gamma)$ 和廓线梯度。这里的梯度曲线与后端求解器使用同一个 $g(\gamma)$ 计算函数；最终根点也会写入 trace，因此前端展示的是本次后端求解过程，而不是另一套离散近似。

实际求解器按 `full.md` 第 9.1 节执行：

1. 探测 $\gamma=0$ 处的廓线梯度 $g(0)$；
2. 若 $g(0)\ge\delta$，说明无约束 offset-root 落在负半轴，按 $\gamma\ge0$ 约束返回

$$
\hat{\gamma}=0
$$

并标记为 `truncated_at_zero`；
3. 若 $g(0)<\delta$，则根应落在 $(0,t_{(1)})$ 内。系统主动选取极贴近 $t_{(1)}$ 的右端锚点形成括弧，再使用 Brent 定根求解

$$
g(\hat{\gamma})=\delta,\quad \hat{\gamma}\in(0,t_{(1)})
$$

并标记为 `brent_root`。如果当前右端锚点的梯度仍低于 $\delta$，这表示采样点没覆盖贴近 $t_{(1)}$ 的急升段，不表示 MDM 无解；系统应利用右端锚点和 $t_{(1)}$ 近端构造拟合/括弧并补出交点，trace 中标记 `root_solver=right_edge_fit`。

`gamma_steps` 仍然是有意义的参数，它表示后端过程曲线的采样密度。为了避免旧均匀网格在靠近 $t_{(1)}$ 的位置漏掉交点，S4.9 起默认 trace 采样使用几何加密：

$$
\gamma_j = t_{(1)} - d_j,\quad d_j \in \operatorname{geomspace}(\epsilon, t_{(1)})
$$

这样既保留了原文的离散过程，也提高了靠近最小样本点区域的分辨率。
计算过程可视化会标明本次结果来自 `brent_root` 或 `truncated_at_zero`，并保留 `legacy_grid_crossing` 字段说明同源 trace 采样点是否也观察到交点。


---
method_id: mdm
method_name: 最小差异法
short_name: MDM
category: 极小化适配法
formula: \min_{\beta, \gamma} \sigma \left( \frac{t_i - \gamma}{[-\ln(1-F_i)]^{1/\beta}} \right)
description: 最小差异法 (Minimum Discrepancy Method, MDM) 是一种基于统计最小差异原理的参数估计方法。该方法通过构造尺度参数的伪估计量，利用递归算法寻找使各个样本点估计的尺度参数之间差异（标准差）最小的形状参数和位置参数。为了克服小样本下的不确定性，MDM 引入了梯度偏移判据（如一阶导数等于 0.1 而非 0），显著提高了估计的稳健性和准确性。
variables:
  - symbol: η_i
    description: 基于第 i 个样本点估计的伪尺度参数
  - symbol: σ_η
    description: 一组伪尺度参数的标准差，反映估计的一致性
  - symbol: ∇(γ)
    description: 标准差最小值关于位置参数 γ 的梯度
  - symbol: δ
    description: 偏移值（通常取 0.1），用于补偿样本不确定性
flowchart: |
  flowchart TD
    A["输入样本数据 t"] --> B["初始化位置参数 γ 范围"]
    B --> C{"遍历 γ"}
    C -->|固定 γ| D["搜索最佳 β"]
    D --> E["计算尺度参数标准差 σ_min(γ)"]
    E --> F["计算梯度 ∇(γ)"]
    F --> C
    C -->|结束遍历| G["寻找 ∇(γ) ≈ 0.1 的点"]
    G --> H["输出最终参数 γ, β, η"]
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

最小差异法（MDM）的核心思想是：如果所选择的形状参数 $\beta$ 和位置参数 $\gamma$ 是真实的，那么利用样本中每一个数据点 $t_i$ 及其对应的累积失效概率 $F(t_i)$ 反算出来的尺度参数 $\eta_i$ 应该彼此相等（或差异最小）。

对于三参数威布尔分布，累积分布函数 (CDF) 为：
$$F(t) = 1 - \exp \left[ - \left(\frac {t - \gamma}{\eta}\right) ^ {\beta} \right]$$

由此可构造尺度参数的**伪估计量**：
$$\eta_i = \frac {t_i - \gamma}{(- \ln (1 - F (t_i))) ^ {1 / \beta}}$$

其中 $F(t_i)$ 通常使用中位秩公式估计：
$$F(t_i) \approx \frac{i - 0.3}{n + 0.4}$$

## 2. 最小差异准则

由于样本的随机性，计算出的 $n$ 个 $\eta_i$ 值不可能完全相等。我们用它们的标准差 $\sigma_\eta$ 来衡量这种差异：
$$\sigma_\eta(\beta, \gamma) = \sqrt{\frac{1}{n-1} \sum_{i=1}^n (\eta_i - \bar{\eta})^2}$$

MDM 方法通过二维搜索寻找 $\hat{\beta}$ 和 $\hat{\gamma}$，使得 $\sigma_\eta$ 最小。

## 3. 梯度偏移补偿

研究（文献 182-046）发现，由于统计不确定性，直接寻找 $\sigma_\eta$ 的绝对最小值（即导数为 0 点）在小样本下可能导致偏差，特别是在位置参数的估计上。

为了提高稳健性，引入了**偏移值 $\delta$**（Offset Value）。即寻找位置参数 $\gamma$，使得标准差的梯度等于一个小的正数（经验值取 0.1）：

$$\nabla \gamma = \frac {\partial \sigma_ {\eta , \min } (\gamma)}{\partial \gamma} = 0.1$$

这一改进显著缩小了参数估计的误差范围，使得方法在工程应用中更加可靠。

## 4. 算法步骤

1.  **数据预处理**：对样本数据进行排序 $t_1 \le t_2 \le ... \le t_n$。
2.  **秩计算**：使用中位秩公式计算每个点的经验 CDF 值。
3.  **外层循环（位置参数 $\gamma$）**：
    *   在 $0$ 到 $t_1$ (最小样本值) 之间设定一系列 $\gamma$ 候选值。
    *   对于每一个 $\gamma$，进入内层循环。
4.  **内层循环（形状参数 $\beta$）**：
    *   搜索一个 $\beta$，使得在该 $\gamma$ 下计算出的 $n$ 个 $\eta_i$ 的标准差最小。
    *   记录该最小标准差 $\sigma_{\min}(\gamma)$。
5.  **梯度计算与寻优**：
    *   计算 $\sigma_{\min}(\gamma)$ 关于 $\gamma$ 的梯度曲线 $\nabla(\gamma)$。
    *   寻找 $\nabla(\gamma)$ 曲线与阈值 $\delta = 0.1$ 的交点。
    *   该交点对应的 $\gamma$ 即为估计的位置参数 $\hat{\gamma}$。
    *   对应的 $\beta$ 即为 $\hat{\beta}$。
6.  **尺度参数计算**：
    *   使用最终的 $\hat{\gamma}, \hat{\beta}$ 计算所有 $\eta_i$ 的均值作为 $\hat{\eta}$。

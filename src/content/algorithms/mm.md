---
method_id: "mm"
method_name: "矩估计"
short_name: "MM"
category: "矩方法"

# 核心信息
formula: '\bar{\mu}_k = \int_0^\infty [\mathrm{Sf}(x)]^k dx = a + \frac{b\,\Gamma(1+1/c)}{k^{1/c}}, \quad c^* = \frac{\ln 2}{\ln(\bar{m}_1-\bar{m}_2) - \ln(\bar{m}_2-\bar{m}_4)}'
description: "矩估计（Method of Moments, MM）的本实现采用 Cran (1988) 的 Weibull 矩：生存函数 k 次幂的积分矩。样本 Weibull 矩是观测值差分的加权和（而非幂次），且三个参数可由低阶样本矩显式解出，无需迭代。适合作快速初估，并可同时给出 2P 对照估计以判断位置参数是否为零。"

# 变量说明
variables:
  - symbol: "c (β)"
    description: "形状参数（论文符号 c，系统符号 β）"
    range: "c > 0"
  - symbol: "b (η)"
    description: "尺度参数（论文符号 b，系统符号 η）"
    range: "b > 0"
  - symbol: "a (γ)"
    description: "位置参数（论文符号 a，系统符号 γ；论文即约定 a ≥ 0）"
    range: "0 ≤ a < x_(1)"
  - symbol: "μ̄_k"
    description: "k 阶 Weibull 矩（生存函数 k 次幂的积分）"
    range: "k = 1, 2, 4"
  - symbol: "m̄_k"
    description: "k 阶样本 Weibull 矩（观测值差分加权和；m̄₁ = 样本均值）"
    range: "-"
  - symbol: "n"
    description: "样本量"
    range: "n ≥ 3"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入数据 x] --> B[样本 Weibull 矩<br/>m1, m2, m4]
    B --> C{可采纳?<br/>m1-m2 > m2-m4 > 0}
    C -->|否| D[显式失败]
    C -->|是| E[式 2a-2c 显式解<br/>c*, a*, b*]
    E --> F{a* 可采纳?}
    F -->|a*<0| G[a=0 重算 b]
    F -->|a*≥x1| H[替代式 a**]
    F -->|是| I[输出 c, b, a]
    G --> I
    H --> I

# 适用场景
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: false
  large_sample: true

# 相关文献
references:
  - id: "182-102"
    title: "Moment Estimators for the 3-Parameter Weibull Distribution"
    author: "Cran, G. W."
    year: "1988"
    publication: "IEEE Transactions on Reliability"
  - id: "182-096"
    title: "Comparison of Estimators of the Weibull Distribution"
    author: "Akram, M., Hayat, A."
    year: "2014"
    publication: "Journal of Statistical Theory and Practice"
---

# 矩估计 (MM)

## 1. Weibull 矩

Cran (1988) 采用 Weibull (1961) 定义的矩——生存函数 k 次幂的积分：

$$
\bar{\mu}_k \equiv \int_0^\infty [\mathrm{Sf}(x; a, b, c)]^k \, dx = a + \frac{b\,\Gamma(1+1/c)}{k^{1/c}}, \quad k = 1, 2, \ldots
$$

相比常规矩（Newby 1984），Weibull 矩有两个优点：

- 样本矩是观测值**差分**的函数而非幂次，数值上更稳定；
- 参数是低阶矩的**显式函数**，无需迭代求解。

## 2. 参数显式解

由 $k = 1, 2, 4$ 三阶矩可解出（论文式 2a-2c）：

$$
c = \frac{\ln 2}{\ln(\bar{\mu}_1 - \bar{\mu}_2) - \ln(\bar{\mu}_2 - \bar{\mu}_4)}, \qquad
a = \frac{\bar{\mu}_1\bar{\mu}_4 - \bar{\mu}_2^2}{\bar{\mu}_1 + \bar{\mu}_4 - 2\bar{\mu}_2}, \qquad
b = \frac{\bar{\mu}_1 - a}{\Gamma(1 + 1/c)}
$$

## 3. 样本 Weibull 矩

用样本生存函数阶梯 $1 - S_n(x)$ 替代 $\mathrm{Sf}$（论文式(3)）：

$$
\bar{m}_k = \sum_{r=0}^{n-1}\left(1 - \frac{r}{n}\right)^k (x_{(r+1)} - x_{(r)}), \quad x_{(0)} = 0
$$

特别地 $\bar{m}_1 = \bar{x}$（样本均值）。将 $\bar{m}_1, \bar{m}_2, \bar{m}_4$ 代入式 (2a-2c) 即得 $c^*, a^*, b^*$。

## 4. 可采纳性与修正

- **矩组合不可采纳**：当 $\bar{m}_2 \geq (\bar{m}_1 + \bar{m}_4)/2$（等价于 $\bar{m}_1-\bar{m}_2 \leq \bar{m}_2-\bar{m}_4$）时 $c^*, b^*$ 非正，矩估计不可用，显式失败（`inadmissible_moments`），应改用其他方法。全等值等退化样本亦落入此分支。
- **$a^* < 0$**：按论文约定取 $a = 0$，并按 $b = \bar{m}_1/\Gamma(1+1/c^*)$ 重算尺度。
- **$a^* \geq x_{(1)}$**：越过样本支撑，用论文替代式修正：

$$
a^{**} = x_{(1)} - \frac{b^*\,\Gamma(1+1/c^*)}{n^{1/c^*}}
$$

修正类型记录在求解诊断 `location_adjustment` 中，不静默。

## 5. 2P 对照与阈值判断

论文建议同时计算 $a=0$ 的两参数 Weibull 矩估计：

$$
c^{**} = \frac{\ln 2}{\ln \bar{m}_1 - \ln \bar{m}_2}, \qquad b^{**} = \frac{\bar{m}_1}{\Gamma(1+1/c^{**})}
$$

若 $(b^*, c^*)$ 与 $(b^{**}, c^{**})$ 接近且 $|a^*|/b^*$ 很小，可认为位置参数为零。本实现把 $(c^{**}, b^{**})$ 写入求解诊断供参考。

## 6. 精度定位

论文定位（SUMMARY）：Weibull 矩估计是**快速初估**工具，用于判断阈值是否存在和形状参数的量级，然后转入更高效的方法（如 MLE）。模拟表明 $a^*$ 负偏、$b^*, c^*$ 正偏，且 $c$ 增大时方差急剧增大（$c=3.5$ 时不推荐）。

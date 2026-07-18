---
method_id: "mle"
method_name: "极大似然估计"
short_name: "MLE"
category: "极大化适配法"

# 核心信息
formula: '\ln L = n \ln\beta - n\beta\ln\eta + (\beta-1)\sum_{i=1}^{n}\ln(x_i-\gamma) - \sum_{i=1}^{n}\left(\frac{x_i-\gamma}{\eta}\right)^\beta'
description: "极大似然估计（Maximum Likelihood Estimation, MLE）是统计推断中最基础且最重要的方法。通过最大化样本观测值的联合概率密度（似然函数）来估计参数。在大样本下具有渐近正态性、一致性和有效性，但在小样本下存在显著偏差。"

# 变量说明
variables:
  - symbol: "L"
    description: "似然函数 (Likelihood Function)"
    range: "L > 0"
  - symbol: "n"
    description: "样本量"
    range: "n ≥ 1"
  - symbol: "β"
    description: "形状参数"
    range: "β > 0"
  - symbol: "η"
    description: "尺度参数"
    range: "η > 0"
  - symbol: "γ"
    description: "位置参数"
    range: "0 ≤ γ < min(x)"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入据 X] --> B[初始猜测<br/>利用 LRE 估算]
    B --> C[数值优化<br/>最大化 ln L]
    C --> D{收敛?}
    D -->|否| C
    D -->|是| E[输出结果<br/>β, η, γ]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: true
  small_sample: false
  large_sample: true

# 相关文献
references:
  - id: "182-105"
    title: "Maximum Likelihood Estimation in the 3-parameter Weibull Distribution: A Look through the Generalized Extreme-value Distribution"
    author: "Hirose, H."
    year: "1996"
    publication: "IEEE Transactions on Dielectrics and Electrical Insulation"
  - id: "182-090"
    title: "Maximum likelihood estimation in a class of nonregular cases"
    author: "Smith, R. L."
    year: "1985"
    publication: "Biometrika"
  - id: "182-101"
    title: "Fitting the Three-Parameter Weibull Distribution: Review and Evaluation of Existing and New Methods"
    author: "Cousineau, D."
    year: "2009"
    publication: "IEEE Transactions on Dielectrics and Electrical Insulation"
---

# 极大似然估计 (MLE)

## 1. 基本思想

极大似然估计 (MLE) 的核心思想是：寻找一组参数 $(\hat{\beta}, \hat{\eta}, \hat{\gamma})$，使得在该组参数下，观测到当前数据集 $X = \{x_1, ..., x_n\}$ 的概率密度乘积（即似然函数）最大。

即：**已经发生的事情应该是概率最大的事情**。

## 2. 似然函数

威布尔分布的概率密度函数 (PDF)：

$$
f(x | \beta, \eta, \gamma) = \frac{\beta}{\eta} \left( \frac{x - \gamma}{\eta} \right)^{\beta - 1} \exp\left[ -\left( \frac{x - \gamma}{\eta} \right)^\beta \right]
$$

假设样本相互独立，则**似然函数**为各样本点概率密度的乘积：

$$
L(\beta, \eta, \gamma) = \prod_{i=1}^{n} f(x_i | \beta, \eta, \gamma) = \prod_{i=1}^{n} \frac{\beta}{\eta} \left( \frac{x_i - \gamma}{\eta} \right)^{\beta - 1} \exp\left[ -\left( \frac{x_i - \gamma}{\eta} \right)^\beta \right]
$$

为简化计算（将乘积转化为求和），取**对数似然函数**：

$$
\ln L = n \ln \beta - n \beta \ln \eta + (\beta - 1) \sum_{i=1}^{n} \ln(x_i - \gamma) - \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^\beta
$$

## 3. 似然方程

对 $\beta, \eta, \gamma$ 分别求偏导并令其为零：

$$
\frac{\partial \ln L}{\partial \beta} = \frac{n}{\beta} - n \ln \eta + \sum_{i=1}^{n} \ln(x_i - \gamma) - \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^\beta \ln\left( \frac{x_i - \gamma}{\eta} \right) = 0
$$

$$
\frac{\partial \ln L}{\partial \eta} = -\frac{n \beta}{\eta} + \frac{\beta}{\eta} \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^\beta = 0
$$

$$
\frac{\partial \ln L}{\partial \gamma} = -(\beta - 1) \sum_{i=1}^{n} \frac{1}{x_i - \gamma} + \frac{\beta}{\eta} \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^{\beta - 1} = 0
$$

该方程组无解析解，需通过数值方法（如 Nelder-Mead、Newton-Raphson）迭代求解。

## 4. 无界问题与非正则边界

当 $\beta < 1$ 且 $\gamma$ 未知时，似然函数可能趋向无穷大。

原因：当 $\gamma \to \min(x_i)$ 时，$x_{\min} - \gamma \to 0$，若 $\beta < 1$，则 $(x_{\min} - \gamma)^{\beta - 1} \to \infty$，导致似然函数无界。

Smith (1985) 给出非正则性的完整分类：$\beta > 2$ 时经典渐近理论成立；$1 < \beta \leq 2$ 时 MLE 存在但不渐近正态；$\beta \leq 1$ 时局部极大意义下的 MLE 可能不存在。因此本实现在优化结果 $\hat{\beta} < 1$ 时显式返回"无解"（`unbounded`），不输出伪结果，需改用 WMLE、MDM 等方法。

## 5. 参数发散问题与平台约束

Hirose (1996) 指出：对高度负偏的样本，三参数 MLE 会出现"参数发散"（$\hat{\beta} \to \infty$、$\hat{\gamma} \to -\infty$，而对数似然收敛于 Gumbel 极限）。

本平台面向寿命数据，采用工程约束 $0 \leq \gamma < \min(x_i)$：对此类发散样本，估计将收敛到 $\gamma = 0$ 边界，即两参数威布尔（W2P）的 MLE 解（与 Hirose 1996 第 5.3 节的 W2P 基准一致）。
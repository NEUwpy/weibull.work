# 图注与 Markdown 引用

以下图注是中文初稿使用版本。图内文字采用英文，便于以后直接进入英文 SCI 稿件。

## 图 1

```markdown
![样本自适应偏移量选择方法](figures/main/fig1_method_structure.png)
```

**图 1  样本自适应偏移量选择方法。** **a，** 离线训练时，同一个 Monte Carlo 样本经 26 个候选偏移量下的 MDM 估计形成实际损失曲线，同时由对应样本量的多层感知机预测损失曲线；两条曲线之间的误差用于训练网络。**b，** 应用时仅输入当前样本，网络预测 26 点损失曲线并以最低点确定 $\widehat{\delta}$，随后仍由 MDM 给出 $\widehat{\beta}$、$\widehat{\eta}$ 和 $\widehat{\gamma}$。图中曲线仅用于说明方法流程，不代表某一参数组合的数值结果。

## 图 2

```markdown
![整体偏移量风险曲线](figures/main/fig2_overall_delta_risk.png)
```

**图 2  统一偏移量与信息增加后的潜在改善。** a，26 个候选偏移量在整个设计域上的汇总 $J_1$；b，低误差区域的局部放大。最低点位于 $\delta=0.06$，经验值 $\delta=0.10$ 的误差仅略高；c，从固定经验值到逐样本 hindsight 的信息层级。统一常数的重新选择收益有限，而更多选择信息带来更大的潜在改善。

## 图 3

```markdown
![不同样本量下的主要结果](figures/main/fig3_per_n_J1.png)
```

**图 3  不同样本量下的总体与逐样本结果。** **a，** 均值归一化 MLP、固定经验偏移量和逐样本 hindsight 参照在四个已训练样本量下的 pooled $J_1$；阴影表示 Default 与 hindsight 之间的逐样本可实现空间，百分数表示样本自适应方法取得该空间的比例。**b，** 逐样本配对损失差 $\Delta\ell_i=\ell_{i,\mathrm{Default}}-\ell_{i,\mathrm{Adaptive}}$ 的分布；细线、中线、粗线和白点依次表示第 1—99、第 5—95 百分位区间、四分位距和中位数，百分数表示误差降低的样本比例。

## 图 4

```markdown
![偏移量选择机制](figures/main/fig4_selector_mechanism.png)
```

**图 4  从风险曲线预测到偏移量选择。** **a，** 折外测试样本中的中位超额损失代表例，展示实际损失曲线、预测损失曲线、所选偏移量和逐样本 hindsight 偏移量；**b，** 全部折外预测中所选偏移量与 hindsight 偏移量的对应分布，每行归一化为 100%，虚线表示完全一致；**c，** 不同样本量下相对于 hindsight 的超额损失中位数、第 90 和第 99 百分位数。该图用于解释选择过程及其误差分布，不把单个样本作为总体效果证据。

## 图 5

```markdown
![参数空间中的改善分布](figures/main/fig5_parameter_landscape.png)
```

**图 5  样本自适应选择在参数空间中的效果分布。** 四个面板分别对应 $n=7,10,15,20$，颜色表示均值归一化 MLP 相对于固定 $\delta=0.1$ 的 pooled $J_1$ 降幅。红框标出发生退化的参数组合；160 个组合中有 35 个退化，最大退化为 16.88%。该图显示汇总改善与局部退化同时存在。

## 图 6

```markdown
![支撑验证汇总](figures/main/fig6_support_validation.png)
```

**图 6  主结果的支撑验证。** a，逐一留出未参与训练的 $\beta$ 水平后，均值归一化 MLP 相对于固定偏移量的 $J_1$ 降幅，阴影为三个随机种子的范围；$\beta=1.5$ 时略为负值。b，在相同样本量分层下与 WMLE、LSE 的 pooled $J_1$ 外部参照；c，均值归一化 MLP、固定偏移量和 WMLE 对 $x_{0.90}$、$x_{0.95}$、$x_{0.99}$ 的相对 RMSE。三类结果分别回答未见参数水平、传统方法参照和参数收益能否传递到工程指标，详细分层结果见补充材料。

## 附录图

```markdown
![未见形状参数验证](figures/supplementary/supp_fig_unseen_beta.png)
![传统方法参照](figures/supplementary/supp_fig_traditional_per_n.png)
![可靠度寿命误差](figures/supplementary/supp_fig_quantile_rmse.png)
![参数引导选择负结果](figures/supplementary/supp_fig_parameter_guided.png)
```

**图 D1  未见形状参数水平验证。** 逐一留出八个 $\beta$ 水平时，均值归一化 MLP、固定偏移量和事后参照的汇总 $J_1$。蓝色阴影表示三个随机种子的范围。

**图 E1  传统方法外部参照。** 在相同 48,000 个样本和评价准则下，比较均值归一化 MLP、固定偏移量、事后参照、WMLE 和 LSE 在不同样本量下的汇总 $J_1$。

**图 E2  可靠度寿命误差。** 五种方法在 $x_{0.90}$、$x_{0.95}$ 和 $x_{0.99}$ 上的相对 RMSE。均值归一化 MLP 的误差线表示三个随机种子的范围。

**图 C1  参数引导（plug-in）偏移量选择的评价。** a，横向森林图：12 个单步参数引导变体相对固定 $\delta=0.1$ 的汇总 $J_1$ 差（横轴标签注明“positive = worse”）及其配对 repeat-block 95% 置信区间；规则按初估量分组（MDM-0.1 与 WMLE），标签含义为“$\beta$·grid / $\beta$·interp”= 仅用形状参数初估、就近网格点或连续插值，“$\beta,n$·…”= 再加样本量，“$\beta,\gamma/\eta,n$·…”= 再加位置尺度比初估。全部 12 个变体均劣于 Default，最优为 WMLE / 仅 $\beta$ / 连续插值（差 0.0203，95% CI [0.0186, 0.0219]）。b，该最优规则按真 $\beta$ 的 $J_1$ 差：仅在 $\beta=1.5$ 改善（−0.0104），$\beta=2.0$–5.0 均更差。c，MDM-0.1 与 WMLE 初步 $\hat\beta$ 落入正确 $\beta$ 网格单元的比例（诊断性指标，不作因果证明）：总体为 19.8%（MDM-0.1）和 16.5%（WMLE）。数值与置信区间定义见附录 C。

**表 C1 和表 C2** 参数引导 12 个单步与迭代变体的汇总 $J_1$、相对 Default 的 $J_1$ 差、配对 95% 置信区间，以及最佳单步规则按真 $\beta$ 的分层结果。

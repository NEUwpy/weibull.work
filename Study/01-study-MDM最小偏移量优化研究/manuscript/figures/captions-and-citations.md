# 图注与 Markdown 引用

以下图注是中文初稿使用版本。图内文字采用英文，便于以后直接进入英文 SCI 稿件。

## 图 1

```markdown
![正偏移量对估计稳定性和联合误差的影响](figures/main/fig1_offset_baseline.png)
```

**图 1  正偏移量对估计稳定性和联合误差的影响。** a，26 个候选偏移量在整个设计域上的汇总 $J_1$；b，低误差区域的局部放大；c，在每个参数组合内分别计算 300 次重复抽样的标准化估计标准差，并比较 $\delta=0$ 与 $\delta=0.10$ 在 160 个参数组合上的分布。小提琴图表示完整分布，箱体表示四分位距和中位数；百分数表示组合间中位标准差的降幅。不同真参数组合的估计值未直接混合计算标准差。

## 图 2

```markdown
![样本自适应偏移量选择方法](figures/main/fig2_adaptive_selection_method.png)
```

**图 2  样本自适应偏移量选择方法。** **a，** 离线训练时，同一个 Monte Carlo 样本经 26 个候选偏移量下的 MDM 估计形成实际损失曲线，同时由对应样本量的多层感知机预测损失曲线；两条曲线之间的误差用于训练网络。**b，** 应用时仅输入当前样本，网络预测 26 点损失曲线并以最低点确定 $\widehat{\delta}$，随后仍由 MDM 给出 $\widehat{\beta}$、$\widehat{\eta}$ 和 $\widehat{\gamma}$。图中曲线仅用于说明方法流程，不代表某一参数组合的数值结果。

## 图 3

```markdown
![不同样本量下的主要结果](figures/main/fig3_per_n_J1.png)
```

**图 3  不同样本量下的总体与逐样本结果。** **a，** 均值归一化 MLP、固定经验偏移量和逐样本事后参照在四个已训练样本量下的 pooled $J_1$；阴影只表示 Default 与 L6 的观测差距，百分数表示样本自适应方法相对 Default 的 $J_1$ 降幅。**b，** 逐样本配对损失差 $\Delta\ell_i=\ell_{i,\mathrm{Default}}-\ell_{i,\mathrm{Adaptive}}$ 的分布；细线、中线、粗线和白点依次表示第 1—99、第 5—95 百分位区间、四分位距和中位数，百分数表示误差降低的样本比例。

## 图 4

```markdown
![偏移量选择机制](figures/main/fig4_selector_mechanism.png)
```

**图 4  从风险曲线预测到偏移量选择。** **a，** 折外测试样本中的中位超额损失代表例，展示实际损失曲线、预测损失曲线、所选偏移量和逐样本 hindsight 偏移量；**b，** 全部折外预测中所选偏移量与 hindsight 偏移量的对应分布，每行归一化为 100%，虚线表示完全一致；**c，** 不同样本量下相对于 hindsight 的超额损失中位数、第 90 和第 99 百分位数。该图用于解释选择过程及其误差分布，不把单个样本作为总体效果证据。

## 图 5

```markdown
![样本实现与MDM梯度机制](figures/main/fig5_decision_mechanism.png)
```

**图 5  样本实现对 MDM 偏移量的影响。** **a，** 在相同真参数 $(\beta,\gamma/\eta,n)=(3,0.5,10)$ 下，三个确认样本产生的经验梯度曲线及各自 L6 交点；**b，** 在 20 个预设参数单元内按默认偏移量所得 $\hat\gamma_{0.1}/\eta$ 分为低、中、高三组后，26 个候选偏移量相对 L6 的平均超额损失；**c，** 各样本量下，每个参数单元内 $\hat\gamma_{0.1}/\eta$ 与 L6 偏移量的 Spearman 相关。代表样本用于展示曲线形态，统计结论来自 2,000 个独立确认样本。

## 图 6

```markdown
![支撑验证汇总](figures/main/fig6_support_validation.png)
```

**图 6  主结果的支撑验证。** a，主 seed 42 下逐一留出未参与训练的 $\beta$ 水平后，均值归一化 MLP 相对于固定偏移量的 $J_1$ 降幅；$\beta=1.5$ 时略为负值。b，在相同样本量分层下与 WMLE、LSE 的 pooled $J_1$ 外部参照；c，均值归一化 MLP、固定偏移量和 WMLE 对 $x_{0.90}$、$x_{0.95}$、$x_{0.99}$ 的相对 RMSE。三类结果分别回答未见参数水平、传统方法参照和参数收益能否传递到工程指标，初始化敏感性与详细分层结果见补充材料。

## 附录图

```markdown
![未见形状参数验证](figures/supplementary/supp_fig_unseen_beta.png)
![传统方法参照](figures/supplementary/supp_fig_traditional_per_n.png)
![可靠度寿命误差](figures/supplementary/supp_fig_quantile_rmse.png)
![参数引导选择负结果](figures/supplementary/supp_fig_parameter_guided.png)
![不同决策条件的确认风险](figures/supplementary/supp_fig_decision_conditions.png)
![参数空间中的改善分布](figures/supplementary/supp_fig_parameter_landscape.png)
![Z-only 经验参照的数据量诊断](figures/supplementary/supp_fig_z_only_learning_curve.png)
```

**图 D1  未见形状参数水平验证。** 逐一留出八个 $\beta$ 水平时，均值归一化 MLP、固定偏移量和事后参照的汇总 $J_1$。折线为主 seed 42，蓝色阴影表示三个随机种子的取值范围。

**图 E1  传统方法外部参照。** 在相同 48,000 个样本和评价准则下，比较均值归一化 MLP、固定偏移量、事后参照、WMLE 和 LSE 在不同样本量下的汇总 $J_1$。

**图 E2  可靠度寿命误差。** 五种方法在 $x_{0.90}$、$x_{0.95}$ 和 $x_{0.99}$ 上的相对 RMSE。均值归一化 MLP 的点为主 seed 42，误差线表示三个随机种子的取值范围。

**图 C1  参数引导（plug-in）偏移量选择的评价。** a，横向森林图：12 个单步参数引导变体相对固定 $\delta=0.1$ 的汇总 $J_1$ 差（横轴标签注明“positive = worse”）及其配对 repeat-block 95% 置信区间；规则按初估量分组（MDM-0.1 与 WMLE），标签含义为“$\beta$·grid / $\beta$·interp”= 仅用形状参数初估、就近网格点或连续插值，“$\beta,n$·…”= 再加样本量，“$\beta,\gamma/\eta,n$·…”= 再加位置尺度比初估。全部 12 个变体均劣于 Default，最优为 WMLE / 仅 $\beta$ / 连续插值（差 0.0203，95% CI [0.0186, 0.0219]）。b，该最优规则按真 $\beta$ 的 $J_1$ 差：仅在 $\beta=1.5$ 改善（−0.0104），$\beta=2.0$–5.0 均更差。c，MDM-0.1 与 WMLE 初步 $\hat\beta$ 落入正确 $\beta$ 网格单元的比例（诊断性指标，不作因果证明）：总体为 19.8%（MDM-0.1）和 16.5%（WMLE）。数值与置信区间定义见附录 C。

**表 C1 和表 C2** 参数引导 12 个单步与迭代变体的汇总 $J_1$、相对 Default 的 $J_1$ 差、配对 95% 置信区间，以及最佳单步规则按真 $\beta$ 的分层结果。

**图 F1  不同决策条件下的确认风险。** a，同一参数单元内 L6 事后偏移量的多样性以及 L5、论文 MLP 和灵活 $Z$-only 参照与 L6 的完全一致率；b，Default、论文 MLP、同域重训 MLP、灵活 $Z$-only 参照和 L6 在 16,000 个确认样本上的 $R=J_1^2$。经验参照不是精确 Bayes 风险。

**图 F2  参数条件下的效果分布。** 四个面板分别对应 $n=7,10,15,20$，颜色表示均值归一化 MLP 相对固定 $\delta=0.1$ 的 pooled $J_1$ 降幅。勾边标出发生退化的参数组合；160 个组合中 125 个改善，35 个退化。

**图 F3  $Z$-only 经验参照的数据量诊断。** 每个参数条件使用 40、80、120、160 和 200 个拟合 repeat 时，固定确认集上的风险。确认集不参与选模；曲线仅用于数据敏感性诊断，不证明已逼近 Bayes 风险。

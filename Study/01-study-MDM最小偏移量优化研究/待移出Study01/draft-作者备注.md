# 作者备注（写作工作稿，不属于投稿正文）

> 本文件收集 draft-Ch1-Ch2 / Ch3 / Ch4 / Ch5 初稿中的作者备注与数据溯源信息。
> 服务修稿与复核，不应被后续 agent 当作正文。
> 主稿（draft-Ch*-初稿.md）已不再包含这些区块。

---

## 【作者备注】全文术语表

| 规范写法 | 首次出现 | 禁止漂移/使用说明 |
|----------|----------|-------------------|
| Minimum Discrepancy Method（MDM） | 首次出现写全称，之后统一用 MDM | 正文不在 MDM/MDE 之间切换；讨论原始论文命名时另行说明 |
| 偏移量 `delta` | 中文正文首次写“偏移量 `delta`”，之后可简称 `delta` | 不在“offset 参数”“修正量”“小正数”之间随意换名 |
| `nabla gamma`（原文写作 `∇γ`） | Ch2 首次定义为 `sigma_eta,min(gamma)` 关于位置参数 `gamma` 的离散梯度 | 尊重第二篇 MDM 原文记号；必须说明不是 `gamma` 自身的梯度，不另改名为 `g(gamma)` |
| Default（`delta = 0.1`） | Ch3 正式定义 | Default 专指原文经验设置，不泛指任意基线 |
| L1-L6 信息层级 | Ch3 正式定义 | L1/L2 为可部署层级；L3-L5 为 oracle 参照；L6 为 sample-level hindsight benchmark |
| oracle 参照 | 首次出现说明依赖真参数 | 不写成可直接部署策略或理论上界 |
| hindsight benchmark | 首次出现说明是扫描网格内逐样本事后参照 | 不写成理论上限或实际部署目标 |
| 神经网络（NN） | Ch1 结尾首次点明，Ch6 定义具体结构 | NN 是样本自适应 offset 选择的主要实现方法，不是论文目的 |
| Vector-MLP | Ch6 定义 | 仅在指 E3b 的具体 vector-output MLP 模型时使用，不与 NN 泛称混用 |
| 现有正式离散参数网格（existing-grid） | Ch6 首次界定证据边界 | 不简写成连续空间或无条件泛化 |

---

## 【作者备注】引用标注规则

- `(182-XXX)` 为文献库一手引用。
- `(182-XXX[N])` 为从 `182-XXX` 转引的第 N 号文献。

---

## 【作者备注】Ch1-Ch2 引用对照表

| 编号 | 文献库编号 | 文献全名 | 用在何处 |
|------|-----------|---------|---------|
| 122-007 | 122-007 | 轩福贞等. 结构疲劳百年研究的回顾与展望. 机械工程学报, 2021 | Ch1：疲劳研究 160 年历史 |
| 122-010 | 122-010 | Freudenthal, Gumbel. On the statistical interpretation of fatigue tests. Proc. R. Soc. A, 1953 | Ch1：Weibull 分布在疲劳中的极值统计基础 |
| 123-001 | 123-001 | 赵丙峰等. 机械结构概率疲劳寿命预测研究进展. 机械工程学报, 2021 | Ch1：50%~90% 失效由疲劳引起 |
| 182-057 | 182-057 | 宋欣等. Weibull 分布参数估计值对细节疲劳额定强度的影响. 航空学报, 2021 | Ch1：航空结构三参数 Weibull 应用 |
| 182-060 | 182-060 | 胡述伟等. 基于三参数威布尔分布的锆合金疲劳寿命高准确度预测模型构建方法. 重庆大学学报, 2024 | Ch1：核材料三参数 Weibull 应用；PWM 法 |
| 182-075 | 182-075 | Zhang 等. 超高性能混凝土的弯曲疲劳行为：两参数与三参数威布尔模型对比. CBM, 2025 | Ch1：三参数 Weibull 在 UHPC 疲劳中的应用 |
| 182-051 | 182-051 | Shimizu 等. Probabilistic Stress-Life Study on Bearing Steel. Tribology, 2009 | Ch1：轴承钢三参数 Weibull P-S-N |
| 182-022 | 182-022 | Ross. Bias and Standard Deviation due to Weibull Parameter Estimation for Small Data Sets. IEEE TDEI, 1996 | Ch1：小样本 MLE 偏差；偏差修正线索 |
| 182-099 | 182-099 | 李进等. 威布尔分布的极大似然估计的精度分析. 北航学报, 2006 | Ch1：小样本 MLE 精度问题 |
| 182-090 | 182-090 | Smith. Maximum likelihood estimation in a class of nonregular cases. Biometrika, 1985 | Ch1：三参数 Weibull 不满足正则条件（β<2 发散，β≤1 不存在） |
| 182-091 | 182-091 | Cohen, Whitten. Modified MLE and MME for 3-P Weibull. Comm. Stat., 1982 | Ch1：β>2.2 才建议用 MLE；MMLE 方法 |
| 182-025 | 182-025 | 杨小玉等. 三参数威布尔形状参数估计方法的比较与推荐取值. 机械工程学报, 2024 | Ch1：β≤2 MLE 不适用；MDM 与 CCM/LSE 比较结果 |
| 182-039 | 182-039 | Comparison of Methods for Estimating Weibull Parameters with Small Sample Data, 2024 | Ch1：小样本 MLE 不稳定 |
| 182-096 | 182-096 | Akram, Hayat. Comparison of Estimators of the Weibull Distribution. Comm. Stat. Sim. Comp., 2013 | Ch1：7 种方法系统比较；转引 Smith & Naylor 贝叶斯[3]、Cheng & Amin MPS[5]、L-moment[6] |
| 182-046[7] | 182-046 转 | Teimouri 等. 12 种方法比较（转引自 182-046） | Ch1：12 种方法结果差异悬殊 |
| 182-088 | 182-088 | Cousineau. Nearly unbiased estimators for 3-P Weibull. 2009 | Ch1：加权 MLE (WMLE)；偏差修正脉络 |
| 182-029 | 182-029 | Man Chen 等. On the Bias of MLE of Weibull Distribution. MCA, 2017 | Ch1：Cox-Snell 解析偏差修正 |
| 182-024 | 182-024 | 杨小玉等. Weibull 形状参数加权极大似然估计的偏差修正. 吉林大学学报, 2024 | Ch1：WMLE 偏差修正（东北大学团队） |
| 182-084 | 182-084 | 夏新涛等. 用自助加权范数法评估三参数威布尔分布可靠性最优置信区间. 航空动力学报, 2013 | Ch1：自助加权范数法 |
| 182-003 | 182-003 | Safari 等. Robust estimation of 3-P Weibull for outliers. Sci. Rep., 2025 | Ch1：异常值稳健估计 |
| 182-023 | 182-023 | Gupta, Singh. Classical and Bayesian estimation of Weibull with outliers. Cogent Math., 2017 | Ch1：异常值稳健估计 |
| 182-030 | 182-030 | Xie, Wu, Yang. A Minimum Discrepancy Method for Weibull Parameter Estimation. IJSSD, 2022 | Ch1：MDM 原始论文；Ch2§1 |
| 182-046 | 182-046 | 谢里阳等. 基于统计最小差异原理的 Weibull 分布参数估计方法. 东北大学学报, 2025 | Ch1：MDM + δ=0.1；Ch2§1-§3 |

---

## 【作者备注】Ch3 方法与实验协议溯源

- MDM 推导基于 `python/methods/mdm.py`（method git_commit: `e4ef9e9`）和原文 `(182-030; 182-046)`。
- 参数网格、δ grid、R、seed 均由 `code/config.py` 和各实验 manifest 追溯。

> 注：Ch3 §1 MDM 推导已前移至 Ch2 §1；本备注中的 mdm.py 溯源同时覆盖 Ch2 §1-§2 和 Ch3 §3 实验协议。

---

## 【作者备注】Ch4 E1 数据溯源

- δ-risk 曲线数据：`../artifacts/formal/E1_baseline/delta_risk_curve.csv`
- Default vs L1 分组合：`../artifacts/formal/E1_baseline/table_default_vs_L1.csv`
- L2 按 n：`../artifacts/formal/E1_baseline/table_L2_by_n.csv`
- 汇总：`../artifacts/formal/E1_baseline/summary.json`
- manifest：`../artifacts/formal/E1_baseline/manifest.json`（run_id: `E1_baseline_v1`, git_commit: `3a35abc`, mdm git_commit: `e4ef9e9`）
- Figure 2 绘图脚本：`code/plot_fig2.py`
- Figure 2 图片：`../artifacts/formal/figures/fig2_delta_risk_curve.{svg,pdf,png}`

> 注：上述脚本/图片命名沿用旧版 Figure 编号；正文 Figure 编号以各章初稿为准。

---

## 【作者备注】Ch5 E2 数据溯源

- 阶梯表：`../artifacts/formal/E2_oracle_layers/ladder_L1_L6.csv`
- L3 按 β：`../artifacts/formal/E2_oracle_layers/L3_by_beta.csv`
- L4 按 (β,n)：`../artifacts/formal/E2_oracle_layers/L4_by_beta_n.csv`
- L5 按 (β,γ/η,n)：`../artifacts/formal/E2_oracle_layers/L5_by_beta_goe_n.csv`
- L6 逐样本：`../artifacts/formal/E2_oracle_layers/L6_per_sample_delta.csv`
- MLE 锚点：`../artifacts/formal/shared_data/mle_anchor.csv`
- Figure 3 脚本：`code/plot_fig3_fig4.py`
- Figure 4 脚本：`code/plot_fig3_fig4.py`

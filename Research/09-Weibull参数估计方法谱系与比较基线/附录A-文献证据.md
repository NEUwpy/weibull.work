# 附录A：文献证据

> 更新：2026-09-27。保存文献事实、适用条件、指标定义和疑点；综合判断及对照推荐以[研究报告](研究报告.md)为准。

首轮从14篇来源提取相关章节，不是全库系统审读：2篇综述、11篇方法或比较研究、1篇WMLE构造来源。原文报告的优势不等于本项目独立验证。A1支撑主报告的方法分类和候选选择，A2支撑评价口径，A3限定证据可用范围，A4登记已取得但待进一步核查的材料。

## A1. 已提取的文献事实

以下统一称形状为β、尺度为η、位置为γ；原论文符号各异。链接均指已有本地正文，PDF入口可在[完整盘点](资料/文献索引.md)按编号查找。

### A1.1 综述

| 来源 | 本轮核查内容 | 能支持的结果与边界 |
|---|---|---|
| [181-004，Yang等，2023](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/181_综述文献/181-004-pdf原文.md) | 方法分类、比较章节、参考文献 | 可用于追溯方法家族；不能把综述的优劣描述直接变成跨场景排名，分类本身需重新编码 |
| [181-008，Bulut与Bingöl，2024](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/181_综述文献/181-008-pdf原文.md) | 2014—2023年风能应用的检索选择、96篇研究的统计及评价指标 | 提供有明确范围的二参数风速应用统计；不代表三参数疲劳小样本领域 |

181-008报告：96篇中MLE出现82次、EMJ 67次、MOM 62次、EPF 61次、M-MLE 55次；RMSE使用率86%、R²为72%、χ²为32%。这些是**该综述作者对其纳入集合的统计，本轮核对了原文，尚未逐篇独立重算**。各方法可在同一论文出现，频数不能相加当论文总数。

该综述还报告MLE在24篇中表现最好。这只能作为该应用集合中的作者报告次数，不能解释成MLE获得了统一协议下的24次胜利。不同论文的样本、拟合对象和损失不同；风速频率/PDF拟合RMSE尤其不能等同于参数估计RMSE。综述列出75个方法标签，也不意味着存在75个互不重叠的统计原理。

### A1.2 方法与比较研究

| 来源与角色 | 已核对的实验范围、对手 | 指标与可用结论 | 必须保留的边界 |
|---|---|---|---|
| [182-101，Cousineau，2009：比较研究](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-101-pdf原文.md) | 三参数；n=8、16、32、64；β=0.5、1、1.5、2、2.5；MLE、MPS、w-MLE、矩及混合估计 | 形状Bias、SD、RMSE；另比较三参数联合误差。WMLE形状估计表现强；联合比较中作者按β范围推荐MPS或混合估计 | §3明确剔除形状估计>5的结果，约占2%；不能把该排名直接当作未截断总体风险。联合指标采用未标准化参数距离 |
| [182-096，Akram与Hayat，2014：独立比较](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-096-pdf原文.md) | 三参数；n=10、20、50、100；β覆盖0.5—9；每设置5000组；比较MLE、LM、MPS及多个修正矩/似然版本 | Bias与RMSE；低形状区MPS有竞争力，高形状小样本中LM值得重视，不同条件的优胜者改变 | §4.1只保留ML收敛且样本L-skewness≥−0.1699的样本；β<1部分不列MLE。适用性筛选会改变比较总体 |
| [182-025，杨小玉等，2024：形状比较](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-025-pdf原文.md) | β=2、3，η=γ=1000；n=15、30、50、100、200；每条件1000组；CCM、LS、MDM | 主要比较形状Bias与RMSE，支持CCM作为形状估计对照 | 不能由形状优势推出三参数联合优势；与MDM/BPNN部分作者重合 |
| [182-030，Xie、Wu、Yang：MDM，2022在线/2023卷期](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-030-pdf原文.md) | 通过各样本与CDF构造伪尺度，以差异建立估计准则；小样本案例比较ML和Weibull概率图LS | 参数相对误差、样本间偏差及案例结果；为MDM改进研究提供母方法 | 案例数量与比较协议有限，不能当作覆盖广泛参数域的大规模重复试验；须核对偏移构造和实现版本 |
| [185-005，Guo等，2023：SAM逐次逼近](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/185_小样本问题方法/185-005-pdf原文.md) | 三参数；n=5、10、15、20；β=1.5、2、2.5，γ=1，η取0.2—4的8个值；每条件10000次；MLE、CCWP、PWM | 三参数MAD均值、SD均值；还评估MTTF及99%可靠度寿命。是现有库中与极小样本直接相关的近期传统构造候选 | 文中MSD指mean standard deviation；把干净样本中的低SD称为robustness，不等同于污染稳健性。调节因子0.99需复现 |
| [182-003，Safari等，2025：PITE](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-003-pdf原文.md) | 三参数；n=50、100、500；β=2、4、6，η=3，γ=1；污染2%、4%、6%、8%，污染分布尺度为原尺度5倍；每条件5000次；MLE、WMLE、MPSE、MOM | 逐参数RMSE及Def；ρ=0.68、1的PITE形状估计表现强，尺度比较中部分条件MPSE更好 | 证据针对特定污染模型；不直接证明干净n=5—20优势。Def是三个原始RMSE的算术平均 |
| [184-009，Yang等，2025：BPNN](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/184_深度学习参数估计/184-009-pdf原文.md) | 三参数；训练β∈[1,4]，η、γ∈[0,10]，n=5—20；对比n=5、10、15、20，β=2、3，η=5，γ=4、5、6，每条件1000组；对手CCM、MDM | 三参数及99%可靠度寿命的SD、RMSE；作者报告在所列条件下优于两种对手；直接覆盖当前极小样本任务 | 未与WMLE、MPS、LM比较；未验证β<1或训练域外优势。输入表述及选模型使用“test MSE”的措辞需在复现时澄清 |
| [182-050，Tsukada、Sugiyama、Ogura，2025：位置更新与回归组合](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-050-pdf原文.md) | 三参数；MVLUE位置更新与平移后二参数greg2/rank估计组合；n=10、20、30，β=0.2、0.5、0.8、1、2、3，η=1，γ=3；100000次；对手标为w-MLE、BL、LSPF-MLE | 逐参数Bias、RMSE及Joint；作者报告低形状条件下的优势，也报告β=4、5时w-MLE较好（这部分表格未展示） | PDF第11页的方差/RMSE定义存在数学不一致；w-MLE及LSPF对手描述也需追溯原始来源。本轮仅推荐为需先审计的近期候选 |
| [182-103，Liu等，2026：ICP-CDF-LS](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-103-pdf原文.md) | 随机右删失三参数；n=10、20、30；β=0.5、1.5、3、5，η=γ=1000；删失率0.2、0.4、0.6；500次；MLE、常规LS | 参数均值、Bias、RMSE；更新失效概率后迭代概率图LS，位置估计相对MLE的表现随β改变 | 属于删失分支；所展示代表样本的收敛过程不能当作一般收敛证明 |
| [187-001，Wang等，2026：ADGBO](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/187_智能优化算法/187-001-pdf原文.md) | 三参数MLE求解；利用Bootstrap/相关系数初始区间、Halton初始化和梯度搜索；比较Newton、PSO、CCLSE；n=10、20、50、100 | 参数偏差、似然、迭代/计算表现等；证明近期有以数值求解为核心的研究路线 | 估计目标仍是MLE。不能把优化器名称直接当作新的统计准则，也不能把更高似然等同于更低参数风险 |
| [183-012，Ali等：AICQME，2025在线/2026卷期](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/183_机器学习参数估计/183-012-pdf原文.md) | 二参数风速；分位数匹配初始化后神经网络校正；韩国3个海上站点2017—2023年，共21个站点年度数据集 | 风速分布拟合RMSE、MAE、R²、K-S距离；支持“统计估计后学习校正”的近期方向 | 两参数、实际风速拟合；没有可观察的真实参数供现场数据参数RMSE比较。网络输入前后表述不同，复现需核对 |

另核查[182-088：Cousineau WMLE构造原文](D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-088-pdf原文.md)的摘要与权重含义：其权重用于修正MLE方程中的偏差，J₁、J₂权重依赖样本量，J₃还依赖形状；本项目采用相应统计量中位数的权重构造。**不能把任意逐观测加权对数似然都称为该WMLE。** 182-088是构造来源，182-101是比较来源，二者不算独立研究团队的重复验证。

## A2. 文献中的指标定义与筛样口径

| 文献 | 已提取的定义或处理 | 使用该证据时的限制 |
|---|---|---|
| Cousineau比较研究，182-101 | 形状Bias、SD、RMSE及原始三参数空间联合距离；印刷页284剔除形状估计>5的结果 | 联合误差受参数尺度影响；截断结果不能代表未经筛选的总体风险 |
| Akram与Hayat，182-096 | Bias、RMSE；印刷页248按ML收敛及L-skewness阈值筛样 | 排名针对筛选后的样本集合 |
| PITE，182-003 | Def为三个原始参数RMSE的算术平均 | 各参数量纲和尺度不同；污染机制须同步报告 |
| SAM，185-005 | MAD为三个参数平均绝对误差的平均，MSD指mean standard deviation；另评MTTF及可靠度寿命 | MSD不能当作均方差；低抽样波动不等于污染稳健 |
| BPNN，184-009 | 三参数与99%可靠度寿命的SD、RMSE | 参数精度与寿命目标应分别解释；训练域限制见A1 |
| Tsukada，182-050 | Joint bias为三个绝对偏差之和，Joint RMSE为MSE矩阵迹平方根 | PDF第11页方差与RMSE定义存在不一致，不能推断其代码也必然算错 |
| AICQME，183-012 | 风速分布拟合RMSE、MAE、R²及K-S距离 | 现场真参数未知，拟合误差不等于参数估计误差 |

本研究统一评价规则及公式见[主报告第三章](研究报告.md#第三章-研究内容与结果)，这里仅保存原文定义与证据边界。

## A3. 来源身份与内容疑点

| 问题 | 已有核查 | 本轮处理 |
|---|---|---|
| 182-096笔记作者/题名错配 | 实际PDF与正文为Akram与Hayat的2014年论文，非笔记所称Teimouri 2013 | 本文按PDF身份引用，不能把两个身份重复统计；未改动外部文献库 |
| 182-050的RMSE定义 | 已查看PDF第11页（印刷页4048）：把围绕真值的均方差写作variance，又给出sqrt(variance+bias²) | 确认是原文表述问题；无法据此判定作者代码是否也这样计算，故不照搬数值排名 |
| 182-050对手身份 | w-MLE写成逐观测加权似然，与182-088的方程修正构造不等价；其LSPF描述还需对原始方法核验 | 降低该文性能比较的直接采信程度；保留新方法原理与复现价值 |
| 184-009与183-012的学习构造表述 | 正文不同段落的输入描述不完全一致 | 标记为复现问题，不擅自指定一个版本后称作原文复现 |
| DOI与年份登记 | 181-008、182-003笔记DOI有误；184-009实际2025；183-012在线2025、卷期2026 | 按PDF/出版来源在本Research更正，详见补下载清单 |
| 同文多编号/相关稿件 | 184-009有历史重复条目；182-054为相关未核实正式出版的稿件 | 不把编号数当独立论文数，不把相关稿件当独立外部验证 |

上述问题不会使全部文献失去价值。它们决定的是证据用途：可以用来识别构造、选择候选或设定验证问题；当性能定义或对手实现不清楚时，不能直接引用“优于所有方法”的结论。

## A4. 新入库材料与审读状态

2026-09-27核对入库记录与文件：原首批5篇已全部补齐，另新增4篇相邻方向论文，9篇均有PDF、OCR正文及笔记。下列材料完成入库核验；5篇原缺文已初读正文开头，完整算法提取与独立复现尚未完成，不计入首轮14篇已提取证据。

| 编号 | 作者年份、题名及正文 | 后续证据用途 |
|---|---|---|
| 182-108 | [Warwick & Jones 2005：Choosing a robustness tuning parameter](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-108-pdf原文.md>) | 稳健性调优参数背景 |
| 182-109 | [Warwick 2005：A data-based method for selecting tuning parameters in minimum distance estimators](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-109-pdf原文.md>) | 最小距离估计的调参背景 |
| 182-110 | [Kelly 1996：Adaptive Choice of Tuning Constant for Robust Regression Estimators](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-110-pdf原文.md>) | 稳健回归调参背景 |
| 182-111 | [da Silva 2025：Bias Reduction of Modified Maximum Likelihood Estimates for a Three-Parameter Weibull Distribution](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-111-pdf原文.md>) | DMMLE：近期三参数偏差修正候选 |
| 182-112 | [Zhang 2023：Data-adaptive M-estimators for robust regression via bi-level optimization](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-112-pdf原文.md>) | 双层优化与数据自适应M估计背景 |
| 182-113 | [Nagatsuka 2013：A consistent method of estimation for the three-parameter Weibull distribution](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-113-pdf原文.md>) | 数据变换、存在性与一致性来源 |
| 182-114 | [Nassar & Elshahhat 2024：Estimation procedures and optimal censoring schemes for an improved adaptive progressively type-II censored Weibull distribution](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-114-pdf原文.md>) | 删失场景的模型及指标核查 |
| 182-115 | [Park 2017：Weibullness Test and Parameter Estimation of the Three-Parameter Weibull Model Using the Sample Correlation Coefficient](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-115-pdf原文.md>) | 相关系数法原始来源；对照当前LRE |
| 182-116 | [Cheng & Amin 1983：Estimating Parameters in Continuous Univariate Distributions with a Shifted Origin](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-116-pdf原文.md>) | MPS目标、端点与适用条件来源 |

原首批5篇对应182-111、113—116，不再需要重复下载。9条种子均有本地正文；187-001原版PDF仍可选补充，已有正文可继续研究。全部文件入口见[文献索引](资料/文献索引.md)，文件哈希见[入库证据](evidence/literature_accession_20260927.json)。

## A5. 首轮来源的出版标识

以下DOI用于定位原始论文；研究结论主要依据本地已有正文。14条DOI均已通过出版元数据解析核验，16个本地链接检查通过；核验记录见[引用报告](历史/2026-09-27重构前/05-已有文献阶段性研究结果_citation_report.json)。DOI可解析不等于已核验每个公式或性能结论。

| 编号 | 题名/身份 | DOI |
|---|---|---|
| 181-004 | A Review of Parameter Estimation Methods of the Three-Parameter Weibull Distribution，2023 | [出版入口](https://doi.org/10.1109/ISSSR58837.2023.00013) |
| 181-008 | Weibull parameter estimation methods on wind energy applications – a review of recent developments，2024 | [出版入口](https://doi.org/10.1007/s00704-024-05184-2) |
| 182-101 | Fitting the Three-Parameter Weibull Distribution: Review and Evaluation of Existing and New Methods，2009，16(1):281–288 | [出版入口](https://doi.org/10.1109/TDEI.2009.4784578) |
| 182-096 | Comparison of Estimators of the Weibull Distribution，Akram与Hayat，2014，8(2):238–259 | [出版入口](https://doi.org/10.1080/15598608.2014.847771) |
| 182-088 | Nearly unbiased estimators for the three-parameter Weibull distribution with greater efficiency than the iterative likelihood method，2009 | [出版入口](https://doi.org/10.1348/000711007X270843) |
| 182-025 | 三参数威布尔形状参数估计方法的比较与推荐取值，2024 | [出版入口](https://doi.org/10.3901/JME.2024.16.367) |
| 182-030 | A Minimum Discrepancy Method for Weibull Distribution Parameter Estimation，2022在线/2023卷期 | [出版入口](https://doi.org/10.1142/S0219455423500852) |
| 185-005 | Weibull parameter estimation and reliability analysis with small samples based on successive approximation method，2023 | [出版入口](https://doi.org/10.1007/s12206-023-1019-z) |
| 182-003 | Robust estimation of the three parameter Weibull distribution for addressing outliers in reliability analysis，2025 | [出版入口](https://doi.org/10.1038/s41598-025-96043-1) |
| 184-009 | Estimation of Weibull distribution using the back-propagation neural network for fatigue failure data，2025 | [出版入口](https://doi.org/10.1016/j.probengmech.2025.103828) |
| 182-050 | Parameter estimation of the initial failure period for a three-parameter Weibull distribution in a small sample，2025 | [出版入口](https://doi.org/10.1080/00949655.2025.2552417) |
| 182-103 | Parameter Estimation of the Three-Parameter Weibull Distribution Based on an Iterative CDF Method，2026 | [出版入口](https://doi.org/10.3390/math14040649) |
| 187-001 | An improved adaptive gradient-based optimization algorithm for estimating the parameters of three-parameter Weibull distribution: an application of aero-engine reliability assessment，2026卷期 | [出版入口](https://doi.org/10.1016/j.ress.2025.111610) |
| 183-012 | AI-calibrated quantile matching estimation: A new method for accurate Weibull parameter prediction under irregular wind distributions，2025在线/2026卷期 | [出版入口](https://doi.org/10.1016/j.enconman.2025.120673) |

# Study 01: MDM 最小偏移量优化研究

> 本目录是面向发表论文的整理工作区。它不是 `docs/research/01`、`02`、`03`、`04` 的简单复制，也不是汇报 PPT 材料的存放处。

## 这个目录要解决什么

当前目标是在已有小研究的基础上，整理出一篇可发表的小论文。论文主题围绕三参数 Weibull 分布 MDM 方法中的偏移量问题：

- MDM 为什么需要偏移量 `delta`？
- 原始经验值 `delta = 0.1` 的作用机理是什么？
- 最优偏移量受哪些因素影响？
- 在部署时无法知道真参数的条件下，是否能比固定 `delta = 0.1` 做得更好？
- 如果需要进入更细的信息层级，能否仅凭样本值和样本量 `n` 近似选择更合适的偏移量？

本目录后续应承载论文级材料：研究问题、证据索引、正式实验协议、正式代码、可复现实验产物、论文骨架、结果表述和投稿版本草稿。

## 与 `docs/research` 的关系

`docs/research` 下的 `01`、`02`、`03`、`04` 是围绕更小问题逐步展开的小研究：

| 目录 | 作用 |
|------|------|
| `docs/research/01对如何评判参数估计准确性的研究` | 建立参数估计准确性评价口径 |
| `docs/research/02对MDM方法有解性的证明` | 解释 MDM offset-root 的有解性、无解成因和工程处理 |
| `docs/research/03对MDM方法最佳偏移量的研究` | 研究最优偏移量的影响因素、标度、部署策略 |
| `docs/research/04基于神经网络的MDM偏移量自适应选取` | 在 01-03 基础上整理统一口径，并继续研究神经网络自适应选取 |

其中，`docs/research/04...` 里的 `01-04研究骨架.md`、`01-04研究内容.md`、讲稿等，是为了汇报而统一整理 `01` 到 `04` 的口径。它们很有价值，但不是最终论文结构本身，也不是投稿论文的正式实验证据。

换句话说：

```text
docs/research/01-04 = 分问题研究、阶段汇报与 pilot evidence
Study/01           = 面向发表的小论文工作区，承载正式实验和论文稿
```

## 核心原文

MDM 方法相关原文在本地文献库中已有 Markdown 正文、图片和 PDF/OCR 版本。后续写论文时应优先核对 Markdown 正文，再在需要时回到 PDF/图片确认版面和公式：

| 编号 | 文献 | 本研究中的作用 |
|------|------|----------------|
| `182-030` | *A Minimum Discrepancy Method for Weibull Distribution Parameter Estimation*，Liyang Xie, Ningxiang Wu, Xiaoyu Yang，International Journal of Structural Stability and Dynamics, Vol. 23, No. 8, 2023, DOI: `10.1142/S0219455423500852` | MDM 第一篇原文，提出 minimum discrepancy method / MDE，用尺度伪估计量差异最小来估计 Weibull 参数 |
| `182-046` | 《基于统计最小差异原理的Weibull分布参数估计方法》，谢里阳、朱文慧、吴宁祥、杨小玉，《东北大学学报（自然科学版）》2025 | MDM 第二篇，进一步表述为“统计最小差异原理”，并引入/论证 `delta = 0.1` 的偏移判据 |

本地材料位置：

| 编号 | 优先核对材料 | 备查材料 |
|------|--------------|----------|
| `182-030` | `src/content/182-030-pdf原文.md`；`src/content/182-030-pdf翻译.md` | `public/182-030-图片/6a98513f-9bde-456f-91c2-b6593e706f7e_origin.pdf`；`public/182-030-图片/6a98513f-9bde-456f-91c2-b6593e706f7e_content_list.json` |
| `182-046` | `src/content/182-046-pdf原文.md` | `public/182-046-图片/012c91a7-edf6-4ddb-942c-5a8add25e875_origin.pdf`；`public/182-046-图片/012c91a7-edf6-4ddb-942c-5a8add25e875_content_list.json` |

## 推荐阅读顺序

新窗口或新 agent 接手时，建议按下面顺序阅读：

1. 项目入口：`README.md`
2. 本文件：`Study/01-study-MDM最小偏移量优化研究/README.md`
3. 总体想法：`Study/研究规划备忘录.md`
4. 汇报整合材料：
   - `docs/research/04基于神经网络的MDM偏移量自适应选取/进度控制.md`
   - `docs/research/04基于神经网络的MDM偏移量自适应选取/01-04研究骨架.md`
   - `docs/research/04基于神经网络的MDM偏移量自适应选取/01-04研究内容.md`
5. 偏移量专题材料：
   - `docs/research/03对MDM方法最佳偏移量的研究/背景.md`
   - `docs/research/03对MDM方法最佳偏移量的研究/第十一轮结果.md`
6. MDM 原文：
   - `src/content/182-030-pdf原文.md`
   - `src/content/182-030-pdf翻译.md`
   - `src/content/182-046-pdf原文.md`
   - 如需核对版面、图片或 OCR 片段，再回到 `public/182-030-图片/`、`public/182-046-图片/`
7. 如需核对实现或重跑实验，再读：
   - `python/methods/mdm.py`
   - `python/studies/common/README.md`
   - `python/studies/mdm/README.md`

## 当前理解

可以先把已有研究理解为一条“前置探索链”。这条链用于提出假设和设计正式实验，不能直接等同于投稿证据：

```text
01 评价口径
  -> 参数视角 J_param、Bias/SD/RMSE
  -> 工程视角 RMSE_xR

02 MDM 有解性
  -> offset-root 机理
  -> gamma >= 0 约束下的负根截断
  -> 工程求解器始终返回候选估计

03 最优偏移量
  -> 研究 delta 的影响因素
  -> 区分 L0-L5 信息层级
  -> 证明固定 delta=0.1 是强 baseline
  -> 显式 beta 预估、自迭代等部署方案并不稳定

04 自适应选取
  -> 尝试用样本可观测特征学习 delta
  -> 风险曲线标签优于硬标签
  -> 可作为正式实验的候选路线
```

投稿论文应重新组织为一条"正式证据链"：

```text
Formal E1 δ 扫描与 L1-L2 层级
  -> Default / L1 / L2 的正式阶梯，回答"δ=0.1 是否最优全局常数，以及按 n 查表能改善多少"

Formal E2 L3-L6 Oracle 层级
  -> 按 β / β+n / β+γ/η+n / 逐样本 hindsight 的参照精度，识别边际递减点

Formal E3 样本自适应 δ 选择
  -> 在真参数不可见时，用样本可观测特征和 n 学习 δ 选择规则；NN 是候选实现，不是论文目的本身

Formal E4 边界与稳健性
  -> 跨 β/n/gamma_eta、极小样本、失败处理、计算成本
```

## 工作边界

- 不要把 `docs/research/04...` 的汇报页码直接当作论文目录。
- 不要直接引用早期轮次数字；旧 `docs/research` 结果只能作为 pilot evidence，正式正文数字必须来自本目录下重新设计、重新实现、重新验证的实验产物。
- MDM 当前默认语义以 `python/methods/mdm.py` 为准：`gamma >= 0`，负 offset-root 截断到 `gamma = 0`，默认偏移量 `delta = 0.1`。
- 正式实验应优先调用 `python/studies/common` 与 `python/methods/mdm.py`，但正式代码、配置、manifest 和输出应组织在本目录下。
- 正式实验必须保留 `results.csv`、`summary.json`、`manifest.json` 等可复现实验产物。
- 本目录应保存论文级整理材料；大规模原始输出不要直接堆进来，除非先说明用途和来源。
- `artifacts/formal/shared_data/mc_scan_raw.csv` 被 `.gitignore` 排除（体积过大）。干净 clone 后需先运行 `python code/generate_mc_data.py --merge-only` 从 tracked chunks 合并出分析输入。tracked chunks 是正式数据源，`mc_scan_raw.csv` 是分析脚本的直接读取对象。
- 不要把本文写成“用神经网络优化 MDM”的单一 ML 论文；本文主线是偏移量 `delta` 的层级最优性、改善幅度和部署可达性。神经网络只是在真参数不可见时逼近下游层级的一种候选工具。

## 投稿准备文件

本目录当前用下列文件承接投稿级准备工作：

| 文件 | 作用 |
|------|------|
| `00-研究问题与边界.md` | 明确本文作为 MDM 第三篇推进工作的研究定位、主问题、贡献、禁区，以及旧材料的 pilot 地位 |
| `01-证据索引.md` | 区分文献证据、pilot 证据和正式证据；正式证据待由 Formal E1-E4 生成 |
| `02-实验协议.md` | 规划正式投稿实验 E1-E4、参数网格、指标、baseline、数据切分、输出结构和停止条件 |
| `03-论文骨架.md` | 按 Formal E1-E4 的正式证据链组织论文，而不是按汇报页码重组 |
| `04-待复核清单.md` | 检查正式代码、正式实验产物、指标、统计、图表和正文主张 |
| `05-投稿进度控制.md` | 以投稿闸门管理从正式实验设计到投稿包的进度 |
| `progress-offset-hierarchy-realignment.md` | 记录 2026-07-06 对“偏移量层级主线 / NN 工具角色 / n 分层视角”的重校准，防止续接时回到旧口径 |

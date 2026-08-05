# Study 01: MDM 最小偏移量优化研究

> 本目录是面向发表论文的整理工作区。它不是 `docs/research/01`、`02`、`03`、`04` 的简单复制，也不是汇报 PPT 材料的存放处。
>
> **当前状态（2026-08-04）**：既有正式实验与技术证据包保持封存，不删除、不重跑、不重封存。P4 正式六方法比较（MDM-Default / MDM-Vector-MLP / Direct-MLP / MLE / LSE / WMLE）已在授权 tip `cfb0c6ed` 上完成四轨道正式运行并通过 SHA256SUMS 17/17 封存校验（seal `f00b561d`，产物 `artifacts/formal/p4_formal_compare/`）。论文主线已收敛为 E1/E2/E3b 三类核心结果；支撑验证、独立 Research 与待移出材料已分层归档。外部中文学术源稿 v0.3 为唯一活动论文稿。

## 这个目录要解决什么

当前目标是在已有小研究的基础上，整理出一篇可发表的小论文。论文主题围绕三参数 Weibull 分布 MDM 方法中的偏移量问题：

- MDM 为什么需要偏移量 `delta`？
- 原始经验值 `delta = 0.1` 的作用机理是什么？
- 最优偏移量受哪些因素影响？
- 在部署时无法知道真参数的条件下，是否能比固定 `delta = 0.1` 做得更好？
- 如果需要进入更细的信息层级，能否仅凭样本值和样本量 `n` 近似选择更合适的偏移量？

本目录承载论文级材料：研究问题、证据索引、正式实验协议、正式代码、可复现实验产物、论文骨架和结果表述。

## 论文研究什么（一句话）

在三参数 Weibull MDM 框架内，本文研究**如何把经验固定偏移量 `delta` 推进为具有明确最优性定义、信息层级和样本自适应选择方法的量**。本文不宣称优于所有参数估计方法，也不把神经网络直接参数估计作为主线；J1 只是统一评价准则，不是方法创新。

## 核心实验（只有这三类属于论文核心结果）

| 编号 | 实验 | 要回答的问题 | 正式数据位置 | 状态 |
|------|------|--------------|--------------|------|
| **E1** | 固定全局偏移量及经验值 `delta=0.1` 的位置 | 经验值 `delta=0.1` 是否已接近当前设计测度下的最佳统一常数？L1/L2 固定规则能否带来收益？ | `artifacts/formal/E1_baseline/`、`artifacts/formal/E1_E2_crossfit/` | 正式证据可用（已封存） |
| **E2** | 不同信息层级下的潜在收益 | 从 L3 到 L6，增加真参数信息能带来多少精度收益？边际递减点在哪里？ | `artifacts/formal/E2_oracle_layers/`、`artifacts/formal/E2_beta_profile_audit/` | 正式证据可用（已封存） |
| **Dimensional-RAW-MLP（样本自适应，最终方法）** | 真参数未知时，按样本量分别训练的 MLP 以排序的原始样本 $X_n=\operatorname{sort}(x)$ 预测 26 点损失曲线并选择偏移量 | 仅凭样本可观测信息能否逼近 oracle 层级的参照精度？ | `artifacts/formal/E6_dimensional_raw/specialist/`（数据复用 `E5_normalized_raw/shared_data/`） | 正式证据可用（本迁移交付） |
| ~~E3b~~（历史） | 旧特征路线：13 统计量、跨 n 联合 Vector-MLP | 历史/Research 证据，不再作为正式输入 | `artifacts/formal/E3b_vector_mlp/`、`artifacts/formal/E3_sample_adaptive/` | 已封存，保留为历史证据 |

三项核心结果的关键数值（以封存口径为准）：

- E1：`delta=0.1` 已接近全局最优统一常数，L1 相对 Default 的 pooled J1 降幅约 `0.8%`（新设计域 cross-fit），全局固定规则收益有限。
- E2：新 160 组合设计统一 cross-fit：Default 0.6304 / L1 0.6252 / L2 0.6230 / L3 0.5905 / L4 0.5885 / L5 0.5813 / L6 0.4923；L2→L3 为最大单步信息增益（5.2%），逐样本事后选择潜在降幅约 21.9%。
- 样本自适应（Dimensional-RAW，新设计域：`eta=1000`、`n∈{7,10,15,20}`、160 组合）：以排序原始样本为输入、按样本量分 n 训练；正式结果（同测试样本比较）：pooled J1 = 0.554（三 seed 0.5545/0.5523/0.5560，std 0.0015），Default = 0.630、L6 hindsight = 0.492、归一化候选对照 = 0.585；相对 Default 改善约 12.1%；分 n J1 = 0.690/0.576/0.485/0.430（n=7/10/15/20），失败率 0%；有量纲输入不具备单位不变性，结论限于训练单位与尺度范围。产物 `artifacts/formal/E6_dimensional_raw/specialist/`。

## 支撑验证（正文简要报告结论，详细结果进入补充材料）

| 验证 | 内容 | 正式数据位置 | 状态 |
|------|------|--------------|------|
| 泛化验证 | 参数插值（P2-PI）、样本量插值（P2-NI，n=15）及边界外推轨道上相对固定规则是否保留收益 | `artifacts/formal/extended_validation/p2_generalization_v2/`、`artifacts/formal/E4_robustness/`（E4d） | 正式证据可用（P2 v2 已获 Codex APPROVE `53932687`） |
| seed 稳定性与输入表示尺度性质 | 60 个 fold×seed 模型级分布（4n×5fold×3seed）；输入表示检查（排序原始样本、逐位置标准化仅训练折拟合、有量纲输入不具备单位不变性） | `artifacts/formal/E6_dimensional_raw/specialist/`（`seed_stability.csv`、`representation_check.json`） | 正式证据可用 |
| 与传统估计方法的外部参照 | WMLE、LSE 作为外部参照（同一样本、同一划分比较）；MLE 已封存但不再作为论文证据消费 | `artifacts/formal/p4_formal_compare/` | 正式证据可用（已封存） |
| 工程寿命分位点 | 由 P4 逐样本三参数估计派生 `x_0.95`（主指标）、`x_0.90`、`x_0.99`，检查参数收益是否传递 | `artifacts/formal/quantile_derivation/` | 正式证据可用（Codex APPROVE `b9bb815a`）；Vector-MLP 在主设计域保留部分分位点收益（main_holdout −3.6%），但小于参数改善且样本量插值轨道未保留；参数排名≠分位点排名 |
| 域匹配真实案例（后置） | 论文主体接近完成后再做；目前不阻塞写作 | — | 待定（NIST 案例不进入本文） |

## 传统方法参照与 MLE 处理

- **保留 WMLE 作为主要传统方法参照**，**保留 LSE 作为另一类传统方法参照**（仅作外部参照，不决定论文主结论）。
- **MLE 不再审查、不再补跑、不进入论文结果表**；已封存的 MLE 结果不得删除或篡改，只是不再消费为论文证据。
- **Direct-MLP 与 MDM 的完整比较属于独立 Research**，不进入本文标题、摘要和主结果链；相关材料归入 `Research/`。

## 独立 Research（不属于论文主线，已在 `Research/` 归档或登记）

1. **Direct-MLP 与 MDM 路线比较**：P3/P4 的 Direct-MLP 公平比较实现与封存产物（见 `Research/README.md`）。
2. **神经网络输入表示与样本量**：`调研-NN输入特征/`、`样本特征选取与样本量关系/` 专题 pilot 调研（已移入 `Research/`）。
3. **RAW 与 Tabular 候选模型**：`artifacts/candidate/E3b_RAW_specialist/` 等候选模型（原位登记）。
4. **评价指标与其他估计路线**：`调研-评价指标/`、`估计结果直观化与方法横向对比/`（已移入 `Research/`）。

## 待移出 Study01

旧论文草稿、旧组会材料、被当前权威文档取代的规划和执行记录、失效或被替代的实验说明、NIST 叙事材料等已移入 `待移出Study01/`，并在其 `README.md` 中登记索引。**不删除任何研究材料**；因代码/审计路径依赖而无法移动的文件保留原位并在索引中登记原因。

## 工程分位点口径

- 已从 P4 已有逐样本估计派生：`x_0.90`、`x_0.95`（主指标）、`x_0.99`（产物 `artifacts/formal/quantile_derivation/`）。
- 已删除原规划中的 `x_0.50`。
- 不得为此重跑估计器或反向调参。

## 真实数据

真实案例后置到论文主体接近完成后再做，目前不阻塞写作。现有 NIST 6061-T6 案例（`artifacts/formal/real_data/nist-6061-t6-fatigue/`）**不进入本文**；其原始与封存证据不得删除或改写。

## 推荐阅读顺序

新窗口或新 agent 接手时，建议按下面顺序阅读：

1. 项目入口：`README.md`
2. 本文件：`Study/01-study-MDM最小偏移量优化研究/README.md`
3. 当前论文准备文件：
   - `00-研究问题与边界.md`（论文能主张什么、不能主张什么）
   - `01-证据索引.md`（主张到实验及正式数据位置的映射）
   - `02-实验协议.md`（仍然有效的实验定义与评价口径）
   - `03-论文骨架.md`（五部分论文论证骨架）
   - `04-待复核清单.md`（论文完成清单）
4. 唯一活动论文稿（只读）：
   - `D:\博士阶段\200学术项目管理\200学术项目管理\230论文写作\260726study01论文写作\Study01论文初稿-v0.3.md`
5. 独立研究材料：`Research/README.md`
6. 待移出材料索引：`待移出Study01/README.md`
7. 历史与反思：
   - `mentor反思记录/`（P4 后论文主张审查记录）
   - `history/`（历史归档）
8. 如需核对实现或重跑实验，再读：
   - `code/`（正式代码入口）
   - `tests/`（合同测试）
   - `python/methods/mdm.py`、`python/studies/common/README.md`

## 目录结构

```text
Study/01-study-MDM最小偏移量优化研究/
  README.md                   <- 入口、当前科学状态、核心实验表、支撑验证表、阅读路径
  00-研究问题与边界.md         <- 论文目标、能主张什么、不能主张什么
  01-证据索引.md               <- 主张→实验→正式数据位置映射
  02-实验协议.md               <- 仍然有效的实验定义与评价口径
  03-论文骨架.md               <- 五部分论文论证骨架
  04-待复核清单.md             <- 论文完成清单
  artifacts/                   <- 正式/候选/pilot 实验产物（封存，不移动）
  code/  tests/                <- 正式代码与合同测试（不移动）
  manuscript/                  <- G7 审计链目标与图表（auto_audit 依赖其路径，不移动）
  mentor反思记录/              <- P4 后 mentor 审查记录
  Research/                    <- 独立 Research 材料
  待移出Study01/               <- 待移出材料
  history/                     <- 历史归档
```

## 工作边界

- 不要把 `docs/research/04...` 的汇报页码直接当作论文目录。
- 不直接引用早期轮次数字；旧 `docs/research` 结果只能作为 pilot evidence，正式正文数字必须来自本目录下重新设计、重新实现、重新验证的实验产物。
- MDM 当前默认语义以 `python/methods/mdm.py` 为准：`gamma >= 0`，负 offset-root 截断到 `gamma = 0`，默认偏移量 `delta = 0.1`。
- 正式实验应优先调用 `python/studies/common` 与 `python/methods/mdm.py`，但正式代码、配置、manifest 和输出应组织在本目录下。
- 正式实验必须保留 `results.csv`、`summary.json`、`manifest.json` 等可复现实验产物。
- 本目录应保存论文级整理材料；大规模原始输出不要直接堆进来，除非先说明用途和来源。
- 替换或重绘已进入论文工作流的图表前，必须先把旧版完整导出包归档到 `history/figures/YYYY-MM-DD-<figure>-<revision>/`，并附来源提交、替换原因和恢复说明；禁止只覆盖或删除旧图。
- `artifacts/formal/shared_data/mc_scan_raw.csv` 被 `.gitignore` 排除（体积过大）。干净 clone 后需先运行 `python code/generate_mc_data.py --merge-only` 从 tracked chunks 合并出分析输入。tracked chunks 是正式数据源，`mc_scan_raw.csv` 是分析脚本的直接读取对象。
- 不要把本文写成“用神经网络优化 MDM”的单一 ML 论文；本文主线是偏移量 `delta` 的层级最优性、改善幅度和部署可达性。神经网络（分 n MLP）是解决样本自适应 `delta` 选择问题的当前主要方法，但不是论文目的本身。
- 有量纲排序原始样本输入不具备单位不变性：本文结论只适用于与训练一致的物理单位及尺度范围，不声称跨单位、跨尺度泛化；MDM 本身的尺度等变性与网络输入的单位依赖性分开表述。

## 与 `docs/research` 的关系

`docs/research` 下的 `01`–`09` 是围绕更小问题逐步展开的小研究（评价口径、MDM 有解性、最佳偏移量、NN 自适应选取、估计量特性、等变修正、分位寿命、WMLE 权重学习、NN 直接估计）。它们很有价值，但不是最终论文结构本身，也不是投稿论文的正式实验证据：

```text
docs/research/01-04 = 分问题研究、阶段汇报与 pilot evidence
Study/01           = 面向发表的小论文工作区，承载正式实验和论文稿
```

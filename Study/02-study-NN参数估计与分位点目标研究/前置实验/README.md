# Study/02 前置实验区

> 创建日期：2026-08-05（Study02 P–Q 受控对照重组）
> 职责：归集旧前置研究 A 的文档、配置与代码索引，覆盖过去用于研究以下问题的内容：
> 输入表示、architecture、loss 形式、fixed/shared n、joint/independent output、
> 参数合法化、model selection，以及 A-E1/A-E3/A-E2 等前置认证。
> 这些材料保留为**研究过程材料**，不再与 P–Q 正文主线混在一起。

## 一、文档（7 份，原文未篡改，git 记录 rename）

| 文档 | 内容 |
|---|---|
| `00-A-执行状态.md` | 前置研究 A 执行状态、单写者租约、阶段关闭顺序 |
| `01-A-研究问题.md` | A 的权威问题清单、范围、优先级、完成标准（19 问） |
| `02-A-实验协议.md` | A 的证据规则、实验模块、待冻结正式配置 |
| `03-A-实验计划.md` | A 的执行顺序、阶段闸门、当前状态 |
| `04-A-文献与复现审计.md` | G1 文献证据、复现对象、已确认配置、重建边界 |
| `05-A-证据索引.md` | 19 问逐题答案、证据来源、边界与复现索引（A-E1 r5 / A-E3 r2 只读引用） |
| `06-A-前置研究报告.md` | A 正式成果报告与对主研究的落实建议 |

## 二、研究主题 → 位置映射

| 主题 | 主要材料 | 位置 |
|---|---|---|
| 输入表示（V 排序样本值 vs F2 特征、等变归一化） | `code/study02a/representations.py`；A1/A4 结论 | 原位 `code/`；`05-A-证据索引.md` |
| architecture（m12 joint fixed-n、shared DeepSets、候选筛选） | `code/study02a/models.py`；`code/study02a/selection.py`（D7 DecisionSpec）；G2/G3 搜索配置 | 原位 `code/`、`configs/A-g2-search-v1.json`、`configs/A-g3-pilot-amendment-*.json` |
| loss 形式（Huber vs MSE、变换目标 + 标准化） | `code/study02a/training.py`；A-E3 stage1 loss 选择 | 原位 `code/` |
| fixed/shared n | A-E3 `n_strategy` decision（F2_or_V_vs_S）；`models.py` | 原位 `code/` |
| joint/independent output | A-E3 `output_form` decision；`models.py` | 原位 `code/` |
| 参数合法化（log β、log(η/scale)、log((min−γ)/scale)、输出变换） | `code/study02a/representations.py`、`training.py` | 原位 `code/` |
| model selection（G2/G3 两阶段搜索、D7 选择引擎、tie-break） | `configs/A-g2-protocol-v1.json`、`configs/A-g2-search-v1.json`、`code/study02a/selection.py` | 原位 |
| A-E1 前置认证（349 fits，V 路线，F2_vs_V） | 外部运行 `C:\weibull-runs\study02\...\A-E1-formal-r5-20260727-222417`；`code/study02a/formal_*.py` | 原位 `code/`；`05-A-证据索引.md` |
| A-E3 前置认证（266 fits，huber+m12+joint+fixed） | 外部运行 `A-E3-formal-r2-20260730-111949`；`code/study02a/formal_*.py` | 原位 `code/`；`05-A-证据索引.md` |
| A-E2 相关（参数错误/offset 审计） | A 阶段 formal 产物索引见 `05-A-证据索引.md` | 原位 |
| pilot 实验 | `artifacts/pilot/`（G3-pilot-*、G3-matrix） | 原位 `artifacts/` |
| lean 预检 | `artifacts/lean/E1-E4-*`；`code/test_E*_preflight.py`、`code/E*-training-sensitivity.py` 等 | 原位 |

## 三、与 P–Q 主线的关系

- 前置实验为 P 路线的表示与训练设置提供了依据，但 **P–Q 实验不沿用 A 的旧 formal 控制面**
  （formal scheduler、authority、unseal/consume、hash-chain、capsule、攻击防护、lease），
  也不消费 A 的 formal test 命名空间。
- 旧 formal 引擎只读冻结，不再扩建。
- P–Q 使用独立、窄而清晰的专用入口 `code/study02pq/`，数据与划分对齐 Study01 Dimensional-RAW。
- 本区材料可作研究过程与设计参考；不得混入 P–Q 正文主线作为证据。

## 四、消费规则

1. 前置实验结论只用于理解历史与设计演进，不作为当前论文证据。
2. 需要追溯 A-E1/A-E3 等认证细节时，从 `05-A-证据索引.md` 定位原始运行工件。
3. 本区文档原文不修改；任何需要更新的说明写入当前主线文档或本 README。

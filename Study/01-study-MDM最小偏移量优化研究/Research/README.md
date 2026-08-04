# Research（独立研究材料）

> 创建日期：2026-08-04
> 职责：归档**不再属于论文主线的独立研究材料**，并按科学目的分类。这里的材料仍具有研究价值，但按当前论文口径不进入本文标题、摘要和主结果链。
> 规则：正式数据、共享代码和 P4 大文件不复制；因路径/哈希/复现依赖无法移动的材料保留原位，本索引指向其现有位置。不删除任何研究材料。

## 分类

### 1. Direct-MLP 与 MDM 路线比较

Direct-MLP（直接回归三参数的受控 NN）与 MDM 家族（MDM-Default / MDM-Vector-MLP）的完整公平比较属于独立 Research，不进入本文。材料保留在原位：

| 材料 | 位置 |
|------|------|
| Direct-MLP 公平比较实现与仓库外 smoke | `code/run_p3_direct_mlp.py`、`code/run_p3_fair_compare.py`、`code/run_p3_smoke.py` |
| Direct-MLP 合同测试 | `tests/test_p3_direct_mlp.py` |
| Direct-MLP 配置 | `code/p3_config.py` |
| P4 正式六方法比较运行脚本与配置 | `code/run_p4_formal_compare.py`、`code/run_p4_smoke.py`、`code/p4_config.py`、`tests/test_p4_formal_compare.py` |
| P4 正式六方法比较封存产物 | `artifacts/formal/p4_formal_compare/`（seal `f00b561d`，SHA256SUMS 17/17） |

说明：P4 封存产物中，WMLE 与 LSE 作为本文传统方法外部参照被消费；MLE 已封存但不再作为论文证据；Direct-MLP 与 MDM 的完整比较为独立研究结论。

待办（Research 背景，不属于论文完成清单）：核对同团队及其他 NN 直接估参论文，确认输入、输出、损失、参数空间和比较协议，作为 Direct-MLP 公平对照与撰写该独立 Research 的讨论的前置条件。

### 2. 神经网络输入表示与样本量

已移入本目录：

| 材料 | 位置 |
|------|------|
| NN 输入特征文献调研（为什么这些统计量有候选合理性） | `神经网络输入表示与样本量/调研-NN输入特征/` |
| 输入表示、显式样本量、联合/分样本量训练的 pilot 验证 | `神经网络输入表示与样本量/样本特征选取与样本量关系/` |

> 注意：`神经网络输入表示与样本量/样本特征选取与样本量关系/README.md` 中的“上一级 `调研-NN输入特征/`”指同目录下的 `神经网络输入表示与样本量/调研-NN输入特征/`。

### 3. RAW 与 Tabular 候选模型

RAW 输入与 Tabular 统计特征输入的候选模型对比属独立研究。材料保留在原位：

| 材料 | 位置 |
|------|------|
| E3b RAW 专用候选模型（candidate，非正式） | `artifacts/candidate/E3b_RAW_specialist/` |
| RAW 专用模型训练脚本 | `code/run_E3b_RAW_specialist.py` |
| Tabular/Vector-MLP 架构图脚本 | `code/plot_tabular_l6_architecture.py`、`code/plot_vector_mlp_architecture.py` |

> 相关结论在 2026-07 已确认 `Tabular-L6` 不进 Ch6 当前主文比较；RAW/Tabular 对比留作独立研究背景。

### 4. 评价指标与其他估计路线

已移入本目录：

| 材料 | 位置 |
|------|------|
| 评价指标调研（参数准确性评价口径） | `评价指标与其他估计路线/调研-评价指标/` |
| 估计结果直观化与传统方法横向对比（单组合 pilot） | `评价指标与其他估计路线/估计结果直观化与方法横向对比/` |

> `评价指标与其他估计路线/估计结果直观化与方法横向对比/` 为 2026-07 前完成的单参数组合 pilot 横评（MLE/WMLE/LSE/LRE 与 MDM），范围有限，不支撑全域排序，仅作实现和指标复用参考。

## 与其他目录的关系

- 本目录只放**非正式、可移动**的调研与解释性材料；正式数据与共享代码在原位。
- 待移出的旧草稿、旧组会材料、被取代的规划记录见 `../待移出Study01/README.md`。
- 论文主线与权威文档见 `../README.md`、`../00-研究问题与边界.md`、`../01-证据索引.md`。

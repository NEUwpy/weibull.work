# Study01 独立 Research

本目录保存与 Study01 有关、但不参与当前论文主论证的研究支线。它们可以独立成题，也可以为后续工作提供材料；不能因为仍在仓库中就自动成为当前论文证据。

## 1. 神经网络输入表示与样本量

位置：`神经网络输入表示与样本量/`

包括旧统计特征输入、RAW 输入、联合训练、分 $n$ 训练和样本量机制的探索。当前论文已选择“有量纲排序原始样本 + per-n specialist”，这些旧调研用于解释决策历史，不替代 E6 正式结果。

相关候选产物因代码路径和体积保留原位：

- `artifacts/candidate/E3b_RAW_specialist/`
- `artifacts/formal/E3b_vector_mlp/`
- `artifacts/formal/E3_sample_adaptive/`
- `artifacts/formal/E5_normalized_raw/`

## 2. Direct-MLP 与 MDM 路线比较

Direct-MLP 回答“神经网络直接估计参数与选择 MDM 偏移量有何差别”，但它不是本文关于偏移量选择的必要前提，完整比较不进入本文标题、摘要和主结果链。

相关材料保留原位：

- `code/p3_config.py`、`run_p3_direct_mlp.py`、`run_p3_fair_compare.py`、`run_p3_smoke.py`
- `code/p4_config.py`、`run_p4_formal_compare.py`、`run_p4_smoke.py`
- `tests/test_p3_direct_mlp.py`、`tests/test_p4_formal_compare.py`
- `artifacts/formal/p4_formal_compare/`

## 3. 评价指标与其他估计路线

位置：`评价指标与其他估计路线/`

包括评价指标调研、固定参数组合下的 MLE/WMLE/LSE/LRE 横向对比和直观表格。当前论文只计划在新 E6 设计上补 WMLE/LSE 外部参照，旧单组合结果不能承担新路线结论。

## 使用规则

1. Research 材料不得直接写入当前论文结论。
2. 若要转回正文证据，必须先在 `02-实验协议.md` 中说明它回答哪个必要问题，并在 `01-证据索引.md` 建立当前路线的证据映射。
3. 不为“也许以后会用”继续扩建公共流水线；出现明确第二个使用者后再抽象。
4. 旧结果和当前 E6 结果设计不同，不作无边界数值排名。

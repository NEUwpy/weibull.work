# NN 输入表征与样本量机制

> 成熟度：`COMPLETE`
>
> 关系角色：`SUPPORTING`
> 原项目名：Study1.5 / Study015

## 研究问题

在 Study01 的 26 点 MDM delta 风险曲线任务中，比较三种受控输入表示 `F13 / F12 / RAW`，并考察单一样本量训练、混合样本量训练和留一样本量外推的差异。它回答的是输入表征与训练组织机制问题，不承担独立论文义务，也不属于 Study01 或 Study02 的 formal 证据链。

研究域固定为既有参数网格、`n=7,10,20`、近似等容量 MLP。结论不得外推到连续样本量、未见参数、真实数据或所有原始样本网络。

## 完成情况

- Explore：seed 42，30/30 模型完成；
- Confirm：seed 2026、3407，60/60 模型完成；
- 合计：90/90 模型，无训练失败、非有限预测或键错配；
- root / explore / confirm 三套 manifest 分别绑定 116 / 35 / 65 个产物。

## 主要答案

1. 在该限定任务中，F13 相对 RAW 的优势较小且随 `n` 变化；这不证明统计特征普遍优于原始样本。
2. 删除显式 `n` 后的 F12 仍携带明显样本量信息；显式 `n` 的增量较小，最清楚地出现在 `n=20`。
3. 不同 `n` 不能当作可互换训练域。混合样本量训练在 `n=7` 可能获益，但在 `n=10,20` 出现代价；未见样本量外推能力有限。
4. 切换成 RAW 不能自动消除混合样本量训练问题；输入表示与训练组织是两个独立设计维度。

## 权威入口

- 研究目的与边界：`02-研究目的计划与边界.md`
- 冻结执行合同：`03-第一阶段执行合同.md`
- 最终报告：`artifacts/stage1/report.md`
- 根 manifest：`artifacts/stage1/manifest.json`
- 探索与确认 manifest：`artifacts/stage1/explore/manifest.json`、`artifacts/stage1/confirm/manifest.json`
- 执行代码：`code/run_stage1.py`

## 证据保护

本目录由 `Study/015-study-NN输入表征与样本量机制研究` 原字节迁入。`code/run_stage1.py` 受 manifest 的 `code_version` 绑定；历史合同、报告、manifest 和 artifacts 均保持原字节，不因目录整理而重写或重封。路径迁移记录见项目级 `../RELOCATION.json`。

早期 Study01 输入研究材料迁入后统一放在 `history/Study01早期研究/`，不得与本研究的冻结结果混作同一证据等级。

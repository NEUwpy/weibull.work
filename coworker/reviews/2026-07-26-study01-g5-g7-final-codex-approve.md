# Study01 G5–G7 最终独立复核

> 日期：2026-07-26
>
> 结论：**APPROVE**
>
> 候选分支：`origin/study01xu`
>
> 候选 tip：`ad4dbdb4232bf25d3bcc4345e07ef3b69e04b4fe`

## 审查范围

本次复核以实际 Git 提交、正式 artifacts、可执行稿件审计和干净检出的测试结果为准，不以执行报告代替证据。审查覆盖 Study01 正式 E4d/R1、R2、P6–P8 真实数据验证、G5 图表、G6 五部分稿件、G7 claims-to-data 与投稿审计链。

## 独立验证

- 干净 detached worktree 精确检出 `ad4dbdb4`。
- P6–P8 核心测试与 G7 真实负向审计合计：`163 passed, 0 failed, 0 skipped`。
- `manuscript/audit/auto_audit.py`：`ALL AUDIT CHECKS PASSED`。
- P8a `SHA256SUMS_p8a`：5/5 文件逐项重新计算并匹配。
- `claims-to-data.csv` 恰好包含 C001–C033；生产审计核对 claim ID 集、来源文件、来源字段和 artifact 重算值。
- 10 项 G7 专项测试实际篡改临时副本并调用生产 `audit_manuscript()`，覆盖错误值、缺失/额外 claim、错误来源、遗留图表状态、缺失引用和错误样本计数。
- 正式实验产物未在稿件审计修订中重跑或覆盖。

## 审查结论

在当前论文冻结边界内，Study01 的正式实验、证据链、图表、五部分稿件和投稿前技术审计均已完成，未发现阻塞合并的问题。

结论为 **APPROVE**：

- 允许把 `study01xu` 合并进 `main`；
- 允许将 Study01 状态写为“正式实验与论文技术包闭环”；
- 不将该结论扩大为“已经投稿”；
- 不把 E3c 连续空间训练、多数据集外部验证或 $\delta>1.00$ 探索列为当前论文的补做条件。

## 合并说明

`08-更新日志.md` 与当前 `main` 的 Study02 R12 条目发生预期内容冲突。合并时必须同时保留两条研究线，并使用唯一版本号；不得用 Study01 分支版本覆盖 Study02 收口记录。

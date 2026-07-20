# Study/02 A G3 formal implementation plan oracle review

> 日期：2026-07-12
> 审查对象：`coworker/plans/2026-07-12-study02-a-g3-implementation.md` Round 2
> 结论：**APPROVE**

## 总判断

上轮七项修订均已落实为明确接口、测试、产物和状态机合同。计划现在足以实施 G3 formal training/validation，并在后续独立 oracle 明确批准后执行一次 test。该 APPROVE 是对实施计划的批准，不等于提前批准 test unseal 或研究结论。

## P0：阻塞项

无。

## P1：核对通过

### P1-1 amendment-v4 强制传播

- Global Constraints 已把 `A-g3-pilot-amendment-v4.json` 及其 SHA-256 纳入权威链。
- 唯一 `EffectiveFormalConfig` 入口只允许覆盖 max epochs `500→100`，并保持 min epochs 50、patience 40。
- 缺失/错误 amendment、残留 500、非法 CLI override 或散落硬编码均有 fail-closed TDD 要求。

### P1-2 formal manifest 合同

- manifest 已要求 base protocol/search ID 与 SHA、amendment ID 与 SHA、effective epoch 合同、820-fit matrix hash、fit 子集、code commit、角色 namespaces、seeds、sealed state 和 predecessor trace hash。
- 字段缺失、hash 不匹配、上游 trace 改变均要求失败或新 run ID。

### P1-3 S formal collate/training

- 计划新增 `formal_data.py` 和专门测试。
- values、boolean mask、显式 n 分离；padding 不参与 pooling；覆盖 mixed n、permutation invariance、mask count 和真实 train/validation smoke fit。
- S 与 MLP 共享 effective 100-epoch 合同。

### P1-4 selection、ceiling-hit 与 leakage

- `selection_trace.jsonl`、`fit_status.csv`、`ceiling_hit_report.json`、`leakage_audit.json` 和 `pre_unseal_bundle.json` 均已成为强制产物。
- 每 fit 保存 actual/best epochs、epoch-100 flag、停止原因、validation 分数、checkpoint hash 和失败状态。
- ceiling report 包含入选臂与末段 validation slope/曲线；若关键臂触顶且仍改善，按计划继续 sealed 并修订合同。

### P1-5 approval-bound test 双闸门

- `formal-select` 无 test 参数并要求 `test_access_count=0`。
- oracle approval artifact 绑定 code、effective config、selection、ceiling 和 leakage hashes。
- `formal-test` 缺失/失配 approval、重复执行或 consumed 状态均 fail closed。
- 状态只允许原子 `sealed → unsealed_once → consumed`，并追加写 ledger。

### P1-6 A-E1→A-E3→A-E2 依赖

- A-E1 先冻结唯一 baseline trace。
- A-E3 必须验证 A-E1 trace hash；A-E2 必须验证 A-E3 trace hash。
- 上游变化使下游失效并要求新 run ID，依赖不再只靠人工顺序。

### P1-7 一阶段一提交

- pilot checkpoint 已独立完成。
- Task 9 不创建 G3 阶段完成提交。
- Task 9 formal 结果与 Task 10 证据、Nature 图和报告在最终审查后形成一个 G3 formal 阶段提交并推送，已消除冲突。

## P2：非阻塞项

- 验证基线已更新为 v7 的 152 passes，并保留精确 ignore 文件与理由。
- Task 10 的 Nature 图合同、源数据、Python-only 导出与视觉 QA 仍完整。
- 已完成任务中的旧示例代码若与当前 S forward 签名不一致，可在维护计划文档时更新，但 Task 9 的当前强制接口与测试是权威实现依据，不阻塞执行。

## 下一闸门

1. 按 Task 9 TDD 实现 formal config/data/contracts/state；
2. 在 test sealed 下依次运行 A-E1、A-E3、A-E2 training/validation；
3. 生成并冻结 pre-unseal bundle；
4. 请求独立 `APPROVE test unseal`；
5. 未获得该批准前不得读取或评价 test。

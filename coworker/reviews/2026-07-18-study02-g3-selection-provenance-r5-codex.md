# Study/02 G3 selection provenance — Codex R5 review

Verdict: **APPROVE**（仅批准 R4/D7 selection point-evidence provenance 增量；不等于批准 A-E1 formal）。

## 审查范围

- 远端交付基线：`3032eb5462a1473143c438b7220665c4595f5122`。
- 执行者报告：`coworker/reports/2026-07-18-study02-g3-selection-provenance-r4-claude.md`。
- 实际审查 `a325208..3032eb5` 的 Git diff、实现、测试与冻结科学口径。
- 本地其后的 coworker live-loop 基础设施提交不属于 R4 科学增量。

## 结论

R4 的两个阻塞均已闭合：

1. `rebuild_selection_point_provenance` 从真实 `checkpoint.pt` 与冻结 validation 输入独立重建逐点证据；`assert_point_evidence_provenance` 对 checkpoint SHA、validation identity、失败状态、标量和 canonical records 逐字段比较。同步伪造 point artifact 及其下游哈希不再能够通过 pre-unseal。
2. canonical point records 已增加精确字段、类型、有限性、support seed、`legal/failure`、`L_param/e_*`、冻结失败惩罚以及跨候选 `point_id` 一致性守卫。

公开 artifact/trace/receipt/bundle 的序列化字段未改变；本次属于输入合同与校验收紧，不要求无必要升 schema 版本。未发现改变冻结指标、bootstrap、failure penalty 或模型选择规则的科学口径漂移。

## Codex 独立验证

在 detached `3032eb5` 快照上执行：

- `test_study02a_selection_rules.py` + `test_study02a_formal_evidence.py`：`52 passed`。
- `test_study02a_formal_selection.py -m "not slow"`：`6 passed, 1 deselected`。
- `test_point_evidence_provenance_rebuild_from_checkpoint_rejects_forgery`：`1 passed`。
- `test_validation_l_param_reproduces_from_checkpoint`：`1 passed`。
- 正确路径 `python -m compileall .../code/study02a`：通过。
- `git diff --check a325208..3032eb5`：通过。

完整 261 项回归在本机两次因运行时间上限被终止；该事实不记作通过，也未出现失败输出。上述定向覆盖直接命中 R4 两个阻塞，结合执行者留下的完整 261-pass 报告，足以批准本棒。

## 后续硬条件

- D8 生产入口必须自行调用 checkpoint provenance rebuild，再把结果交给 `build_pre_unseal_bundle`；不得允许生产调用者以任意外部映射替代独立重建。
- D8、staged A-E1、完整临时 smoke 及其他运行器门禁完成并经 Codex 复审前，A-E1 formal 仍未授权。
- test 保持 `sealed`；本审查不批准 9d，也不批准任何 test 访问。
- 不要求为 R5 额外执行完整约 177-fit A-E1 concrete run；该运行属于后续 staged/formal 棒，而不是 R4 组件验收。

## 下一动作

Codex Controller 使用 coworker live loop 启动一根有边界的 Claude executor 棒，实现 D8 占位符解析、deferred-spec/predecessor 生产接线及其 fail-closed 测试；本棒不得启动 staged/formal run，不得访问 test，不得改变冻结科学口径。

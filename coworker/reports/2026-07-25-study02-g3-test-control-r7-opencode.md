# G3 Test Control Plane R7 执行报告

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`eec3855a` (origin/main)
> 状态：**awaiting Codex R7 review**（不得声称 test consumer 或 formal ready）

## R7 实现：真实实验权威接线

| 完成条件 | 实现 |
|----------|------|
| 三 run 实际调用 `_rebuild_authority` | `verify_g3_chain_authority`：对 A-E1/A-E3/A-E2 各调用 `_rebuild_authority(validate_controller=False)`，验证 manifest/plan/events/state 完整重放 |
| 无 live claim | 检查每个 run 的 `state["active_claim"] is None`，否则 fail-closed |
| Cohort fit 与 replay fit_state/receipt/checkpoint 一致 | `derive_g3_cohort_from_authority`：每个 fit 必须 `fit_states[fit_id] == "succeeded"`，checkpoint.pt 和 fit_status.json 存在且 SHA 非空 |
| Resolution 使用既有验证器 | `resolve_g3_placeholders_from_evidence`：A-E1 从 staged_resolution_ledger.jsonl；A-E3/A-E2 从 selection_trace.jsonl 经 `_validate_selection_trace_bytes` 验证 |
| 所有 selected:*/selected_top_*/training_size=-1 唯一解析 | `_resolve_or_fail`：未解析即 raise，无默认值 |
| 最小生产入口 | `build_g3_accreditation`：chain → authority → cohort → resolve → manifest → bundle（sealed，不 authorize） |
| formal-consume-test 继续 BLOCKED | 保持 SystemExit |

## 变更文件

| 文件 | 变更 |
|------|------|
| `study02a/formal_g3_control.py` | +`G3Authority` dataclass, +`verify_g3_chain_authority`, +`derive_g3_cohort_from_authority`, +`resolve_g3_placeholders_from_evidence`, +`_resolve_or_fail`, +`build_g3_accreditation` |
| `python/tests/test_study02a_g3_control.py` | +`TestProductionAuthority`（5 测试：rebuild_authority 调用+tamper 拒绝、non-succeeded 拒绝、unresolved 拒绝、live claim 拒绝） |

## 测试命令与结果

```
python -m pytest python/tests/test_study02a_g3_control.py -q → 26 passed, 4 skipped (5.50s)
  (4 skipped = dirty-tree production-bound tests, 提交后恢复)
python -m compileall study02a -q → OK
verify_frozen_hashes → OK
git diff --check → clean
```

## 验证覆盖

- [x] `_rebuild_authority` 实际被调用（production fixture: materialize + claim + record）
- [x] Tampered plan → `_rebuild_authority` 拒绝
- [x] Tampered receipt → `_rebuild_authority` 拒绝
- [x] Non-succeeded fit → `derive_g3_cohort_from_authority` fail-closed
- [x] Unresolved placeholder → `_resolve_or_fail` fail-closed
- [x] Resolved placeholder → 正确返回值
- [x] Live claim → `verify_g3_chain_authority` fail-closed
- [x] Cohort 精确 205/110/100（冻结 matrix）
- [x] 所有 R6 攻击测试仍通过（24 passed）
- [x] CLI formal-consume-test 仍为 BLOCKED

## 生产入口数据流

```
build_g3_accreditation(ae2_run_dir, artifact_root, cache_root, study_root, code_commit)
  1. resolve_g3_predecessor_chain(ae2_run_dir) → A-E2 → A-E3 → A-E1
  2. verify_g3_chain_authority(chain, cache_root) → _rebuild_authority × 3, no live claims
  3. derive_g3_cohort_from_authority(frozen, chain, authority) → 415 entries, all succeeded
  4. resolve_g3_placeholders_from_evidence(chain, cohort) → no selected:*/selected_top_*/-1
  5. build_g3_test_manifest(cohort, chain, frozen, effective, commit) → manifest_sha256
  6. build_g3_pre_unseal_bundle(manifest, chain, traces, ...) → bundle_sha256
  → {"status": "sealed_ready_for_approval", ...}
```

## 禁止事项确认

- [x] 未启动 formal、authorize 或真实 test
- [x] 未生成 test 数据
- [x] 未执行 consumer
- [x] 未修改冻结 matrix/protocol/selection rule/科学指标/test namespace
- [x] 未继续重构 journal 或扩展通用框架
- [x] 真实 test_access_count 仍为 0

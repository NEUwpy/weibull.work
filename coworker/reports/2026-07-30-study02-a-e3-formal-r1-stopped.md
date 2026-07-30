# Study/02 A-E3 Formal R1 — 停止报告（永久 blocked/aborted）

> 分支：`codex/study02-a-e3-evidence-schema-fix-20260730`（from `cc2a9708`，tip `723e17ce`）
> Run：`A-E3-formal-r1-20260729-214640`
> 状态：**永久 blocked/aborted — r1 不恢复、不迁移、不拼接**
> 修复分支状态：**awaiting Codex review**（待 review 后由 NEUwpy 决定 commit + push；**A-E3 formal r2 尚未授权**）

---

## 1. 停止事件

| 字段 | 值 |
|------|----|
| Run ID | `A-E3-formal-r1-20260729-214640` |
| 模块 | A-E3（staged execution） |
| Predecessor | A-E1 formal r5（`A-E1-formal-r5-20260727-222417`，tip `d2a056f`，V winner） |
| Crash fit | `G3-fit-0483`（A-E3 第一个 independent output_form fit，matrix position 134） |
| Crash 时间 | 2026-07-29 21:46:40 UTC（run-id 时间戳） |
| 异常 | `ValueError: fit evidence output must match its exact canonical schema` |
| Counts | 134 succeeded / 131 pending / 1 dead claimed（G3-fit-0483） / 0 failed |
| Authority | `e11cb2a2…`（无 drift） |
| HEAD | `cc2a9708`（无 drift） |
| test_access_count | 0（test sealed） |

## 2. Crash 调用栈

```
run_a_e3_staged
  → execute_claimed_fit(plan_row=G3-fit-0483 resolved row, …)
    → _write_outputs(run_dir, fit_id, run_id, checkpoint_bytes, checkpoint_sha256, evidence)
      evidence = {…11 canonical fields…, "output_form": {…capacity metadata…}}
    → record_fit_succeeded(run_dir, cache_root, fit_id, owner_id, owner_nonce, output_hashes, timestamp)
      → _rebuild_authority(run_dir, cache_root)            # OK
      → _validate_success_files(run_dir, row, output_hashes)
        → _decode_exact(payload, _EVIDENCE_FIELDS, "fit evidence output")
          set(value) != fields   # evidence has 12 keys; _EVIDENCE_FIELDS has 11
          → raise ValueError("fit evidence output must match its exact canonical schema")
```

G3-fit-0483 的 claim 已写入 journal（dead claimed），但 success terminal 未写入（`_validate_success_files` 先于 `_terminal` 抛出）。134 个前驱 fit（positions 0..133，含 12 loss_screen + 72 search_stage1/stage2 + 50 joint output_form）均已正常 terminal。

## 3. 根因

**`execute_claimed_fit` 向 `evidence` 写入了 `evidence["output_form"]` extra field。**

R3-A/R4-2 的 `_prepare_fit_inputs` 通过 `build_output_form_aware_factory` 返回 `output_form_evidence`（joint/independent architecture ids、exact parameter counts、capacity selection）。`execute_claimed_fit` 将该 metadata 写入 `evidence["output_form"]`：

```python
# formal_executor.py ~line 781 (BUG, removed by this branch's fix)
if prepared.output_form_evidence is not None:
    evidence["output_form"] = dict(prepared.output_form_evidence)
```

scheduler 的 `_EVIDENCE_FIELDS`（formal_scheduler.py:70-74）是 frozen 11-key exact-schema：

```python
_EVIDENCE_FIELDS = {
    "evidence_version", "fit_id", "run_id", "checkpoint_sha256", "actual_epochs",
    "best_epoch_one_based", "hit_epoch_100", "early_stop_reason",
    "terminal_validation_slope", "validation_curve", "test_access_count",
}
```

`_decode_exact`（formal_scheduler.py:242-248）检查 `set(value) != fields`，12-key evidence（含 `output_form`）被拒绝。

**为何 joint output_form（positions 84..133）未 crash**：`build_output_form_aware_factory` 对 joint arm 返回 `metadata=None`（output_form_contract.py:485-493），`_prepare_fit_inputs` 设 `output_form_evidence=None`，`if … is not None` 跳过写入。independent arm 返回 non-None metadata dict（capacity selection 结果），触发写入 → crash。G3-fit-0483 是第一个 independent output_form fit（matrix position 134），恰好在 134 succeeded 之后。

## 4. Stage receipts（crash 前）

134 succeeded fits 覆盖了以下 staged receipts 的前提条件：

- `loss_selection_receipt.json`（loss_screen fits terminal → `transformed_train_z_mse` winner）
- `stage1_selection_F2_or_V_receipt.json`（search_stage1 F2_or_V top4）
- `stage2_selection_F2_or_V_receipt.json`（search_stage2 F2_or_V winner）
- S token 的 stage1/stage2 receipts 尚未到达（S arm fits 在 position 184+）
- `output_form_selection_receipt.json` 尚未生成（output_form fits 未全 terminal）

## 5. 修复

**删除 `execute_claimed_fit` 中的 `evidence["output_form"]` 写入**（formal_executor.py ~line 781）：

```python
# output_form metadata is a deterministic derivative of plan/matrix + frozen
# contract SHA + input_dim + checkpoint. Do NOT write it to evidence.json:
# scheduler _EVIDENCE_FIELDS is frozen (rejects extra fields). Contract SHA
# + factory + capacity derivation remain independently unit-verified.
```

- `output_form_contract.py`（contract v2 SHA + `derive_independent_widths` + `select_independent_capacity` + `resolve_independent_capacity`）：contract/factory/capacity/SHA **不变**（仅修正 docstring 中"metadata 写入 evidence / 是 authoritative audit record / 可从 evidence alone 重建"等失真说明，改为"模型由 authority-bound plan/matrix route + 冻结 contract + input_dim 确定性重建；checkpoint 按该 factory 加载验证；metadata 不写入 evidence、非 authoritative audit record"）。
- `build_output_form_aware_factory` 返回值（factory + metadata）：签名与返回 **不变**（独立合同测试 `test_study02a_a_e3_output_form_contract.py` 仍直接调用并验证确定性 metadata）。
- `_PreparedFit.output_form_evidence` 字段：**删除**（无消费者；`execute_claimed_fit` 与 `_score_fit_from_checkpoint` 均不引用；`_prepare_fit_inputs` 不再保存该 metadata，metadata 在调用处即丢弃）。模型加载/重建不依赖该字段。
- `_EVIDENCE_FIELDS`：**不变**（仍为 frozen 11-key exact-schema）。

修复后：在 Codex review 通过且用户显式授权 A-E3 formal r2 后，从新 SHA 创建 r2 从零执行（**r2 尚未授权**；不恢复 r1、不迁移 134 checkpoint）。

## 6. 现场 run dir 处置

**保留** `A-E3-formal-r1-20260729-214640` 现场 run dir（不删/不恢复/不迁移 134 checkpoint）。用途：

- 作为停止事件的不可篡改现场（authority `e11cb2a2…` + 134 succeeded terminal events + 1 dead claim + journal/anchors/state 全部在盘）。
- 任何恢复/迁移 134 checkpoint 到 r2 的操作都会破坏 r2 的 authority 全链条 replay（134 个 fit 的 checkpoint 是在 buggy code（含 evidence["output_form"] 写入路径）下训练的——尽管 joint output_form 的 evidence 不含 output_form，loss_screen / search_stage1 / search_stage2 的 training 代码路径经过了被 R3-A/R4-2 修改的 `_prepare_fit_inputs`，不能假定 r2 code 下的 training 行为与 r1 完全一致）。

## 7. 回归测试

修复分支新增两个测试（`python/tests/test_study02a_formal_executor.py`）：

| 测试 | 标记 | 路径 | 断言 |
|------|------|------|------|
| `test_a_e3_r1_evidence_schema_fix_independent_output_form_via_real_scheduler` | `@pytest.mark.slow` | REAL `materialize_run` + REAL `claim_next_fit`（target，replays all 269 prerequisite events） + REAL `execute_claimed_fit`（G3-fit-0483） + REAL `record_fit_succeeded` → `_validate_success_files` → `_decode_exact` → `_rebuild_authority` | evidence.json field set == `_EVIDENCE_FIELDS`（无 output_form）；`build_output_form_aware_factory` 返回 capacity metadata（deterministic re-derivation）；`status_run` 135 succeeded / 0 failed / tac=0；ATTACK：手动加 output_form → `record_fit_succeeded` raises exact r1 message |
| `test_a_e3_r1_evidence_extra_output_form_field_rejected_by_decode_exact` | fast | minimal A-E1 materialize + REAL `claim_next_fit` + REAL `_write_outputs`（evidence 含 output_form） + REAL `record_fit_succeeded` | `_decode_exact` raises "fit evidence output must match its exact canonical schema"；attack evidence 与 canonical 的唯一差异是 output_form key |

**Production-bound 路径（r1 crash site G3-fit-0483）**：real `execute_claimed_fit` → real `_write_outputs` → real `record_fit_succeeded` → real `_validate_success_files` → real `_decode_exact` → real `_rebuild_authority`。134 prerequisites 通过 real `_commit_transaction`（real event/publication/anchor/state 写入）批量进入 journal，after-state 增量计算以避免 O(N²) replay-per-event；target fit 通过 real `claim_next_fit` + real `execute_claimed_fit` 走完整 scheduler 路径。

**不绕过**（r1 bug 所在路径）：`_write_outputs` / `record_fit_succeeded` / `_validate_success_files` / `_decode_exact` / authority replay。

**约束**：不改 production code（fix 已完成）；不改 r1 run 目录；不启动 r2/A-E2；不 authorize/unseal/consume。

## 8. Codex 裁决

- r1 **永久 blocked/aborted**：代码 REVISE（删 `evidence["output_form"]` 写入 + 删无消费者的 `_PreparedFit.output_form_evidence` 字段 + 修正 `output_form_contract.py` 失真说明 + 删除测试中对 `_assert_scoped_code_clean` 的 monkeypatch 绕过）。
- r1 run dir 保留为现场。
- 在 Codex review 通过且用户显式授权后，从新 SHA 创建 A-E3 formal r2 从零执行（**r2 尚未授权**）。

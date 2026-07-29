# Study/02 A-E3 Orchestration R1 — C5 执行报告

> 分支：`codex/study02-a-e3-orchestration-r1-20260728`
> Base tip（C4）：`52bc41a85db29dda22e12647ba21c2b5edf7e693`
> C5 未 commit（待 Codex review 后由 NEUwpy commit + push）
> 状态：**CODEX BLOCKED — 不批准 commit/push**

---

### CODEX BLOCK 注记（2026-07-29 加）

**de25710 BLOCK**。R1 工作树（C5 CLI wiring + sealed smoke + 文档）已被 Codex 审查认定为**不可合并**：C5 自身的接线正确，但它所依赖的 C1–C4 已 Frozen 了 3 个 science/contract blocker。3 个 blocker 已被 4 个诊断 reproducer test 钉死（`python/tests/test_study02a_a_e3_blocker_reproducers.py`，`python -m pytest -k "blocker_reproducer" -q` → 4 passed），证明问题在 de25710 真实存在而非审查猜测。

- **Blocker A — SCIENTIFIC CONTRACT AMBIGUITY（joint vs independent 无效对照）**：`A-E3_joint_independent` matrix 行（`matrix.py:58-59`）的 joint 与 independent_capacity_matched 两 arm 共用同一 architecture placeholder `selected:A-E3_architecture`；`resolve_model_factory`（`formal_executor.py:135-163`）仅按 architecture 分发，signature 不含 route/output_form；`build_mlp`（`models.py:31-32`）hardcoded `output_dim=3`；`select_independent_capacity`（`training.py:54`）定义存在但 production executor 从不导入/调用。两 arm 训练的是结构上完全相同的模型，independent arm 没有任何 capacity 特化——A-E3 output_form 决策不是对比性实验，**违反 module_matrix_rules capacity clause 的科学契约**。
- **Blocker B — 无 n_strategy decision（capacity axis 静默丢失）**：`_FIT_KIND_AXIS`（`selection.py:81-88`）无任何 fit_kind → `n_strategy` 映射；`build_decision_specs("A-E3", ...)` 只产生 `output_form:A-E3:selected:F2_or_V`（joint vs independent）一个 capacity 类决策，不产生任何 `n_strategy` 决策；`shared_winner_retrain` fit 不在 `_FIT_KIND_AXIS`，never competes。fixed-n vs shared-n 这一冻结决策轴在 A-E3 selection plan 中完全消失。
- **Blocker C — r5 不可重放 + 跨 commit 拒**：(a) C1（fc12674）把 formal manifest predecessor 段从 r5/d2a056f 的 7-key 扩为 10-key（新加 `selection_staged_ledger_path` / `selection_staged_ledger_sha256` / `resolved_baseline_route`），并由 `_require_exact_fields`（`FC:1162-1167`）exact-match 校验——r5 sealed manifest 在 de25710 下 replay 立刻 fail。(b) `_verify_chain_consistency`（`formal_g3_control.py:976-982`）要求三模块 manifest 的 `code_commit` set 长度恰为 1——任何跨 commit 的 3-run chain（如 A-E1=d2a056f, A-E3/A-E2=de25710）直接被拒，无法在同一 authority 下重放。

**A 是科学正确性问题（不可仅靠测试接线掩盖），B/C 是控制面契约问题**。B 与 C 的修复设计见 R2 报告 `coworker/reports/2026-07-29-study02-a-e3-r2-design.md`。R1 的接线、sealed smoke、文档保持作为历史记录，下方原文未改；新读者请将本注记视作对下方"READY FOR CODEX REVIEW / 无 breaking schema / git diff --check clean"等措辞的**前置订正**（详见下方 §3 / §5 的 inline correction）。

---

## 1. 目标与范围

C5 闭合 A-E3 orchestration r1 的最后一环：CLI wiring + sealed smoke + 文档 + 测试 G.15。基于设计 `stateful-hatching-knuth-agent-a295f965170a6739c.md` 的 B.8/H 节。C1–C4 已就位（`fc12674` / `8d29a85` / `6e30693` / `52bc41a`）：`PredecessorTrace` + staged_ledger 字段、`_validate_staged_resolution_ledger`、`_a_e3_fit_stage` + scoring resolver、stage builders + recover/ensure、`run_a_e3_staged` + `resolve_a_e3_staged_selection`（9-record ledger）。

**不做**：不改科学（matrix/config/metric/penalty/rule/seed）；不启动真实 A-E3/A-E2 formal；不进 G3 accreditation/authorize/unseal/consume/9d/G4；不 mock 整个 orchestrator/scheduler/scoring/predecessor-validation。

## 2. Changed files

| 文件 | 改动 |
|------|------|
| `Study/02-.../code/run_study02a.py` | formal-execute A-E3 arm（构建 PredecessorTrace + 调 `run_a_e3_staged`）；formal-staged A-E3 arm（调 `resolve_a_e3_staged_selection`）；`_build_predecessor_trace` 辅助（从 `resolve_deferred` 提取，staged_ledger 字段扩展）；`--predecessor-run-id` 新增；imports 扩 `run_a_e3_staged` / `resolve_a_e3_staged_selection`；`formal-staged` `--module` 扩 `A-E3` |
| `python/tests/test_study02a_cli.py` | 拆分 `test_formal_execute_dispatches_a_e3_a_e2_to_run_module` → A-E3 dispatches to `run_a_e3_staged`（含 `--predecessor-run-id` + `_build_predecessor_trace` mock）；新增 A-E3 缺失 predecessor-run-id 的 fail-closed 测试；A-E2 仍 dispatches to `run_formal_module`（不动） |
| `python/tests/test_study02a_formal_executor.py` | 新增 `_build_a_e3_pred_trace` 辅助；`test_formal_staged_cli_wires_a_e3_resolver`（non-slow CLI wiring）；`test_g15_a_e3_final_selection_accepted_as_a_e2_predecessor`（@slow）；`test_g16_a_e3_sealed_smoke_production_equivalent`（@slow） |
| `README.md` | Study02 快照段：A-E1 r5 APPROVE/frozen predecessor；A-E3 orchestration wiring 真实完成度；**A-E3 formal 尚未授权** |
| `Study/02-.../00-A-执行状态.md` | A-E3 orchestration r1 完成度 + 尚未 formal 授权 |
| `Study/02-.../03-A-实验计划.md` | A-E3 orchestration 接线状态；停止条件更新为"A-E3 formal 授权前" |

## 3. 控制面 schema 变化

> **CODEX 订正（2026-07-29）**：原 "无 breaking schema 变化" 措辞**不成立**，仅对 C5 vs C4 的 diff 成立。C1（fc12674）相对 r5/d2a056f 是**破坏性 schema 变化**：formal manifest predecessor 段从 7-key 扩为 10-key，由 `_require_exact_fields`（`FC:1162-1167`）exact-match 强制——r5 sealed-run manifest 在 de25710 下**无法 replay**（见 Blocker C reproducer）。下方原文保留作为历史措辞，但"无 breaking schema"应读作"无 C5-vs-C4 breaking schema；C1-vs-r5 为 breaking，已 block"。

**~~无 breaking schema 变化~~**（见上方订正；C5 自身相对 C4 不新增 artifact 字段）：

- `PredecessorTrace` staged_ledger 字段（`staged_ledger_path` / `staged_ledger_sha256`）在 C1 已加入；C5 只是通过 `_build_predecessor_trace` 在 CLI 路径填充它们（assembly 逻辑从 `resolve_deferred` 提取复用，行为等价）。
- A-E3 manifest 的 `predecessor` 段（含 `selection_staged_ledger_path` / `selection_staged_ledger_sha256` / `resolved_baseline_route`）由 `materialize_run` 在 C1 已实现的 `_validate_predecessor` 产生；C5 不改 manifest schema。
- A-E3 `staged_resolution_ledger.jsonl` 的 9-record 链 schema 在 C4 已定义（`_STAGED_LEDGER_SEQUENCES["A-E3"]`）；C5 不改。

唯一新增：`formal-execute` 子命令新增 `--predecessor-run-id` 参数（A-E3 必填，A-E1/A-E2 忽略）。

## 4. Authority + evidence 数据流

```
A-E1 r5 staged run（predecessor）
  selection_trace.jsonl + selection_receipt.json + selection_ledger.jsonl
  staged_resolution_ledger.jsonl（8-record, V winner）
  manifest.json（code_commit）
      │
      ▼  _build_predecessor_trace (run_study02a.py)
  PredecessorTrace(
      module_id="A-E1", trace/receipt/ledger SHAs,
      staged_ledger_path + staged_ledger_sha256,   ← C1 control-plane v2 binding
      selection_code_commit)
      │
      ▼  run_a_e3_staged(predecessor=trace)
  materialize_run → _validate_predecessor("A-E3", trace)
      │  verifies trace SHA / receipt SHA / ledger binding /
      │  staged_ledger SHA + 8-record chain + resolved_baseline_route="V"
      ▼
  A-E3 plan.jsonl（每 fit 的 selected:F2_or_V → V placeholder）
      │
      ▼  staged driver loop（claim → train → record）
  _ensure_a_e3_loss / stage1 / stage2 / output_form（6 receipts）
      │  stage builder score_fit 注入（_a_e3_staged_score_fit）
      ▼
  build_module_selection("A-E3")  ← score_fit=None 时 checkpoint-forward
      │  _score_fit_from_checkpoint（real forward pass）
      ▼
  selection_trace.jsonl（6 decisions）+ receipt + ledger
      │
      ▼  resolve_a_e3_staged_selection
  staged_resolution_ledger.jsonl（9-record chain from _ZERO_HASH）
      loss → stage1:F2_or_V → stage2:F2_or_V → stage1:S → stage2:S
      → output_form → shared_winner_retrain:S → baseline_route → final_aliases
      baseline_route.input.predecessor_staged_ledger_sha256 = <A-E1 SHA>
      │
      ▼  _validate_predecessor("A-E2", ae3_trace)
  A-E2 downstream binding（staged_ledger SHA bound，resolved_baseline_route="none"）
```

## 5. 测试命令与结果

### compileall
```
python -m compileall "Study/02-.../code/run_study02a.py" python/tests/test_study02a_cli.py python/tests/test_study02a_formal_executor.py
→ OK（all compile）
```

### non-slow CLI tests
```
python -m pytest python/tests/test_study02a_cli.py -q
→ 7 passed in 14.38s
```

### non-slow formal_executor tests
```
python -m pytest python/tests/test_study02a_formal_executor.py -q -m "not slow"
→ 118 passed, 14 deselected
```

注：3 个 `test_accredit_build_rejects_tampered_*` 测试在 C5 工作树（`run_study02a.py` dirty）下因 `_assert_scoped_code_clean` 检测到 `Study/02-.../code/` dirty 而 fail——这是预期的 authority guard 行为（非逻辑回归），commit 后工作树 clean 即恢复 pass（已在 `git stash` 干净树下验证 3 passed）。

### G.15（@slow）
```
python -m pytest test_g15_a_e3_final_selection_accepted_as_a_e2_predecessor -q
→ 1 passed in 11.06s
```

### sealed smoke G.16（@slow，checkpoint-forward）
```
python -m pytest test_g16_a_e3_sealed_smoke_production_equivalent -q
→ 1 passed in 28.22s
```

### git diff --check
```
git diff --check → clean（无 whitespace error）
```

> **CODEX 订正（2026-07-29）**：`git diff --check` 只检查 whitespace（trailing whitespace / tab-vs-space / merge marker），**不检查科学正确性、契约一致性、schema 兼容性**。"clean" 在这里仅意味着 diff 无空白错误，**不构成 R1 无 blocker 的证据**。3 个 blocker（A/B/C）全部在 `git diff --check clean` 的情况下存在——已由 reproducer tests 钉死。

## 6. Sealed smoke 替代范围（G.16）

**真实跑（NOT mocked）**：
- `materialize_run`（predecessor 绑定，C1 control-plane v2）
- `_ensure_a_e3_*` / `build_a_e3_*`（6 staged receipts 发布/复验）
- `build_module_selection("A-E3")`（score_fit=None → `_score_fit_from_checkpoint` checkpoint-forward）
- `resolve_a_e3_staged_selection`（9-record staged ledger chain from `_ZERO_HASH`）
- `_validate_predecessor("A-E2", trace)` + `_validate_staged_resolution_ledger`
- `_prepare_fit_inputs` + `resolve_model_factory` + `_write_outputs`（每个 fit 的 checkpoint 训练 + 输出）

**明确替代（非科学层）**：
- `_install_small_data_pilot`：数据源 shrink 到 pilot scale（rows=20, points=4, repeats=2），使真实 `_prepare_fit_inputs` + `resolve_model_factory` 链在秒级完成。**不 mock 行为**，只缩数据。
- `_mock_rebuild_authority_all_succeeded`：scheduler authority（O(N²) event replay，非科学；tamper detection 由 attack tests 覆盖）。staged driver loop 见所有 fit terminal，不 re-claim。
- `_a_e3_staged_score_fit` 注入：6 staged receipts 由 `_stage_a_e3_staged_outputs` 预发布（deterministic score_fit）。**final selection（`build_module_selection`）用 score_fit=None（checkpoint-forward）**。

## 7. 4 flags（设计 B.8/H 节的冻结决策）

C5 实现遵循 C1–C4 已冻结的 4 个 flags，无新增：

1. **predecessor staged-ledger binding**（C1）：A-E1/A-E3 都 publish staged_resolution_ledger；downstream 通过 `PredecessorTrace.staged_ledger_sha256` 绑定，`_validate_predecessor` fail-closed。
2. **resolved_baseline_route = "V"**（C1，r5 设计冻结）：A-E1 r5 baseline winner=V；A-E3 每个 `selected:F2_or_V` placeholder 解析为 V（从 manifest predecessor 段读，不 re-read）。
3. **A-E3 staged ledger 9-record canonical sequence**（C4）：`loss → stage1:F2_or_V → stage2:F2_or_V → stage1:S → stage2:S → output_form → shared_winner_retrain:S → baseline_route → final_aliases`；`baseline_route.input.predecessor_staged_ledger_sha256` 绑定 A-E1 SHA。
4. **A-E3 baseline_route = "none" for A-E2**：A-E3 staged ledger 无 `baseline_input` stage（与 A-E1 不同），所以 `_validate_predecessor("A-E2", trace)` 的 `resolved_baseline_route` 为 `"none"`——A-E2 自己从 A-E3 output_form winner 解析 baseline，不从 predecessor route 读。

## 8. 跳过项（out of scope）

- **A-E2 path 不动**：`formal-execute --module A-E2` 仍 dispatch to `run_formal_module`（legacy）；A-E2 staged driver / orchestration 不在 C5 范围。
- **A-E1 path 不变**：`formal-execute --module A-E1` 仍调 `run_a_e1_staged`。
- **不启动真实 A-E3/A-E2 formal**：sealed smoke 用 pilot 数据 + 自建 predecessor，不读真实 r5 dir。
- **不进 G3 accreditation / authorize / unseal / consume / 9d / G4**。
- **不改科学**（matrix / config / metric / penalty / rule / seed）。

## 9. 剩余风险

1. **A-E3 formal 未授权**：orchestration 代码就绪 ≠ formal 完工。真实 A-E3 formal run 需要：(a) 显式授权；(b) 真实 r5 A-E1 predecessor dir；(c) 全数据（非 pilot）；(d) O(N²) scheduler replay（未在 smoke 中跑）。sealed smoke 只证明 wiring 正确，不证明全数据可行性。
2. **scheduler authority O(N²) 未在 smoke 中跑**：`_mock_rebuild_authority_all_succeeded` 替代了真实 event replay；真实 A-E3 formal run 的 per-fit authority rebuild 性能未被 smoke 覆盖（与 A-E1 r5 同一瓶颈，r5 已证明 349 fits 可行；A-E3 266 fits 预期同理）。
3. **stage builder score_fit 注入 vs production checkpoint-forward**：smoke 的 6 staged receipts 用 deterministic score_fit（非 checkpoint-forward）；只有 final selection（`build_module_selection`）跑 checkpoint-forward。真实 formal run 的 staged receipts 也应 checkpoint-forward（`run_a_e3_staged(score_fit=None)` 时 stage builders 会调 `_score_fit_from_checkpoint`）；smoke 为速度用注入，G.14 已独立证明 publish/rebuild parity。
4. **`_assert_scoped_code_clean` 在 dirty 工作树下 fail**：commit 后 clean 即恢复（预期行为，非 bug）。

## 10. READY FOR CODEX REVIEW

C5 交付完整：CLI wiring（formal-execute + formal-staged A-E3）+ `_build_predecessor_trace` 复用 + sealed smoke（G.16, checkpoint-forward）+ G.15（A-E3 → A-E2 predecessor acceptance）+ non-slow 无回归（CLI 7 passed, formal_executor 118 passed）+ 文档（README / 00-A / 03-A）+ 本报告。compileall OK，git diff --check clean。不 commit，等 NEUwpy review。

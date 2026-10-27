# Study/02 G3 — R1 wiring（Claude 执行者棒，2026-07-18，Codex R1=REVISE 之后）

> 角色：Claude=执行者；Codex=唯一规划者/审批者。本棒**不得自签 APPROVE、未启封 test、未启动 formal run**。
> 状态：**partial implementation, awaiting Codex R2 review**（非 APPROVE；formal 未授权）。
> 分支：`claude/study02-a-20260715`。基线 `codex/long-task-20260711`（`8e56a0e`）未动。保留 R1 指定的 `b402ce6` 及此前实现提交。

## 0. 一句话结论

本棒完成并验证了 **R1§2 的 multi-seed selection evidence schema 升级**（每候选绑定完整 supporting fit 集 + `supporting_evidence_sha256`，废除"代表 checkpoint"；`selection_rule` 字段；pre-unseal 逐 fit 重算聚合并对照 trace）。**R1 的其余部分（决策分组重写含多 n 聚合、global_better/2%+CI/fixed-vs-shared 规则、阶段交错、D8 wiring、完整 smoke）尚未完成**——见 §7。A-E1 formal 仍不可启动（见 §9）。

## 1. 最终提交 SHA 与远端 SHA

| commit | 内容 |
|---|---|
| `2f45657` | **R1§2 multi-seed selection evidence schema**（本棒交付） |
| `b402ce6` | R0 报告+状态同步（R1 要求保留） |
| `5ecda89` | D6 决策分组 helper + 诊断 + 失真说明修正 |
| `73de48b` | D7 selection scoring 原语 + 共享 fit-prep |
| `cd2efb1` | 复现缺口（.gitattributes eol=lf + requirements） |

文档/报告提交：本提交。远端 = 推送后 `origin/claude/study02-a-20260715` tip。纯 Claude 成果：`git log codex/long-task-20260711..claude/study02-a-20260715`。

## 2. Changed files（本棒）

- `code/study02a/formal_contracts.py`：`_FIT_STATUS_FIELDS`(+selection_score, +failure_penalty)、`_SELECTION_RECORD_FIELDS`(v2: −checkpoint_sha256, +supporting_evidence_sha256, +seed_count, +selection_rule)、新增 `_SUPPORTING_FIT_FIELDS` 与 4 个 selection_rule 常量；`build_fit_status_record`(+selection_score/+failure_penalty 参数)；`_validate_fit_status_row`(新字段校验)；新增 `_canonical_supporting_row` + `build_candidate_supporting_evidence`（单源聚合真理）；`build_selection_trace_records`(v2，从 supporting_fits 计算 aggregate+sha，按规则标 winner)；`_validate_selection_trace_bytes`(v2 schema，按 selection_rule 校验 winner)；pre-unseal fit↔trace 交叉校验改为按候选重组 supporting 证据并逐项对照（success 未绑定 trace 候选则 fail-closed；全失败独立 fit 透明保留）。
- `python/tests/test_study02a_formal_contracts.py`、`test_study02a_formal_evidence.py`：升级到 multi-seed schema（`_trace` 经 `build_candidate_supporting_evidence` 产 v2 记录；fit_status 加 selection_score/failure_penalty；selection 候选改 supporting_fits+approved_seeds；2 个失败语义测试按新模型重述）。

**未改动**：冻结矩阵/配置内容与哈希；scheduler 的 per-fit fit_status.json 契约；Study/01；未合并 main。

## 3. D7/D8 实际数据流（本棒已实现：schema 层）

multi-seed 候选证据（每候选，跨批准 seeds 聚合）：

```
supporting_fits = [{fit_id, seed, failed, checkpoint_sha256|"", selection_score|"", failure_penalty|""}, ...每批准 seed 一条...]
  → build_candidate_supporting_evidence:
       校验 seed 集合 == 批准 seeds（缺/重/多 → fail-closed）
       aggregate_score = mean(成功→selection_score, 失败→failure_penalty)
       supporting_evidence_sha256 = sha256(canonical(seed-sorted supporting rows))
       seed_count = len(rows)
  → build_selection_trace_records:
       每候选记录 {validation_score=aggregate_score, tie_break_key, selected, supporting_evidence_sha256, seed_count, selection_rule}
       按 (aggregate, tie_sort, candidate_id) 排序；lowest_aggregate→winner=argmin；其余规则→caller 给 selected_candidate_id，pre-unseal 再按 fits 重算
  → write_selection_trace(canonical JSONL, sha-bound, no-replace)
  → publish_selection_receipt(锁/ledger/去重/不可覆盖)
pre-unseal：按 (module, decision, candidate) 重组 fit_status → 重算 supporting_evidence_sha256/aggregate/seed_count → 对照 trace（不符、缺/重/篡改 → fail-closed）
```

D7 scoring 原语（checkpoint→failure-penalized L_param，`73de48b` 已交付验证）产出每成功 fit 的 `selection_score`，是上述 supporting_fits 的来源。

## 4. 精确测试命令与结果

```
cd python && python -m pytest \
  tests/test_study02a_formal_executor.py tests/test_study02a_formal_selection.py \
  tests/test_study02a_formal_scheduler.py tests/test_study02a_formal_contracts.py \
  tests/test_study02a_formal_evidence.py tests/test_study02a_formal_runner.py \
  tests/test_study02a_formal_state.py tests/test_study02a_formal_config.py \
  tests/test_study02a_formal_data.py -q
```
→ **226 passed in 70.96s**（0 failed）。`compileall study02a/` exit 0。`git diff --check` clean。

## 5. clean-checkout 复现

本棒未改复现相关文件（`.gitattributes`/requirements 在 `cd2efb1` 已闭环）。R0 报告记录的干净 clone+autocrlf=true 验证仍成立（`verify_frozen_hashes`+`FROZEN_MATRIX_SHA256` 通过、冻结文件 LF）。

## 6. test_access_count 证据

未启动 formal run。schema 升级只动 contracts/test 代码，不涉及 test 数据。既有 sealed-test 断言（executor 冒烟 `test_access_count==0`、scheduler `_validate_success_files` 强制 0、evidence 写入 0）含在 226 passed 中。无新增 test 访问路径。

## 7. smoke / 未完成项

- **完整临时 smoke 未执行**：R1 验证门要求的 `checkpoint→per-fit score→aggregate→stage receipt→top4/selected 解析→downstream spec→final receipt` 端到端 smoke **未做**——因为阶段交错、占位符解析、deferred-spec、build_module_selection 尚未实现。无临时 smoke artifacts 产生（pytest `tmp_path` 自动清理）。
- **未完成（待 Codex R2 后续棒）**：
  1. 决策分组按 R1§3 重写：A-E1 architecture/stage2（每 route n=10）/baseline(F2-vs-V,global_better)；A-E3 loss/fixed-arch/fixed-stage2/output_form(全局,跨 core n×formal seeds)/shared-arch/shared-stage2/n_strategy(fixed-vs-shared,按 core n 等权)；A-E2 training_size(全局,2%+配对 CI)/distribution(全局,global_better+penalized L_param+distribution id tie)。retrain 行非新决策。**多 n 聚合**需把 supporting fit 的 key 从 seed 推广到 (n,seed)，并按决策类型选聚合权重（n_strategy 等权 per n）。
  2. 选择规则实现：ranking(lowest_aggregate 已在 schema 内)；global_better_rule、smallest_within_2pct_ci、fixed_vs_shared_equal_weight 需 evaluation.py 的 CI/全局优势 + 等权聚合，并在 pre-unseal 按 fits 重算校验。
  3. 阶段交错（R1§1）：stage1→不可变阶段工件(hash 入证据链)→selected_top_1..4→stage2→…→模块结束一次性发布最终 trace/receipt（不可覆盖）。
  4. D8（R1§4）：receipt-backed 占位符解析、deferred-spec 重建、A-E1→A-E3→A-E2 前驱接线。
- `_derive_decision_candidate`（`5ecda89`）仍是 R0 版（output_form/distribution/training_size 的 scoping 问题未修），`build_module_selection`/`resolve_selected_placeholders`/`reconstruct_deferred_specs` 仍 fail-closed。

## 8. 协议偏离 / skipped checks

- **无协议偏离**：L_param 与失败惩罚（10）未改；冻结矩阵/配置内容与哈希未改；test 全程 sealed。
- schema 升级（`_FIT_STATUS_FIELDS`/`_SELECTION_RECORD_FIELDS`）属于 R1 明确允许的"正式运行前升级 schema version 和合同测试"（test 未启封、无 formal artifacts）。
- skipped：完整 smoke（§7）、global_better/CI/等权规则与多 n 聚合的测试（依赖未实现的 wiring）。
- 未跑 `ruff`（环境不可用，以 pytest+compileall 为准）。

## 9. 是否具备分阶段启动 A-E1 formal 的条件

**否。** `build_module_selection`/D8 wiring 尚未实现（仍 fail-closed）。schema 已就位（multi-seed 证据契约已定并验证），但 A-E1 的 stage2/winner_retrain 依赖完整的 wiring。需 Codex R2 + 后续棒完成 §7 四项后方可分阶段启动。

## 10. 给 Codex 的请求

R2 请就以下裁决：本棒的 multi-seed schema 升级是否 APPROVE；§7.1 的多 n 聚合（supporting fit key 推广到 (n,seed)，n_strategy 等权 per n）是否如所述；§7.2 三条非 ranking 规则在 pre-unseal 的重算口径。确认后我将在下一棒完成 wiring + 完整 smoke。

完成并推送后停止，等待 Codex R2。不进 formal、9d 或 G4。

— Claude（执行者），2026-07-18

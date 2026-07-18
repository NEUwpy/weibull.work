# Study/02 G3 — D7 selection evidence + decision-rule engine（Claude 执行者棒，2026-07-18，Codex R2=REVISE 之后）

> 角色：Claude=执行者；Codex=唯一规划者/审批者。本棒**不得自签 APPROVE、未启封 test、未启动 formal run**。
> 状态：**partial implementation, awaiting Codex R3 review**（非 APPROVE；formal 未授权）。
> 分支：`claude/study02-a-20260715`。基线 `codex/long-task-20260711`（`8e56a0e`）未动。保留 R1 指定的此前实现提交。

## 0. 一句话结论

本棒完成并验证了 Codex R2 要求的 **selection evidence 与 decision-rule engine**：以确定性 `DecisionSpec` 为唯一权威（调用方不得传入 expected fits / approved seeds / winner / rule），v2 schema + 独立 pre-unseal 重建，4 条冻结选择规则（含两级 bootstrap CI 与逐参数点证据），`build_module_selection` 编排器（score→aggregate→rule→trace→receipt），以及覆盖 R2 全部 7 项发现与合同攻击清单的测试套件。**staged A-E1 执行（stage1→selected_top→stage2→baseline_input 交错）、D8（占位符解析 / deferred-spec / 前驱链）与完整临时 smoke 明确不在本棒范围**——见 §7。A-E1 formal 仍不可启动（见 §9）。241 formal+selection 测试全绿。

## 1. 最终提交 SHA 与远端 SHA

| commit | 内容 |
|---|---|
| `2833daa` | **R2§E 规则引擎**：`evaluate_rows_per_sample` + 两级配对 bootstrap CI（seed 520001、2000 reps、参数点聚类 + 训练 seed 二级单位、顺序无关）+ `global_better_intervals`（三 CI 判定）+ `smallest_within_2pct_ci_choice`（A-E2 训练量）+ 12 项规则单测 |
| `f933953` | **DecisionSpec 引擎**（`selection.py`）：确定性决策/候选/期望 fit/(n,seed) support/approved_seeds/rule/tie-break 派生；R1§3 决策分组修正（output_form/distribution/training_size 合并）；规则应用（winner 计算非传入）；full-context `supporting_evidence_sha256`；攻击面（缺/多/重复/错 n/错 seed、跨候选复用、期望 fit 不匹配）fail-closed + 15 项引擎测试 |
| `b80e721` | **v2 schema + 独立 pre-unseal 重建**（`formal_contracts.py`）：`_SELECTION_RECORD_FIELDS` v2（+support_count，v1 混用 schema-gate fail-closed）；receipt/bundle v2；移除不安全旧 API（caller approved_seeds / selected_candidate_id）；pre-unseal 重开冻结矩阵独立重建 DecisionSpec 并逐候选重算证据/selected 一致性；fit_id 全局唯一 + 冻结合同对应；selected 候选级（失败 fit 可属获胜候选）；contracts/evidence 测试重写为 v2 |
| `6a79f10` | **`build_module_selection` 编排器**（`formal_executor.py`）：派生 specs→逐 fit 评分（checkpoint→逐参数点 L_param，no sidecar）→规则→v2 trace+receipt；`validation_failure_penalized_l_param_points` + `_prepare_fit_inputs` 暴露 validation metadata；`score_fit` DI（测试注入，不启 formal）；2 项编排测试 |
| `f9fafc7` | **攻击套件 + mixed-rule 守卫**：trace 校验器加"同决策 selection_rule 唯一"；引擎攻击（相同 fit 跨候选哈希不同、重复 support 拒绝、global_better 回退/支配边界）；evidence v1-trace-schema 拒绝；D8 占位测试修正 |

文档/报告提交：本提交。远端 = 推送后 `origin/claude/study02-a-20260715` tip。纯 Claude 成果：`git log codex/long-task-20260711..claude/study02-a-20260715`。

## 2. Changed files（本棒）

**新增**
- `code/study02a/selection.py`：DecisionSpec 引擎（SupportKey / CandidateSpec / DecisionSpec / FitEvaluation 数据类；`build_decision_specs`、`candidate_supporting_evidence`、`build_selection_trace`、`point_evidence_sha256`；4 规则赢家选择；冻结轴→规则/tie-break 表）。
- `python/tests/test_study02a_selection_rules.py`（12）、`test_study02a_selection_engine.py`（20）。

**修改**
- `code/study02a/evaluation.py`：+`evaluate_rows_per_sample`、`paired_two_level_bootstrap_ci`（两级、顺序无关、完整 (seed,sample) 网格校验）、`global_better_intervals`、`smallest_within_2pct_ci_choice`、`_pair_candidates`/`_paired_field`。
- `code/study02a/formal_contracts.py`：v2 selection schema（`_SELECTION_RECORD_FIELDS` +support_count、`_SELECTION_TRACE_VERSION`）；receipt_version→v2、bundle_version→v2；**移除** `build_candidate_supporting_evidence`/`build_selection_trace_records`/`_canonical_supporting_row`/`_SUPPORTING_FIT_FIELDS`（迁至 selection.py，旧 caller-seed/winner API 不再存在）；`_validate_selection_trace_bytes` v2（+support_count、+同决策 rule 唯一）；pre-unseal 重写为独立 DecisionSpec 重建 + fit_id 全局唯一 + (decision/candidate/n/seed) 冻结权威对应 + selected 候选级一致性（无 any/all）；放宽 `build_fit_status_record`/`_validate_fit_status_row` 的 failed+selected（R2 #4）。
- `code/study02a/formal_executor.py`：实现 `build_module_selection`（替换 NotImplementedError 占位）+ `_score_fit_from_checkpoint` + `_n_key_of`；`validation_failure_penalized_l_param_points` + `location_of_batch`；`_PreparedFit`/`_prepare_fit_inputs` 暴露 `validation_metadata`；导入 selection 符号。
- `python/tests/test_study02a_formal_contracts.py`、`test_study02a_formal_evidence.py`、`test_study02a_formal_selection.py`、`test_study02a_formal_executor.py`：升级到 v2（contracts `_trace` 走 `build_selection_trace`；evidence 用真实冻结决策 A-E1 architecture:F2:n10 两候选 scope；selection 加 `build_module_selection` 测试；executor 占位测试改为 D8-only）。

**未改动**：冻结矩阵/配置内容与哈希；scheduler 的 per-fit fit_status.json 契约；Study/01；未合并 main。

## 3. DecisionSpec 与证据数据流

```
frozen experiment_matrix.csv (820 rows, 冻结权威) + frozen config (module_matrix_rules: 每 axis 的 rule/tie-break 文本)
  → selection.build_decision_specs(module_id, matrix_rows)            [纯函数，确定性，与 run 结果无关]
       每 axis → 冻结 rule（lowest_aggregate / global_better / smallest_within_2pct_ci / fixed_vs_shared_equal_weight）
       每候选 → 决定性 expected_fit_ids + (n,seed) support_keys + approved_seeds（来自冻结 plan，非实际行）
  → build_module_selection: 每 expected fit
       outputs/{fit_id}/checkpoint.pt → load → forward(该 fit 的 scaled validation batch) → decode →
       evaluate_rows_per_sample → (scalar mean L_param, 逐参数点 records[stable pairing sample_id/point_id/seed_id])
       → FitEvaluation(fit_id, support_key, failed, checkpoint_sha256, selection_score, failure_penalty, point_records)
       （测试用 score_fit DI 注入合成 FitEvaluation，不启 formal）
  → selection.build_selection_trace(specs, evaluations_by_fit)
       每候选 → candidate_supporting_evidence:
            校验 support 覆盖 == 候选 support_keys（缺/多/重复/错 n/错 seed → fail-closed）
            校验每 support 的 fit_id == 冻结 expected（防重贴标签 / 跨候选复用）
            aggregate = mean（或 fixed_vs_shared 的 core-n 等权）
            supporting_evidence_sha256 = sha256(canonical(module,run,decision,candidate,rule,expected_fit_ids,supporting_rows))
            （每 row 含 checkpoint_sha256——传递性钉住逐点证据；point_evidence_sha256 另绑定 checkpoint 绑定的 evidence.json）
       规则选 winner（lowest_aggregate→argmin；fixed_vs_shared→等权 argmin；smallest_within_2pct_ci；global_better→支配否则 penalized L_param 回退）—— **winner 计算，非传入**
       跨候选 fit_id 复用 → fail-closed
  → write_selection_trace(canonical v2 JSONL, sha-bound, no-replace)
  → publish_selection_receipt(v2, 锁/ledger/去重/不可覆盖)
pre-unseal：重开冻结矩阵 → 独立 build_decision_specs → 逐候选从 fit_status 重算 supporting_evidence_sha256/aggregate/support_count → 对照 trace（不符、缺/重/篡改/重贴标签/selected 不一致 → fail-closed）；fit_id 全局唯一；v1/v2 混用 schema-gate fail-closed
```

逐参数点评价证据（合同 E）：`evaluate_rows_per_sample` 产每样本 {sample_id, point_id, seed_id, legal, failure, l_param, e_beta, e_eta, e_gamma}；CI 规则（global_better 的失败率/配对 L_param/三分量 RMSE 恶化、2%+CI）在其上跑两级 bootstrap（聚类参数点 + 训练 seed 二级重采样），而非单个标量。

## 4. 精确测试命令与结果

```
cd python && python -m pytest \
  tests/test_study02a_formal_executor.py tests/test_study02a_formal_selection.py \
  tests/test_study02a_formal_scheduler.py tests/test_study02a_formal_contracts.py \
  tests/test_study02a_formal_evidence.py tests/test_study02a_formal_runner.py \
  tests/test_study02a_formal_state.py tests/test_study02a_formal_config.py \
  tests/test_study02a_formal_data.py tests/test_study02a_selection_rules.py \
  tests/test_study02a_selection_engine.py -q
```
→ **241 passed in 95.73s**（0 failed）。`compileall study02a/` exit 0。`git diff --check` clean。

## 5. clean-checkout 复现

本棒未改复现相关文件（`.gitattributes`/requirements 在 `cd2efb1` 已闭环）。R0 报告记录的干净 clone+autocrlf=true 验证仍成立。

## 6. test_access_count 证据

未启动 formal run。selection 引擎/规则/证据层只动 contracts/evaluation/selection/test 代码与冻结矩阵（只读）。`build_module_selection` 默认路径读 `outputs/{fit_id}/checkpoint.pt`（training/validation 产物）与 validation 批次（training/validation 角色），从不打开 test；测试用 `score_fit` DI 注入合成证据，无任何 fit 执行。既有 sealed-test 断言（executor 冒烟 `test_access_count==0`、scheduler `_validate_success_files` 强制 0、evidence 写入 0）含在 241 passed 中。无新增 test 访问路径。

## 7. 未完成项 / 遗留问题（待 Codex R3）

明确不在本棒范围（合同："不要做 D8、阶段交错或任何正式训练"）：

1. **Staged A-E1 执行**（R1§1 / R0§8.1）：A-E1 是两阶段搜索——stage1（具体架构）排序→临时解析 `selected_top_{1..4}`→stage2（`selected_top_*`×optimizer）→baseline_input（F2-vs-V，`global_better_rule`）。`build_module_selection` 当前对**已完成模块的具体 screening 决策一次性**发布 trace/receipt；模块内 execution↔selection 交错（不可覆盖的 trace/receipt 与 staged execution 的协调）未实现。
2. **D8**（R1§4 / R0§8.4）：`resolve_selected_placeholders`（`selected:*`→winner）、`reconstruct_deferred_specs`（A-E3/A-E2 FormalDatasetSpec）、A-E1→A-E3→A-E2 前驱链 wiring。`_validate_predecessor` 已存在；缺的是解析与 deferred-spec 重建。三处仍 `NotImplementedError`（`test_d8_placeholders_remain_fail_closed` 锁定）。
3. **派生决策的执行接线**：`baseline_input`（F2-vs-V）与 `n_strategy`（fixed-vs-shared）的规则已在冻结表声明并经引擎验证，但其候选 support 来自子决策 winner，需 staged execution 产出——本棒未伪造。
4. **完整临时 smoke**：`checkpoint→per-fit score→aggregate→stage receipt→top4/selected 解析→downstream spec→final receipt` 端到端 smoke 未执行（依赖 staged/D8）。无临时 smoke artifacts（pytest `tmp_path` 自动清理）。
5. **shared-n fit_status 表示**：`build_fit_status_record` 要求 n 为正整数；route S（DeepSets）的 `n="shared"` 决策（A-E3_fixed_shared architecture/stage2）尚无法在 fit_status 中表示为 `n="shared"`——pre-unseal 的 SupportKey 比较会检测到不一致。这是 staged/DeepSets baton 需补的点（已在本棒 DecisionSpec 中正确建模为 `SupportKey(n="shared", seed)`）。
6. **per-point 证据的 pre-unseal 重算**：`supporting_evidence_sha256` 绑定 fit_status 可复现的标量行（含 checkpoint_sha256，传递性钉住逐点证据）；逐点 `point_evidence_sha256` 作为独立 per-fit 绑定写入 checkpoint 绑定的 evidence.json，由 CI 规则在发布时消费。pre-unseal 当前从 fit_status 标量重算 trace 哈希；从 checkpoint 重算逐点哈希的完整路径留待执行器 smoke。

## 8. 协议偏离 / skipped checks

- **无协议偏离**：L_param 与失败惩罚（10）未改；冻结矩阵/配置内容与哈希未改；test 全程 sealed；冻结 bootstrap seed=520001、2000 reps、参数点聚类 + 训练 seed 二级重采样（协议 §5.3）严格执行。
- v2 schema 升级（trace/receipt/bundle）属"正式运行前升级 schema version"（test 未启封、无 formal artifacts）。
- skipped：完整 smoke（§7.4）、staged 执行/D8 的正常/篡改/恢复测试（依赖未实现 wiring）。
- 未跑 `ruff`（环境不可用，以 pytest+compileall 为准，与 codex 一致）。

## 9. 是否具备分阶段启动 A-E1 formal 的条件

**否。** selection evidence + decision-rule engine 已就位并验证，但 A-E1 的 stage2/winner_retrain（≈172 fit）依赖 staged execution（§7.1）与 D8（§7.2），均未实现。需 Codex R3 + 后续棒完成 §7.1/§7.2 后方可分阶段启动。

## 10. 给 Codex 的请求

R3 请就以下裁决：本棒的 selection evidence + decision-rule engine（DecisionSpec 确定性权威、v2 schema、独立 pre-unseal 重建、4 规则、build_module_selection、攻击套件）是否 APPROVE；§7.6 的 per-point 证据绑定口径（supporting_evidence_sha256 绑定 checkpoint_sha256 传递性钉住 + evidence.json 显式 point_evidence_sha256）是否如所述；output_form/n_strategy 统一用 `fixed_vs_shared_equal_weight`（core-n 等权）是否符合 module_matrix_rules 的 capacity 语义。确认后我将在下一棒完成 staged 执行 + D8 + 完整 smoke。

完成并推送后停止，等待 Codex R3。不进 formal、9d 或 G4。

— Claude（执行者），2026-07-18

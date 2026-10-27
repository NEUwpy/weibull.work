# Study/02 G3 — D7/D8 + 复现缺口（Claude 执行者棒，2026-07-17）

> 角色：Claude = 执行者；Codex = 唯一规划者与审批者。本棒**不得自签 APPROVE、未启封 test、未启动 formal run**。
> 状态：**partial implementation, awaiting Codex design review**（非 APPROVE；formal 未授权）。
> 分支：`claude/study02-a-20260715`。基线 `codex/long-task-20260711`（`8e56a0e`）未动。

## 0. 一句话结论

本棒**闭环了新环境复现缺口**（autocrlf + 依赖声明，已用干净 clone 验证），**实现并验证了 D7 selection 的 scoring 原语**（从完整性绑定 checkpoint 推理产生 failure-penalized L_param，无 sidecar），并交付了 D6 决策分组 helper + 冻结矩阵覆盖诊断。**D7/D8 的完整 wiring 未完成**——其剩余部分依赖 Codex 对若干规划级设计点的确认（见 §7）。A-E1 formal 尚不具备分阶段启动条件（见 §9）。

## 1. 最终提交 SHA 与远端 SHA

实现提交（本棒，claude 分支）：

| commit | 内容 |
|---|---|
| `cd2efb1` | 复现缺口：`.gitattributes eol=lf` + Study02 `requirements.txt`（torch CPU + pin） |
| `73de48b` | D7 selection scoring 原语 + 共享 `_prepare_fit_inputs` + 正确性测试 |
| `5ecda89` | D6 `_derive_decision_candidate` + 冻结矩阵覆盖诊断 + 修正失真占位说明 |

文档/报告提交：本提交（含 00-A、03-A、relay handoff §11、本报告）。远端 = 推送后的 `origin/claude/study02-a-20260715` tip。纯 Claude 成果：`git log codex/long-task-20260711..claude/study02-a-20260715`。

## 2. Changed files

- `.gitattributes`（改 `text`→`text eol=lf`，补 `*.csv/*.sha256/*.jsonl/*.pt`）
- `Study/02-study-NN参数估计与分位点目标研究/requirements.txt`（**新增**，torch CPU + numpy/scipy/pandas pin + `--extra-index-url`）
- `Study/02-study-NN参数估计与分位点目标研究/README.md`（环境与复现入口节 + 文件表）
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/formal_executor.py`（`validation_failure_penalized_l_param`、`_decode_param_columns`、`_prepare_fit_inputs`/`_PreparedFit`、`_derive_decision_candidate`；`execute_claimed_fit` 改用共享 prep；3 个 D7/D8 占位说明修正为准确状态）
- `python/tests/test_study02a_formal_selection.py`（**新增**：decode round-trip、checkpoint→L_param 复现、矩阵覆盖诊断）
- `Study/02-study-NN参数估计与分位点目标研究/00-A-执行状态.md`、`03-A-实验计划.md`、`coworker/handoffs/2026-07-15-study02-a-claude-relay.md`（§11）

**未改动**：冻结矩阵（`experiment_matrix.csv`、820 行）、`A-g2-protocol-v1.json`、`A-g2-search-v1.json`、`A-g3-pilot-amendment-v4.json` 的批准内容与哈希；`formal_contracts.py` 的 selection 验证机器（trace/receipt/ledger/predecessor）；任何 Study/01 文件；未合并 main。

## 3. D7/D8 实际数据流（已实现部分）

**D7 scoring（已实现+验证）**，单候选单 seed 的评分：

```
outputs/{fit_id}/checkpoint.pt (完整性绑定：sha256 由 fit_status.json + evidence.json + scheduler ledger 三方绑定)
  → training.load_checkpoint(bytes) → state_dict
  → resolve_model_factory(architecture) → model.load_state_dict(state) → model.eval()
  → forward(scaled validation batch)  # 与训练同源的 _prepare_fit_inputs 准备
  → _decode_param_columns(prediction, location, scale)   # encode_targets 的精确反演
       β̂=exp(p0), η̂=scale·exp(p1), γ̂=location−scale·exp(p2)
  → 同法从 bound targets 解出真值 (β,η,γ)（encode/decode round-trip 精确）
  → evaluation.evaluate_rows(rows, failure_penalty=10.0)
  → unconditional_mean_l_param   # = 冻结 ranking 名 mean_validation_failure_penalized_l_param_across_screening_seeds 的单 (候选,seed) 值
```

合法性口径与 protocol §5.1 一致（有限、β̂>0、η̂>0、γ̂<min(x)=anchor.location、收敛）；decode 反演保证 β̂/η̂>0、γ̂<location 恒成立，故 failure 仅由非有限（exp 溢出）触发，赋惩罚 10。**不读任何 sidecar**（evidence.json 故意不存 selection signal，per review2 #2）。

**D6 决策分组（已实现+诊断）**：`_derive_decision_candidate(plan_row)` 按 fit_kind 映射到 `(decision_id, candidate_id, tie_break_key)`：search_stage1→architecture、search_stage2→stage2(arch_slot:opt)、loss_screen→loss、output_form/distribution_screen/size_screen→对应轴；historical/controlled/`*_retrain`→None。

## 4. 精确测试命令与结果

环境：Windows 11，`core.autocrlf=input`（本地），torch 2.11.0+cpu。从仓库根：

```
cd python && python -m pytest \
  tests/test_study02a_formal_executor.py \
  tests/test_study02a_formal_selection.py \
  tests/test_study02a_formal_scheduler.py \
  tests/test_study02a_formal_contracts.py \
  tests/test_study02a_formal_evidence.py \
  tests/test_study02a_formal_runner.py \
  tests/test_study02a_formal_state.py \
  tests/test_study02a_formal_config.py \
  tests/test_study02a_formal_data.py -q
```
→ **226 passed in 85.30s**（含既有强化冒烟、deferral、evidence 自洽、selection scoring round-trip、矩阵覆盖诊断）。`compileall study02a/` exit 0。`git diff --check` clean（docs 的 CRLF 警告由 autocrlf=input + 新 `.gitattributes` 在提交时规范为 LF）。

新增 selection 测试（`test_study02a_formal_selection.py`，3 项）：
1. `test_decode_param_columns_inverts_encode_targets`——向量化 decode 是 encode_targets 的精确反演且与 `decode_targets` 一致（float64）。
2. `test_validation_l_param_reproduces_from_checkpoint`——`validation_failure_penalized_l_param(checkpoint)` == 从同一 checkpoint 加载→前向→decode→evaluate_rows 的手算值（float32 线程归约噪声内）。
3. `test_derive_decision_candidate_covers_frozen_matrix`——D6 诊断，覆盖 820 行冻结矩阵的结构不变量。

## 5. clean-checkout 复现结果

模拟新机器默认 `core.autocrlf=true`：

```
git -c core.autocrlf=true clone --local --no-hardlinks . /tmp/study02_repro_clone
cd /tmp/study02_repro_clone && git checkout claude/study02-a-20260715
# autocrlf=true；冻结文件 CR 计数：
configs/A-g2-protocol-v1.json: 0   configs/A-g2-search-v1.json: 0
configs/A-g3-pilot-amendment-v4.json: 0   artifacts/pilot/G3-matrix/experiment_matrix.csv: 0
verify_frozen_hashes: OK (protocol + search)
matrix sha matches FROZEN_MATRIX_SHA256: True
```
即 `.gitattributes eol=lf` 使 autocrlf=true 的全新 checkout 工作树为 LF，`verify_frozen_hashes`/`FROZEN_MATRIX_SHA256` 无需人工改 Git 配置或手写文件即通过。临时 clone 已 `rm -rf` 清理。依赖入口：`pip install -r "Study/02-study-NN参数估计与分位点目标研究/requirements.txt"`（torch CPU 经 `--extra-index-url`）。

## 6. test_access_count 证据

- 本棒未启动 formal run，无任何 fit 执行产出。
- scoring 原语只读 `outputs/{fit_id}/checkpoint.pt`（training/validation 产物）与 validation 批次（training/validation 角色）；**从不导入或打开 test 数据**。
- 既有 formal 套件含 sealed-test 断言（executor 冒烟 `assert test_access_count == 0`；scheduler `_validate_success_files` 强制 `test_access_count==0`；evidence.json 写入 `test_access_count: 0`）。226 passed 含这些断言。
- 无任何代码路径新增 test 访问。

## 7. smoke artifacts 临时位置及清理

- 本棒**未执行独立 smoke 脚本**：scoring 的"checkpoint→L_param"链由 pytest 临时目录（`tmp_path`）内的单元测试覆盖，pytest 自动清理，无残留 artifacts。
- **完整 smoke 链（checkpoint→L_param→selection receipt→placeholder resolution→downstream spec）未执行**——因 receipt 发布/占位符解析/deferred-spec 重建的 wiring 尚未实现（见 §8）。`build_module_selection`/`resolve_selected_placeholders`/`reconstruct_deferred_specs` 仍 fail-closed（`NotImplementedError`，消息已修正为准确状态）。
- 无正式 ledger/artifacts 被污染（无 run 物化）。

## 8. 未完成项 / 遗留问题（待 Codex 设计确认）

D7/D8 完整 wiring 未实现。剩余工作及其依赖的设计决策：

1. **`build_module_selection` 的 run_module 集成**——A-E1 是两阶段搜索：stage1（具体架构）→ 排序 → 解析 `selected_top_{1..4}` → stage2（`selected_top_*`×optimizer，目前因占位被 `_is_selection_dependent` 判为 deferred）→ 排序 → baseline_input（F2-vs-V，`global_better_rule`）。这意味着 selection 与 execution 在模块内**交错**，而非"模块 fits 全完成后一次性选择"。需 Codex 确认交错执行模型（stage1 选中→临时解析→stage2→…→最终一次性发布 trace/receipt，因 `write_selection_trace`/`publish_selection_receipt` 不可覆盖）。
2. **代表 checkpoint 策略**——冻结 ranking 是"跨 screening seeds 的均值"，但 trace 每条记录只有单个 `checkpoint_sha256`，且 pre-unseal 校验要求 selected winner 的 fit_status 行 checkpoint == trace 记录 checkpoint（`formal_contracts.py:1237`）。多 seed 候选需选一个**代表 checkpoint**（如首个 screening seed）。需 Codex 裁定代表选取规则。
3. **决策分组 scoping（诊断已客观暴露）**——`_derive_decision_candidate` 在冻结矩阵上的分组：architecture/stage2/loss 正确（12/12/4 候选）；但 `output_form` 被按路由后缀拆成 10 个单候选决策、`distribution` 拆成 15 个单候选、`training_size` 按 n 拆成 5 个四候选决策。这三处（A-E3/A-E2）的合并语义是研究设计选择，需 Codex 裁定。A-E1（architecture/stage2）不受影响。
4. **D8 占位符解析 + deferred-spec 重建 + 前驱链 wiring**——`_validate_predecessor`（A-E3←A-E1、A-E2←A-E3 的验证）已存在于 contracts；缺的是 `resolve_selected_placeholders`（`selected:*`→winner）、`reconstruct_deferred_specs`（重建 A-E3/A-E2 FormalDatasetSpec）与 `run_module` 对 A-E3/A-E2 的前驱接线。

## 9. 是否具备分阶段启动 A-E1 formal 的条件

**否。** 虽然 A-E1 的 concrete 部分（historical/controlled/stage1 搜索 ≈177 fit）可由既有 `run_module` 执行，且其 scoring/decision 分组已就绪，但 A-E1 的 stage2/winner_retrain（≈172 fit）依赖 `build_module_selection` wiring（§8.1/§8.2），尚未实现。在 Codex 确认 §8 的设计点并完成 wiring + 复审前，不应启动 formal run。

## 10. 协议偏离 / skipped checks

- **无协议偏离**：冻结指标 L_param 与失败惩罚（10）未改；冻结矩阵/配置内容与哈希未改；test 全程 sealed。
- **skipped**：完整 smoke 链（§7）、`build_module_selection`/D8 的正常路径/篡改/重复/冲突/中断恢复测试（因 wiring 未实现）。
- **未跑** `ruff`（本环境不可用，以 pytest + compileall 为准，与 codex 一致）。

## 11. 给 Codex 的建议

如认可以下设计，我可在下一棒完成 wiring：（a）A-E1 模块内交错执行（stage1 选中→临时解析 `selected_top_*`→stage2→baseline_input→一次性发布）；（b）代表 checkpoint = 首 screening seed（可配置）；（c）output_form/distribution/training_size 按"同 route 前缀/同 baseline 内合并"重定 scoping。请就 §8 四点给出 APPROVE/REVISE/BLOCK。

完成并推送后停止，等待 Codex 审批。不进 formal、9d 或 G4。

— Claude（执行者），2026-07-17

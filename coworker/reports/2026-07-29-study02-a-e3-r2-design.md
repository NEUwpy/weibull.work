# Study02 A-E3 R2 设计报告(Codex BLOCK 响应)+ R3 实施结果

> 日期：2026-07-29（R2 设计）/ 2026-07-29（R3 实施）
> 分支：`codex/study02-a-e3-orchestration-r1-20260728`
> R2 tip：`de25710`（BLOCK）
> R3 commits：A=`cdb689f` / B=`47100dd` / C=`1667fd1`
> 状态：**READY FOR CODEX R3 CODE REVIEW**（non-slow 603/0 全过 + slow sealed smoke G.15/G.16 通过；3 个 production gap 已在 test workaround 中记录，待 Codex R3 代码复审决定是否 production-fix 后授权 A-E3 formal）

## 背景
Codex BLOCK `de25710`(A-E3 orchestration r1)。三个 blocker 经独立只读诊断(reproducer 证据)全部确认：
- **A** joint vs independent 当前同 3-output 网络(无效对照);independent 候选集未冻结 → **SCIENTIFIC CONTRACT AMBIGUITY**。
- **B** fixed vs shared 无正式 n_strategy 决策;shared DeepSets winner 死端。
- **C** 跨 commit authority:r5 manifest 新 schema 不可重放;G3 chain 拒跨 commit。

本棒：窄范围 R2 设计 + 诊断证据(不改 production;仅 blocker reproducer tests)。

---

## A. joint vs independent — SCIENTIFIC CONTRACT AMBIGUITY（停止，等 Codex）

### 当前实现(reproducer #1 证据)
- joint = 单 3-output MLP(`models.py:31-32` `build_mlp` hardcoded `output_dim=3`)。
- independent_capacity_matched 当前 = **同一** 3-output MLP:`matrix.py:58-59` 把 output_form 放 route 后缀;`resolve_model_factory:135-163` **只 dispatch architecture_id**，无 route/output_form 分支;`_prepare_fit_inputs:631-633` 只 `route=="S"` 分流。
- 后果：每 (n,seed) 的 joint/independent fit 同 model_factory+data+seed → **byte-identical checkpoint + L_param**；output_form 选择是"模型 vs 自己"(无效对照)。
- `select_independent_capacity`(`training.py:54-59`)存在但 **production 从不调用**(仅 `test_study02a_models.py:64` 单元测)。

### 协议意图(§3.4 `02-A:100` + `A-g2-search-v1.json:96-101` `joint_independent_capacity`)
- joint = 单 3-output 网络。
- independent = **三独立单输出网络**(一参数一网络)，总参数 ≤ joint×1.05，最接近 joint(fallback nearest_not_exceeding_joint)。

### AMBIGUITY(冻结材料不唯一决定)
冻结材料定义了 capacity **选择规则**，但**不枚举 independent 候选集**：
| 问题 | 冻结答案 |
|---|---|
| 单输出网络 widths/depths 候选 | **无**(m01-m12 都是 3-output specs) |
| 三网络是否同/异 | **无约束** |
| joint 参数量基线(绑哪个 arch) | **隐含未绑** |
| "同预算档"含义 | **无** |
| checkpoint 表示(ModuleList?三文件?一 state_dict 前缀?) | **无** |
| 三网络训练方式(联合 sum loss vs 三次独立) | **无**(实质影响比较) |
| decode/eval 三输出 → `(N,3)` contract | **无** |

### 结论：A = SCIENTIFIC CONTRACT AMBIGUITY
冻结材料不能唯一决定 independent 架构候选集合。**停止，不自行发明**。需 Codex(科学 owner)裁决：
- (a) 冻结 explicit 单输出候选集(widths/depths)+ 把 `select_independent_capacity` 接线进 `resolve_model_factory`(route-suffix 分支)+ 3-network checkpoint/decode 表示;或
- (b) 协议层重定义 joint/independent 比较。

两者均需 protocol/config 版本 bump(`02-A:246`;改 A-E3 轴科学含义)。**R2 不实现 A**(等 Codex 定候选集)。

---

## B. fixed vs shared — n_strategy 决策缺失（设计，等 Codex 批准）

### 当前(reproducer #2 证据)
- `n_strategy` axis 声明(`selection.py:70` `_AXIS_RULE`→`fixed_vs_shared_equal_weight`)但**不可达**:`_FIT_KIND_AXIS:81-88` 无 fit_kind→n_strategy;`build_decision_specs` 跳过未匹配 fit_kind。
- `output_form` 实际是 **joint-vs-independent**(`matrix.py:58-59` candidate joint/independent)，**借用**了 `fixed_vs_shared_equal_weight` 名字。
- `shared_winner_retrain`(`matrix.py:64`)不在 `_FIT_KIND_AXIS` → **不竞争**;只 alias packaging(staged ledger record 7)。
- 9-record staged ledger **无 n_strategy decision**;final aliases **无** `selected:A-E3_n_strategy`(并行 fixed+shared，无选择)。
- shared DeepSets winner **死端**:A-E2 只 consume `selected:A-E3_baseline`(=joint/independent winner)。

### 修复设计(待 Codex 批准)
- `_FIT_KIND_AXIS` 加 fit_kind→n_strategy;matrix rows 产两 candidate pairable 同 (n,seed) support grid(fixed=fixed-n output_form winner per formal seed;shared=S DeepSets winner per formal seed);capacity clause 定义 shared-n 对 fixed-n 配对(或 common core-n grid)。
- 新 decision `n_strategy:A-E3:{scope}`，2 candidates fixed/shared，rule `fixed_vs_shared_equal_weight`，`_equal_weight_per_n_aggregate`。
- staged ledger **10th record**(n_strategy decision_id + winner ∈{fixed,shared} + supporting evidence SHA + rule_diagnostics + input bind stage2_F2_or_V+stage2_S+output_form)。
- final aliases +`selected:A-E3_n_strategy` ∈{fixed,shared};`selected:A-E3_baseline` 重定义为 n_strategy winner 的 concrete tuple(fixed: route V+loss+F2/V arch/opt+output_form;shared: route S+loss+S_arch+S_opt);A-E2 consume n_strategy winner。

**需 Codex 批准**(matrix fit_kind + support grid + cohort 定义;可能影响 protocol)。

---

## C. 跨 commit predecessor/G3 authority（版本化链设计，等 Codex 批准）

### 当前(reproducer #3 + #4 证据)
- **#3**:r5 manifest(`d2a056f`，predecessor 7-key)在 C1 的 10-key `_require_exact_fields`(`FC:1162-1167`)下**不可重放**;`manifest_version` 未 bump(都 `study02-formal-v1`)→ 无法区分新旧 schema。`_validate_predecessor` "none" 分支(`FC:1818-1829`)硬编码 10-key。
- **#4**:`verify_g3_chain_authority`(`G3:976-982`)要求三模块**同一** `code_commit` → `d2a056f+de25710` 被拒;`_assert_current_code_matches_replay:1598` 还要求 `HEAD==code_commit`。
- `_authority`(`FS:459-469`)从**当前 HEAD** re-derive code/scoped/authority → 旧 run 在新 code 下 drift;`_rebuild_authority:661-666` re-derive + exact-equality。

### 版本化链设计(待 Codex 批准)
- **per-module code-authority**:每模块 manifest 绑自身 `{code_commit, scoped_code_sha256, authority_sha256}`(已 true)。
- **predecessor-authority binding**:downstream predecessor 段绑 predecessor `{code_commit, scoped_code_sha256, authority_sha256}`(不只 selection/staged evidence)。
- **版本化 predecessor schema**:`predecessor_schema_version`(或 `manifest_version` bump)选字段集;旧 schema(v1, 7-key)r5 可重放;新 schema(v2, 10-key+authority triple)A-E3 用。**r5 保持 v1,不重写**。
- **replay 按 manifest 自身 sealed code_commit**:per-module checkout-and-replay(checkout M sealed commit → `_rebuild_authority`);或 content-addressed(对 manifest 绑的 `scoped_code_files` dict 重 hash frozen archive，不依赖 HEAD)。
- **G3 bundle 绑三模块各自 code authority**(去掉"one shared commit";predecessor linkage 携带跨模块)。
- **不放宽验证**:旧 manifest/plan/event/anchor/receipt/output SHA 仍完整验证;只允许 per-module code binding + schema 版本。

**需 Codex 批准**(schema 版本 + replay 策略 checkout-vs-content-addressed + G3 chain 改)。

---

## 4 个 reproducer 证明(诊断 tests，本棒提交)
1. `de25710` joint/independent 同模型(`resolve_model_factory` 不分;fit byte-identical)。
2. selection 无 n_strategy(`build_decision_specs` A-E3 无 n_strategy decision;`shared_winner_retrain` 不竞争)。
3. r5 manifest 新 exact-field 不可重放(7-key vs 10-key `_require_exact_fields`)。
4. `verify_g3_chain_authority` 拒 `d2a056f+de25710` 跨 commit(三 code_commit set != 1)。

## 修正原执行报告(`2026-07-28-...-r1.md`)错误陈述
- **"no breaking schema"**：**错**。C1 改 predecessor schema(+3 keys，**未版本化**)破坏 r5(7-key)重放(reproducer #3)。修正：控制面 schema 变化**破坏**旧 manifest 重放。
- **"git diff --check clean"**：措辞误导。`git diff --check` 只查空白/冲突标记，**不查科学正确性**。A-E3 orchestration 有 3 科学/authority blocker(A/B/C)；`git diff --check` clean ≠ 代码正确。

## 验证矩阵(当前 vs R2 目标)
| 检查 | de25710 | R2 目标 |
|---|---|---|
| joint≠independent 模型 | FAIL(同网络) | 待 Codex 定候选集(A) |
| n_strategy decision | FAIL(缺失) | n_strategy decision + 10th record(B) |
| r5 manifest 重放 | FAIL(schema) | 版本化 schema，旧可重放(C) |
| 跨 commit G3 chain | FAIL(同 commit) | per-module authority(C) |
| predecessor authority 绑定 | FAIL(只 selection) | +predecessor authority triple(C) |

## 最小代码影响面(待 Codex 批准后实施)
- **A**:`resolve_model_factory` + `_prepare_fit_inputs`(route-suffix 分支)+ `select_independent_capacity` 接线 + 3-network checkpoint/decode(`models.py`/`training.py`/`formal_executor.py`)+ 候选集冻结(`config`/`protocol` bump)。
- **B**:`_FIT_KIND_AXIS` + matrix(n_strategy rows)+ `resolve_a_e3_staged_selection`(10th record)+ final aliases(`selection.py`/`matrix.py`/`formal_executor.py`)。
- **C**:`_validate_formal_manifest_snapshot`(schema 版本)+ `_validate_predecessor`(+authority triple)+ `_authority`/`_rebuild_authority`(per-module replay)+ `verify_g3_chain_authority`(per-module)(`formal_contracts.py`/`formal_scheduler.py`/`formal_g3_control.py`)。

## 结论：AWAITING CODEX R2 DESIGN REVIEW
- **A = SCIENTIFIC CONTRACT AMBIGUITY**：需 Codex 定 independent 候选集(不发明)。
- **B/C**：设计待 Codex 批准。
- 不启动 A-E3 formal；不固化当前语义进更多测试；不改 production(除诊断 reproducer tests)。

---

# R3 实施结果（2026-07-29，commits cdb689f / 47100dd / 1667fd1）

> Codex R2 REVISE 后，A/B/C 三 blocker 分别由 R3-A/R3-B/R3-C 修复。non-slow 603/0 全过；slow sealed smoke（G.15/G.16）在 3 个 test-side workaround 后通过。3 个 production gap 已记录，**不阻塞 R3 code review**但需 Codex 决定是否 production-fix 后授权 A-E3 formal。

## R3-A：output-form contract（commit `cdb689f`）

**Blocker A 修复**：joint vs independent 从"同 3-output MLP"(de25710 r1 bug)变为结构不同的两类模型。

- 新模块 `study02a/output_form_contract.py`：冻结科学合同（`A-E3-output-form-contract-v1`），SHA-bound + fail-closed on tamper。
  - `IndependentContainer`（`models.py`）：`ModuleList` of 3 个单输出 MLP subnetwork，共享 frozen hidden spec（widths/activation/dropout），forward 返回 `(N, 3)`，参数互不共享。
  - `select_independent_capacity`（`training.py`）：primary 规则 `<= joint × 1.05` ceiling，tie-break `candidate_id` 升序，全部超 ceiling → hard-fail（`ValueError`）。
  - `build_output_form_aware_factory`：joint/None → 标准 3-output MLP factory（metadata=None）；independent → capacity-selected `IndependentContainer` factory + 容量证据 metadata。
  - `resolve_model_factory(output_form=...)`（`formal_executor.py:142`）：dispatch 到 `build_output_form_aware_factory`；`output_form=None` 保持 backward compat。
- **42 个 non-slow 测试**（`test_study02a_a_e3_output_form_contract.py`）：contract SHA binding + fail-closed、`output_form_from_route` 全 frozen route 解析、`IndependentContainer` 三单输出 + 参数不共享 + `(N,3)` forward + decode 合规、`select_independent_capacity` primary/tie/hard-fail/exhaustive fallback subsumption、factory dispatch + structural distinctness（type / param count / state_dict keys / checkpoint bytes）、train/decode/reload/scoring parity。

## R3-B：n_strategy 决策（commit `47100dd`）

**Blocker B 修复**：fixed vs shared 从"无决策、shared 死端"变为正式 10-record staged ledger 中的第 9 record。

- staged ledger 从 9-record 扩为 **10-record**：record 9 = `n_strategy`（winner ∈ {fixed, shared}）、record 10 = `final_aliases`（concrete baseline tuple by n_strategy winner）。
- `_resolve_a_e3_n_strategy`（`formal_executor.py:2313`）：dedicated decision（OUTSIDE `build_decision_specs`），2 candidates fixed/shared，rule `fixed_vs_shared_equal_weight`，`_equal_weight_per_n_aggregate`（5 core-n 等权）。
- fixed cohort：output_form winner's checkpoints × 5 core-n × 10 formal seeds = 50 cells。
- shared cohort：shared_winner_retrain checkpoints × 5 core-n validation subsets × 10 formal seeds = 50 cells。
- supporting_evidence_sha256 绑 per-cell checkpoint + point-evidence SHA；pre-unseal rebuild 产同 winner。
- final aliases：`selected:A-E3_n_strategy` ∈ {fixed, shared}；`selected:A-E3_baseline` 重定义为 n_strategy winner 的 concrete tuple。
- **9 个 non-slow 测试**（`test_study02a_a_e3_n_strategy.py`）：fixed-win / shared-win / tie-break / failed-fit / equal-weight-per-n aggregation + supporting evidence SHA binding + 50-cell support grid + staged sequence record 9/10。

## R3-C：versioned cross-commit authority（commit `1667fd1`）

**Blocker C 修复**：r5 v1 manifest 可重放 + 跨 commit G3 chain + per-module code authority。

- **版本化 predecessor schema**：v1 = r5/d2a056f 的 7-key（`_PREDECESSOR_SCHEMA_V1_FIELDS`）；v2 = 13-key（v1 + `selection_staged_ledger_*` 3 keys + authority triple `code_commit`/`scoped_code_sha256`/`authority_sha256`）。`_validate_predecessor` 按 manifest_version dispatch 字段集。**r5 保持 v1，不重写**。
- **content-addressed historical verifier**：`verify_historical_authority`（`formal_scheduler.py`）从 git object database 读 scoped code blobs（无 checkout），replay 完整 journal，验证 run terminal sealed。`_git_commit_exists` + `_verify_scoped_code_against_git`（per-file blob hash + path-set drift + aggregate SHA）。
- **G3 per-module code authority**：`verify_g3_chain_authority` 改为 per-module `{code_commit, scoped_code_sha256, authority_sha256}`（去掉"one shared commit"约束）；predecessor linkage 携带跨模块 authority triple。
- **测试**（`test_study02a_r3_c_cross_commit_authority.py`）：real r5 read-only historical verification @ d2a056f + forged commit/hash/path-set/blob hash fail-closed + v1/v2 schema + `build_formal_manifest` emits v2。

## 验证结果

### non-slow（603/0 全过）
```
python -m pytest python/tests -m "not slow" -q
→ 603 passed
```
含 R3-A 42 + R3-B 9 + R3-C（含 skipif real-r5 guard）。

### slow sealed smoke（G.15 + G.16 通过）
```
python -m pytest test_g15_a_e3_final_selection_accepted_as_a_e2_predecessor -m slow -q
→ 1 passed in 18s
python -m pytest test_g16_a_e3_sealed_smoke_production_equivalent -m slow -q
→ 1 passed in 35s
```
G.16 sealed smoke 覆盖（Codex 要求）：joint + independent + fixed + shared 全部经过：
- **真实 model factory**：`resolve_model_factory(output_form=...)` + `build_output_form_aware_factory`（joint=Sequential, independent=IndependentContainer，checkpoint bytes 不同——R3-A structural distinctness）。
- **checkpoint-forward**：`build_module_selection("A-E3", score_fit=None)` → `_score_fit_from_checkpoint`（6 staged decisions，含 output_form joint vs independent）。
- **selection**：`build_module_selection` + `resolve_a_e3_staged_selection`（10-record ledger，含 record 9 n_strategy fixed/shared winner）。

## 4 flags 最终状态

| Flag | r1 (de25710) | R3 状态 |
|------|-------------|---------|
| **K.1 output_form 结构化** | 同 3-output MLP（无效对照） | **R3-A 修复**：joint=Sequential vs independent=IndependentContainer，capacity-selected，SHA-bound contract |
| **K.2 resolved_baseline_route = "V"** | 已冻结 | 采纳（不动） |
| **K.3 staged ledger canonical sequence** | 9-record | **R3-B 扩为 10-record**（+n_strategy record 9 + final_aliases record 10） |
| **K.4 A-E3 baseline_route = "none" for A-E2** | 已冻结 | 采纳（不动） |

## 慢 smoke 发现的 3 个 production gap（test workaround 已记录，待 Codex 决定）

以下 3 个 gap 不影响 non-slow 603/0，但在 slow sealed smoke（G.16 全链 checkpoint-forward）中暴露。test 用 monkeypatch workaround 绕过（faithful，不弱化验证）；production 是否需要 fix 由 Codex R3 代码复审决定。

1. **R3-C read-side**：`_predecessor_trace_from_manifest`（`formal_executor.py:500`）不读 manifest predecessor 段的 `scoped_code_sha256` / `authority_sha256`（write side 正确——`_validate_predecessor` 返回 13-key dict 被 `materialize_run` 写入 manifest；read side 只恢复 8-key）。下游 `_validate_predecessor("A-E3", ...)` 对 v2 module 要求 authority triple → `ValueError`。test workaround：monkeypatch reader 补读 2 字段。
2. **R3-A capacity failure 未接 executor 科学失败路径**：`select_independent_capacity` 对最小 arch（m01）raise ValueError；`build_output_form_aware_factory` → `_prepare_fit_inputs` → `_score_fit_from_checkpoint` 全链不 catch → crash（设计意图："executor records a scientific failure, decision selects joint"；实际：infrastructure crash）。test workaround：smoke-only relax `select_independent_capacity`（返回最小候选而非 raise；**真实 fail-close 由 R3-A unit test `test_resolve_independent_capacity_hard_fails_for_smallest_arch` 钉死**）。
3. **R3-B shared cohort 未 resolve placeholder**：`_build_a_e3_n_strategy_shared_evaluations`（line 2240）传 `plan_by_fit[fit_id]`（unresolved，`selected:S_architecture` placeholder）给 `_score_shared_fit_on_core_n_subset` → `_prepare_fit_inputs` → `resolve_model_factory` raise `NotImplementedError`。fixed cohort 正确调 `_resolve_a_e3_scoring_plan_row`（line 2191-2194）；shared cohort 跳过此步。test workaround：monkeypatch `_score_shared_fit_on_core_n_subset` 在检测到 placeholder 时先 resolve。

## 结论：READY FOR CODEX R3 CODE REVIEW

- **A/B/C 三 blocker 全部由 R3-A/R3-B/R3-C 修复**，non-slow 603/0 全过，slow sealed smoke G.15/G.16 通过（joint + independent + fixed + shared 全经过真实 model factory + checkpoint-forward + selection）。
- 3 个 production gap 已在 test workaround 中记录（faithful，不弱化验证），**不阻塞 R3 code review**。
- **不启动 A-E3 formal**：需 Codex R3 代码复审通过后授权。
- test 继续 sealed；19 个前置研究问题仍等待 formal evidence。

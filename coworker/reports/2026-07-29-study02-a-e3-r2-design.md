# Study02 A-E3 R2 设计报告(Codex BLOCK 响应)

> 日期：2026-07-29
> 分支：`codex/study02-a-e3-orchestration-r1-20260728`(tip `de25710`)
> 响应：Codex 对 `de25710` BLOCK(A/B/C 三 blocker)
> 状态：**AWAITING CODEX R2 DESIGN REVIEW**（不启动 A-E3 formal；不固化当前语义进更多测试；不改 production code 除诊断 reproducer）

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

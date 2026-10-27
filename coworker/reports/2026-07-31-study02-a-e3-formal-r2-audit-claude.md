# A-E3 Formal R2 完成证据独立审核报告（Claude Code executor）

> 审核对象（executor 完成报告）：`coworker/reports/2026-07-31-study02-a-e3-formal-r2-111949.md`
> Run ID：`A-E3-formal-r2-20260730-111949`
> 分支：`codex/study02-formal-a-e3-r2-20260730`（HEAD `996434b2111ba328adda41d8593d7304a7a32250`）
> authority_sha256（期望）：`488baf3cdaa192e027c4a6d5304cfa8b14a4b6ad1075a9ccbd5a2ccb410fae9d`
> predecessor（期望）：A-E1 formal r5（`A-E1-formal-r5-20260727-222417`，tip `d2a056f`，route V）
> 审核性质：**只读证据审核**，不产出 verdict（APPROVE/REVISE/BLOCK 仅 Codex 可发）。未改源码/测试/产物/既有报告，未 authorize/unseal/consume，未进 A-E2。

---

## 结论摘要（recommendation，非 verdict）

**A-E3 r2 的完成证据充分、内部自洽，且 executor 完成报告对证据的描述准确。** 全部 stop-condition 触发项均为阴性：

- 身份/authority/predecessor/test 全部与期望一致，**无 drift**；authority 在当前工作树上可独立重建为 `488baf3c…`。
- 266 fits 全 terminal：`succeeded=266 / pending=0 / claimed=0 / failed=0`，`live_claim=null`。
- `test_state=sealed`、`test_access_count=0`（manifest 原值）；无 active formal worker。
- `staged_resolution_ledger` 10/10 结构、哈希链、语义序、trace 绑定、final concrete aliases 全部独立复算通过（**0 error**）。
- 13 个关键 SHA-256 全部独立复算与报告逐字一致；checkpoint/evidence 与 receipt 的绑定系统性成立（首 fit 0349 / r1 crash 点 0483 / 末 fit 0614 均绑定成功）。

**建议 Codex 进入最终 verdict 流程**；本报告不发 verdict。审核中发现 1 处措辞瑕疵与 2 处可记录的轻微观察（均非 blocker，见下）。

---

## 1. 身份 / authority / status（独立确认）

| 检查 | 期望 | 实测 | 结果 |
|---|---|---|---|
| 分支 | `codex/study02-formal-a-e3-r2-20260730` | 同 | ✅ |
| HEAD | `996434b2…a32250` | `996434b2111ba328adda41d8593d7304a7a32250` | ✅ |
| dirty paths（计划声明） | 仅 4 个 untracked coworker 文档 | 见 §7（额外出现与本次审核无关的 `.agents/skills/coworker/` 变更） | ⚠️ 见 §7 |

**只读命令 `formal-select --status`（authority 由当前代码独立重建）：**

```
python run_study02a.py formal-select --module A-E3 \
  --run-id A-E3-formal-r2-20260730-111949 \
  --artifact-root C:/weibull-runs/study02/artifacts \
  --cache-root   C:/weibull-runs/study02/cache --status
```

```json
{"authority_sha256":"488baf3cdaa192e027c4a6d5304cfa8b14a4b6ad1075a9ccbd5a2ccb410fae9d",
 "counts":{"claimed":0,"failed":0,"pending":0,"succeeded":266},
 "effective_config_sha256":"44fba47c…97449",
 "live_claim":null,
 "matrix_sha256":"fad701af…d6b1",
 "module_id":"A-E3",
 "plan_sha256":"ff7eeb55…842c",
 "run_id":"A-E3-formal-r2-20260730-111949",
 "test_access_count":0}
```

- authority 重建值 = 期望 `488baf3c…` → **当前工作树代码与 frozen config/matrix/plan 绑定一致，无 drift**（在 §7 的 `.agents/` 变更出现后再次复跑仍为同一值，证明这些变更不在 scoped_code 范围内、不影响 authority）。
- `counts` = 266/0/0/0；`live_claim=null`；`test_access_count=0`。✅
- 原始 `scheduler_state.json` 复核：`fit_states` 共 266 项全 `succeeded`，`live_claim=None`，`authority_sha256=488baf3c…`。✅

---

## 2. manifest 绑定（commit / authority / predecessor / test）

读 `manifest.json`（SHA `eeeb2390…`，见 §3）：

| 字段 | manifest 值 | 期望/交叉 | 结果 |
|---|---|---|---|
| `code_commit` | `996434b2…a32250` | = HEAD | ✅ |
| `scheduler.authority.authority_sha256` | `488baf3c…` | = 期望 authority | ✅ |
| `scheduler.authority.plan_sha256` | `ff7eeb55…` | = plan.jsonl SHA | ✅ |
| `matrix.sha256` / `effective_config.sha256` | `fad701af…` / `44fba47c…` | = status 输出 | ✅ |
| `test_state` / `test_access_count` | `sealed` / `0` | sealed, 0 | ✅ |
| `fit_count` | 266 | matrix `fit_ids` = G3-fit-0349..0614 (266) | ✅ |
| `predecessor.run_id` / `code_commit` | `A-E1-formal-r5-20260727-222417` / `d2a056f…fbb3` | tip `d2a056f` | ✅ |
| `predecessor.resolved_baseline_route` | `V` | 报告 route V | ✅ |

**predecessor 文件存在性 + SHA 与 manifest 声明逐字一致：**

| 文件（A-E1 r5 run dir 下） | manifest 声明 SHA | 实测 SHA |
|---|---|---|
| `selection_receipt.json` | `d6311059…16fd` | `d63110591bf660509ac63cb485075c6cff762ff12bcf0114eb805894868d16fd` ✅ |
| `staged_resolution_ledger.jsonl` | `828a7fc0…e5bf` | `828a7fc0e0b9c1c15381cf524a5290cf37d7cb26a478697c524529948265e5bf` ✅ |
| `selection_trace.jsonl` | `95b86bd6…3508` | `95b86bd64774867e39a71f3a563cfe600483ea9acac21c0d1238271599bf3508` ✅ |

predecessor commit `d2a056fdfe650af9f2992f8ea85f8b2daab2fbb3` 在 git 中存在（`git cat-file -t` → `commit`）。✅

> 注：predecessor 读取的是 A-E1 r5 的**已发布 selection 产物**（receipt/trace/staged_ledger），非 sealed test 数据；未触碰 test。

---

## 3. 关键 SHA-256 独立复算（13/13 全部与报告一致）

`cd <run-dir> && sha256sum <file>`：

| 文件 | 报告声明 | 实测 | |
|---|---|---|---|
| manifest.json | `eeeb2390…a662` | `eeeb2390f51ed499de3b69cf3fdcf7a11021605c59092bdaec82019d9264a662` | ✅ |
| plan.jsonl | `ff7eeb55…842c` | `ff7eeb5505522b18b507111f266fe64e933b891288645736414044806dd9842c` | ✅ |
| scheduler_state.json | `93bee9c6…a48a` | `93bee9c6cce5fc74448515850ef06df0e6961dfb99adba71260aaf75838aa48a` | ✅ |
| selection_trace.jsonl | `54500395…05fd` | `5450039508eb52be56dc0f4f72da132f0b2d1053d326129cb4ead88feb9605fd` | ✅ |
| selection_receipt.json | `d399703a…1b6f7` | `d399703ad4c7f3f3acd9ab0281bfe3699f7dae058d12cacd1f04f5641401b6f7` | ✅ |
| selection_ledger.jsonl | `f8e44edd…0044` | `f8e44eddd2cbaefccf0ad41b69296797869db3d72b98c1d4afea555836eb0044` | ✅ |
| selection_diagnostics.jsonl | `e6ef3bd9…2824` | `e6ef3bd9c3e1f72f09bb0510a7be05f0688f3ccd1e50f0045598731b7aae2824` | ✅ |
| staged_resolution_ledger.jsonl | `ba6a7118…97ac` | `ba6a7118a23d5af7b94beaf2dedf64379cc7bdfdf089911857a0539f5d0897ac` | ✅ |
| loss_selection_receipt.json | `e0547ab4…d791` | `e0547ab4347fca2d8a8f13bcb9e71d022f61511c59dccb6b5d10671c59c4d791` | ✅ |
| stage1_selection_F2_or_V_receipt.json | `a0e987ed…5109` | `a0e987ed46f7a915f5e48e3927b3d671fb6710e9c0de101a4edaadd92d835109` | ✅ |
| stage2_selection_F2_or_V_receipt.json | `dbb275c5…f32c` | `dbb275c5f186d47f3959f46657f2195e3b448dd0054ca7d46e5b8790e950f32c` | ✅ |
| stage1_selection_S_receipt.json | `44dde4e0…f0ce` | `44dde4e03838a1fbed453e70ab9bb4fcd1853e222249b26776d203474e9bf0ce` | ✅ |
| stage2_selection_S_receipt.json | `a70b7580…93d6` | `a70b7580ffeda82d0cf11344735744b670391555cea63ef9b7513852ac6893d6` | ✅ |

---

## 4. receipts / outputs / point_evidence / events 计数

| 项 | 报告声明 | 实测 | |
|---|---|---|---|
| `receipts/` 终态收据 | 266 terminal | **266，全部 `.succeeded`**（succeeded 266 / failed 0 / claimed 0 / pending 0） | ✅ |
| `outputs/` checkpoint 目录 | G3-fit-0349..0614 (266) | **266**（首 0349 … 末 0614） | ✅ |
| `selection/point_evidence/` | (256) | **256**（G3-fit-0349..0604） | ✅ |
| `events/` | — | **533** = 1 genesis + 266×2（claim+succeed，计数器 0..532） | ✅ |
| `claims/` | — | 266 条已结算 claim（奇数计数器 1,3,…,531，每 fit 一条；`live_claim=null` 无残留） | ✅ |

- genesis event `00000000-50abced9….json` 的 SHA = manifest `genesis_event_sha256=50abced9…`。✅
- 6 个 stage receipts（loss / stage1·2 F2_or_V / stage1·2 S / selection）+ 4 个 stage ledgers（stage1·2 F2_or_V / stage1·2 S）文件全部存在。✅

**关于 256 vs 266（记录为观察，非缺口）：** point_evidence 覆盖 G3-fit-0349..0604（256）；G3-fit-0605..0614（10 个）有 terminal succeeded receipt + checkpoint，但不在 `selection/point_evidence/` 内。报告自身已用「(256)」与「266 checkpoint」分别标注，未把两者混为一谈，描述准确。这 10 个 fit 属于 n_strategy / 共享重训决策侧产物（staged ledger record 7 `shared_winner_retrain` / record 9 `n_strategy`），不进入 selection point_evidence，与完成判据不冲突。

---

## 5. staged_resolution_ledger 10/10 独立验证（核心结构校验，0 error）

独立脚本（临时文件 `%TEMP%\audit_ae3_r2_staged.py`，**仅** 导入 torch-free 的 `_canonical_json_bytes` 以忠实复刻规范化，其余校验逻辑按计划自行重写；只读）对 `staged_resolution_ledger.jsonl` 逐条复算，**TOTAL ERRORS = 0**：

- 记录数 = 10；每条字段集 == 13 项 frozen 必填字段；`record_version=study02-staged-resolution-v1`；`module_id=A-E3`；`run_id` / `code_commit=996434b2…` / `effective_config_sha256=44fba47c…` 全一致。
- **语义序** 与 `_A_E3_STAGED_SEQUENCE` 逐位相等：`loss → stage1/F2_or_V → stage2/F2_or_V → stage1/S → stage2/S → output_form → shared_winner_retrain/S → baseline_route → n_strategy → final_aliases`。
- **哈希链**：record 1 `previous_record_sha256=0*64`，其后每条 = 上一条 `record_sha256`（`prev_ok=True` ×10）。
- **自洽性**（关键，证明哈希非自说自话）：每条 `record_sha256 = sha256(canonical(record 去掉 record_sha256))`、每条 `resolution_sha256 = sha256(canonical(resolution))` 均复算相等。
- **trace 绑定**：每条 `selection_trace_sha256` = 独立复算的 `selection_trace.jsonl` SHA `54500395…`。
- **final_aliases concrete**：record 10 resolution 无 `selected_top_*` 占位键；`selected:A-E3_baseline` = `{architecture:m12, loss:transformed_train_z_huber, optimizer:o3, output_form:joint, route:V}` 完全 concrete。其余 7 个 `selected:*` 终态别名（loss / arch / optimizer / n_strategy / route / S_arch / S_opt）全 concrete。
- 全部 10 条 `record_sha256` 与报告表格逐字一致；整文件 SHA = `ba6a7118…97ac`（= 报告 staged_ledger 整体 SHA）。✅

---

## 6. checkpoint / evidence 与 receipt 绑定 + evidence-schema-fix 生产验证

**绑定（spot-check 首 / r1 crash 点 / 末 fit，checkpoint.pt + evidence.json + fit_status.json 三件 SHA 均与 receipt `details.output_hashes` 一致，`state=succeeded`）：**

| fit | state | checkpoint 绑定 | evidence 绑定 |
|---|---|---|---|
| G3-fit-0349（首） | succeeded | ✅ | ✅ |
| G3-fit-0483（**r1 crash 点**，position 134，首个 independent output_form fit） | succeeded | ✅ | ✅ |
| G3-fit-0614（末） | succeeded | ✅ | ✅ |

**evidence-schema-fix（r1 在 G3-fit-0483 因 evidence 12-key 违反 frozen 11-key 而 crash；r2 修复后越过）：**

- frozen `_EVIDENCE_FIELDS`（`formal_scheduler.py:70`）= **11 键**：`evidence_version, fit_id, run_id, checkpoint_sha256, actual_epochs, best_epoch_one_based, hit_epoch_100, early_stop_reason, terminal_validation_slope, validation_curve, test_access_count` —— **无 `output_form`**。
- G3-fit-0483 的 `evidence.json` 顶层键 = 上述 11 键，`output_form` **不存在**，键数 11 → **r1 crash 点在 r2 成功 terminal，evidence-schema-fix 生产链验证通过**。与报告「修复仅删 `evidence["output_form"]` 写入、`_EVIDENCE_FIELDS`(frozen 11-key) 不变」一致。

**r1 现场**（`A-E3-formal-r1-20260729-214640` run dir 仍在 `artifacts/A-E3/` 下，仅只读可见，未恢复/未迁移）—— 报告称 r1 永久 blocked/aborted、r2 从零启动无 checkpoint 复用；本审核未进入 r1 内容比对（超界），仅确认其目录存在且未被本次审核改动。

**恢复时间线旁证**（claims 时间戳）：G3-fit-0432 `14:30` → G3-fit-0433 `16:15` 出现断档（~14:39 停电 + 15:53 同 run-id 续接），前 84 fits（0349..0432，loss_screen 12 + F2_or_V stage1/stage2 72）在停电前完成，从 position 84（G3-fit-0433）恢复 —— 与报告执行记录一致。

---

## 7. 工作树状态与无关变更（重要披露）

- **HEAD 全程 `996434b2…`，未 drift**；本次审核**未修改**任何源码/测试/产物/既有报告；未 stage/commit/切换分支。
- 计划「Known facts」声明工作树初始仅有 4 个 untracked coworker 文档、无 modified/staged。本审核**首次** `git status` 时确为该状态。
- **审核期间，工作树额外出现了与本次审核无关的 `.agents/skills/coworker/` 变更**（3 modified / 3 deleted / ~12 untracked，形如 coworker skill v2 迁移：弃用 live-loop/coworker-live.ps1，新增 mailbox/duplex-mailbox/version-resolution/incremental-review 等）。这些变更**非本次审核任何只读命令所致**，应来自并发的外部进程；按边界要求**已原样保留、未触碰**。
- 关键：这些变更全部位于 `.agents/skills/coworker/`，**不在 authority 的 scoped_code 范围**（`studies/**`、`study02/study02a/**` 等）。`git status -- Study/ python/ study02/` 为空 → **scoped 代码零改动**；且变更出现后**再次** `formal-select --status` 仍重建 authority 为 `488baf3c…` → 权威绑定不受影响。
- 提示 Codex：`.agents/skills/coworker/` 这批变更与本 A-E3 r2 审核无关，需由对应 owner 单独处理；不应影响本 run 的 verdict。

---

## 8. 未执行 / 越界的检查（含原因）

- **未运行项目自带的 A-E3 staged-ledger 全量校验器**（`formal_g3_control._resolve_a_e3_from_staged_ledger`，会从 checkpoint 重建 n_strategy provenance 并跨绑 stage receipts / predecessor manifest）。原因：该路径属 `formal-g3-accredit-build`（需 A-E2 run-id，当前不可用），且会触发较重的 checkpoint 重算与更深 predecessor 校验，超本次只读审核的最小必要范围。**替代**：§5 已用导入项目规范化函数的独立脚本完成同等的 13-字段/语义序/哈希链/record_sha+resolution_sha 自洽/trace 绑定校验（0 error），覆盖计划要求的 staged-ledger 完整性。Codex 若需更强保证可自行跑该校验器。
- **未逐 fit（266 个）重算 checkpoint↔receipt 绑定**：已 spot-check 首/r1 crash 点/末三处系统性成立，全量逐 fit 重算超最小必要。
- **未比对 selection_trace/ledger 的逐决策内部一致性**（已通过「每条 staged record 的 trace_sha = 已校验根 trace SHA」+ status authority 重建间接绑定）。
- **未读 r1 run dir 内容**（超界，仅确认其存在且未被改动）。

---

## 9. 发现（findings）

- **F1（措辞瑕疵，非 blocker）**：完成报告称 final_aliases「无 `selected:*` placeholder 残留」。实际 record 10 的 resolution **包含** 8 个 `selected:*` 键（`selected:A-E3_architecture` 等），但它们是**终态具体别名**、非占位符；真正的占位形式是 `selected_top_*`（仅存在于中间 record 2/4，final_aliases 中确为 0）。即「无 `selected_top_*` 占位」这一**实质**正确，仅「`selected:*`」措辞不够精确。不影响任何哈希/绑定/结论。
- **O1（轻微观察）**：`formal-select --status` 输出里的 `test_access_count` 在 `status_run` 中硬编码为 0；权威值以 `manifest.test_access_count=0` 为准（已独立确认 = 0）。两者一致，非差异，仅提示来源。
- **O2（轻微观察，见 §4/§7）**：point_evidence=256 而 fits=266（10 个 0605..0614 决策侧 fit 不进 point_evidence）；工作树出现无关 `.agents/skills/coworker/` 变更。均已被报告如实区分/不属本 run 范畴。

无 BLOCKER 级发现；无身份/authority/predecessor/test/fit-state 任何 drift；无 pending/claimed/failed fit。

---

## 停止

A-E3 r2 完成证据审核完毕，证据充分且自洽，executor 完成报告描述准确（仅 1 处措辞瑕疵 + 2 处轻微观察）。**等待 Codex Controller 发最终 verdict**。本审核未发 APPROVE/REVISE/BLOCK，未 authorize/unseal/consume，未进 A-E2，未触碰 sealed test。关联 [[repo-location-discrepancy]]、[[hermes-venv-launcher-torch]]。

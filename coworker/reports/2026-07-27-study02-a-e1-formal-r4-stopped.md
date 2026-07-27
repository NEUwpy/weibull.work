# A-E1 Formal R4 停止报告

> 日期：2026-07-27
> Run ID：`A-E1-formal-r4-20260727-001519`
> 状态：**blocked/aborted**（production checkpoint scoring 在 stage2 selection 命中 fail-closed，不可续跑）
> 授权 commit：`1891b0974076f499c6323316f8d2c20788531f30`
> authority SHA：`a51647ca560779d07e634da8d4a347872017f92fc6553acdb1969fb01c542276`
> 执行者 owner_id：`study02a-r4`

## 停止原因

run 在授权 commit `1891b097` 上 materialize，完成 177 个 fit（stage1 训练，route F2 的 stage1 selection 已发布）后，由 winner-retrain 阶段触发 stage2 selection（`build_a_e1_stage2_selection`）。stage2 checkpoint scoring 把**原始 plan row**（`architecture = selected_top_N` placeholder）直接传入 `_score_fit_from_checkpoint → _prepare_fit_inputs → resolve_model_factory`，命中 `resolve_model_factory` 对 `selected_top_` / `selected:` 的 fail-closed 守卫，抛 `NotImplementedError`，进程崩溃退出。

**根因（Codex 裁决措辞）**：staged placeholder 已在执行路径（training）解析，但 **production checkpoint scoring 未使用相同的权威解析上下文**。`resolve_model_factory` 的 fail-closed 是**正确守卫**，冻结 matrix 保留 placeholder 是**正确设计**，二者均不修改。这不是“D7/D8 整体未实现”，也不是“matrix 不该含 placeholder”。

完整 traceback：

```
run_a_e1_staged (formal_executor.py:2310)
 → _ensure_a_e1_stage2_selection (:2194)
 → build_a_e1_stage2_selection (:2019)
 → _score_fit_from_checkpoint (:869)
 → _prepare_fit_inputs (:503)
 → resolve_model_factory (:145)   ← raise NotImplementedError
    "architecture 'selected_top_1' requires selection-trace resolution (D7/D8, deferred)"
```

## Run 状态（停止时，只读）

| 字段 | 值 |
|---|---|
| succeeded | 177 |
| pending | 172 |
| claimed | 0 |
| failed | 0 |
| live_claim | null（无悬挂 claim，scheduler 状态一致，无需清理） |
| test_access_count | 0（test 始终 sealed） |
| authority_sha256 | a51647ca560779d07e634da8d4a347872017f92fc6553acdb1969fb01c542276（稳定，全程无 drift） |
| effective_config_sha256 | 44fba47c7af66166e1d3f11890299a8bb5c352ac1abf3447cd00cfd3acf97449 |
| matrix_sha256 | fad701af2e2084bf7ce8f678d642410af58057b4ae33029c9150e50971fdf6b1 |

## Run 产物（保留，不删除/覆盖/迁移/复用）

```
C:\weibull-runs\study02\artifacts\A-E1\A-E1-formal-r4-20260727-001519\
├── manifest.json
├── plan.jsonl
├── scheduler_state.json
├── stage1_selection_F2_{trace.jsonl, receipt.json, ledger.jsonl}
├── claims/    (177)
├── events/    (355)
├── receipts/  (177)
└── outputs/G3-fit-0000 .. G3-fit-0176/   (各 checkpoint.pt + fit_status.json + evidence.json)
```

文件 SHA-256（完整 64 位）：

| 文件 | SHA-256 |
|---|---|
| manifest.json | 2971160a44cc5818a0df32925abc83625db4c8c24f274000429b41b2369cabec |
| plan.jsonl | 6142c6c16caf200c9cf19217a484a43c06605b8fc38c8cba4beef90aaa03d45a |
| scheduler_state.json | fe6c93c878505f1af72421a8c3152dba8f1f8a490646ed774ddfa40276d7cd83 |
| stage1_selection_F2_trace.jsonl | 9143ae778b1453e18eae48a194d8d16e4996b8cbabc60afa3db1fd0671853973 |
| stage1_selection_F2_receipt.json | 508256dbfbf7886879cc8a2a2712542435ab0cdf34e3ef6e450cf4ab6d5a956e |
| stage1_selection_F2_ledger.jsonl | 8996d226dcdf8387f98f06dfad513661b25ab08947e35998620dfd541e9e91dd |

manifest 关键绑定：

- code_commit：`1891b0974076f499c6323316f8d2c20788531f30`（= 授权 SHA）
- scoped_code_sha256：`b8f2e4e25e5790713f0f3ac78c7a348b6fcaf494bba4491cec2ac99e924fc89e`
- genesis_event_sha256：`8435101bbe367748bb125916375db719790dd0afce1b5209d0f72775443be3b7`
- test_state：`sealed`；test_access_count：`0`
- last_event_sha256（scheduler_state）：`07101566d74bd7edc6e6c82c9be94fd9b6cca247a406bec02c853702eb36eadd`

已核查**不存在**任何 approval / unseal / pre_unseal / oracle / consume / formal_state / ceiling_hit_report / leakage_audit / staged_resolution_ledger / 模块级 selection_trace 等产物——run 自始至终未发生 approval、unseal 或 test 访问。

## 时间线

| 时间（UTC） | 事件 |
|---|---|
| 2026-07-26T16:15:19Z（本地 00:15） | preflight 通过；materialize run（349 fits） |
| 2026-07-26T16:16:18Z | 首个 claim；训练开始 |
| 训练期间 | stage1 fits 陆续 succeeded；route F2 stage1 selection 发布 |
| 2026-07-26T21:56Z（本地 05:56，约） | 第 177 个 fit succeeded；winner-retrain 触发 stage2 selection |
| 同上 | `build_a_e1_stage2_selection` 在 stage2 checkpoint scoring 命中 `resolve_model_factory` fail-closed，`NotImplementedError`，进程崩溃 |
| 同上 | 守卫停止，保留现场；`live_claim=null`、`test_access_count=0` |

## 后续（Codex 裁决）

- r4 永久 **blocked/aborted**；177 个 checkpoint **仅作历史诊断证据保留，不得迁移到 r5**，不得复用其 checkpoint/journal/receipt/fit 状态。
- r5 **不得**在固定 `1891b097` 的 r4 分支（`codex/study02-formal-r4-20260726`）上启动——该分支锁定 r3 archive commit，不含本次修复。应以**包含经 Codex 批准修复的新精确 commit 创建独立的 r5 稳定分支**，重新显式授权后从零启动。
- 修复方向：让所有 A-E1 production checkpoint scoring 路径使用从磁盘 verified staged trace/receipt/ledger 独立恢复的 concrete plan context，覆盖 stage2 / winner-retrain / final module selection / `rebuild_selection_point_provenance` / pre-unseal。修复分支：`codex/study02-a-e1-stage2-scoring-r1-20260727`。
- 修复后代码**不得用于恢复/评分/写入 r4**；r4 仅只读取证。
- test 始终 sealed；不进入 A-E3/A-E2、approval、unseal、consumer、9d、G4。

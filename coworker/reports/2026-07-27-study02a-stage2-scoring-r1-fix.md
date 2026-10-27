# Study02 A-E1 Stage2 Scoring 修复报告(r1)

> 日期：2026-07-27
> 修复分支：`codex/study02-a-e1-stage2-scoring-r1-20260727`（从 `1891b0974076f499c6323316f8d2c20788531f30` 新建）
> 修复对象：r4(`A-E1-formal-r4-20260727-001519`)的 stage2 checkpoint scoring 崩溃
> 状态：已实现 + 自测全绿,等 Codex 代码复审;**formal r5 仍 BLOCK**

## 根因(Codex 裁决)
production checkpoint scoring 未使用 staged resolution 的 concrete plan context——把原始 plan row(`architecture=selected_top_N`)直接送进 `_score_fit_from_checkpoint → _prepare_fit_inputs → resolve_model_factory`,命中正确 fail-closed。**不是** D7/D8 整体未实现,**不是** matrix 不该含 placeholder。`resolve_model_factory` 的 fail-closed 与冻结 matrix 保留 placeholder 均**正确不动**。

## changed files
- `formal_executor.py`(+146/−52):新增 `_resolve_a_e1_scoring_plan_row`(plan_row 唯一来源 `plan_by_fit[fit_id]`;自证 `matrix_row_sha256` 绑定 + route;按 matrix `fit_kind` 分类 recover 磁盘 verified evidence 解析 placeholder);3 个 scoring 入口改造(`build_a_e1_stage2_selection` 去 `top4`;`_derive_and_score_evaluations` 加 `study_root`/`run_id`;`_score_a_e1_winner_retrain` 去 `route_stage2` 加 `run_id`)各自先 `_validate_plan_against_matrix` + `_rebuild_authority` 再 resolve+score;caller(`build_module_selection`/`rebuild_selection_point_provenance`/`resolve_a_e1_staged_selection`/`_ensure_a_e1_stage2_selection`)同步;移除 dead code。
- `formal_g3_control.py`:caller 去 `route_stage2`、加 `run_id`。
- `test_study02a_formal_executor.py`(+新测试 + helpers):production-bound(single-fit + **full-route builder**)、provenance rebuild、publish vs rebuild 一致、attack/unit(含真实 state-dict mismatch)、签名锁;fixture 改真实 `_PLAN_FIELDS` plan;修复 `_arch_matched_fit_runner` cache key(漏 `fixed_n` 导致 winner-retrain 错维度)。

## 数据流
`_resolve_a_e1_scoring_plan_row`:plan_row 仅来自 `plan_by_fit[fit_id]` → 自证 plan↔matrix SHA 绑定 + route → 按 matrix `fit_kind` 分类(concrete→原样;stage2→`_recover_a_e1_stage1_selection` top4 → `_resolve_stage2_plan_row`;winner_retrain→recover stage1+stage2 winner → `_resolve_winner_retrain_plan_row`)→ 只读磁盘 verified evidence,无缓存,不 publish。三个 scoring 入口各自独立完成 plan↔matrix 绑定 + authority replay,不依赖外层 `run_a_e1_staged`。

## authority stub 边界(透明告知)
production-bound slow 测试中 **`_rebuild_authority` 被 stub**(返回全 succeeded `fit_states`,O(1),避免 scheduler O(N²) journal replay)——参照现有测试惯例(`_accredit_real_matrix_run` 等,`test_*.py:1074/:2136/:1326`)。**scientific checkpoint-scoring path 全程真实**:`_validate_plan_against_matrix`、`_resolve_a_e1_scoring_plan_row`、`_prepare_fit_inputs`、`resolve_model_factory`、checkpoint load、forward scoring(`validation_failure_penalized_l_param_points`)、trace/receipt/ledger publication。**未运行**真实 `run_a_e1_staged` / scheduler journal。

## 精确测试结果
- **non-slow Study02**:`498 passed / 0 failed / 1 skipped`(注:`test_concurrent_claim_has_exactly_one_live_owner` 出现 1 次瞬时 flake,单独重跑 2 次均通过;在未改动的 `formal_scheduler.py`,与本修复无关)。
- **targeted slow**(5:stage2 single-fit + winner-retrain single-fit + `rebuild_selection_point_provenance_resolves_stage2_placeholder` + `produce_same_concrete_context` + `build_a_e1_stage2_selection_full_route_production_scoring`):**5 passed**(46.53s)。
- **compileall**(`Study/02-.../code`):exit 0。
- **validate-config**:`frozen_oracle_approved`(protocol `f82e0780…`/search `abd6d17b…` 不变 == 权威)。
- **git diff --check**:clean。

## 未运行的 multi-hour smoke(透明)
- `test_run_a_e1_staged_executes_real_fits_via_scheduler`(@slow)
- `test_staged_full_chain_smoke`(@slow)
(Codex 要求:不运行既有多小时 full smoke。)

## 不变项(frozen)
`resolve_model_factory` fail-closed、冻结 matrix、plan schema(`_PLAN_FIELDS`)、selection rule、指标、scheduler journal、checkpoint 格式、test 控制面;不回写 concrete 进 plan;不加 fallback/默认值/吞异常。

## 后续
**formal r5 仍 BLOCK**。需:(1) Codex 代码复审通过;(2) 以**包含经批准修复的新精确 commit 创建独立的 r5 稳定分支**(不得在固定 `1891b097` 的 r4 分支上启动);(3) 重新显式授权,才能从零启动 r5。r4 不重启/不复用/不评分。

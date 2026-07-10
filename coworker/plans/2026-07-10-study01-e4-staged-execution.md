# Task Plan

Goal:

Replace the one-shot E4 formal batch with a staged, API-failure-tolerant execution queue. Each Hermes task must be small enough to survive GLM/Hermes instability, produce one report, update the active status handoff, and stop for Codex/user review before the next heavy step.

Known facts:

- Workspace: `D:\weibull`.
- Branch: `study01-e4-validation`.
- Active status/handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`.
- First-round smoke commit: `245bca2`.
- Codex first-round review exists at `coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md`.
- The previous one-shot batch handoff exists but is now superseded for execution:
  - `coworker/plans/2026-07-10-study01-e4-formal-batch.md`
  - `coworker/handoffs/2026-07-10-study01-e4-formal-batch-hermes.md`
- Current worktree has untracked partial E4 files:
  - `Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py`
  - `Study/01-study-MDM最小偏移量优化研究/code/run_E4_mc_generation.py`
  - `Study/artifacts/`
- These partial files must be inventoried before any new execution.

Execution queue:

## Step 1: Preflight / Inventory / Contract Freeze

Purpose: safely take over the partial batch state, inventory untracked files, confirm what exists, and freeze a revised staged route.

Allowed:

- Read and summarize untracked partial files.
- Inspect whether `Study/artifacts/` contains misplaced output that should have gone under `Study/01-study-MDM最小偏移量优化研究/artifacts/...`.
- Update `E4-validation-suite-状态交接.md` to staged mode.
- Write `coworker/reports/2026-07-10-study01-e4-step1-preflight-hermes.md`.

Not allowed:

- Do not run formal E4.
- Do not delete partial files.
- Do not move partial artifacts unless the report clearly proves they are misplaced and Codex/user approves.
- Do not write Ch7.

## Step 2: E4b/E4c MC Generation Only

Purpose: generate boundary and off-grid risk curves using the exact combo lists and `R=500`.

Inputs:

- Approved Step 1 report.
- Exact E4b/E4c combo lists from the formal batch plan unless Step 1 found a blocker.

Outputs:

- `boundary_risk_curves.csv`
- `offgrid_risk_curves.csv`
- `manifest.json` and `run_log.txt` update.

Stop before analysis.

## Step 3: E4b/E4c Reference Analysis

Purpose: compute Default/L1/L2/L3/L4/L5/L6, endpoint, failure, near-optimal/regret, and cost summaries from generated risk curves.

Outputs:

- `E4b_boundary_reference.csv`
- `E4c_offgrid_reference.csv`
- `endpoint_diagnostics.csv`
- `near_optimal_diagnostics.csv`
- `cost_report.csv`

Stop before model training.

## Step 4: E4a Formal Feature Ablation

Purpose: run feature ablation using E3b-equivalent MLP config on the existing main-grid data.

Outputs:

- `E4a_feature_ablation.csv`
- E4a diagnostics and plots.

Stop before E4d.

## Step 5: E4d Selector Extrapolation Diagnostic

Purpose: if feasible, train/reproduce E3b-style selector on original main-grid data and evaluate on E4b/E4c generated risk curves.

Outputs:

- `E4d_selector_extrapolation.csv`, or
- `E4d_skip_reason.md` with timing/memory evidence.

Stop before Ch7.

## Step 6: Consolidation Report

Purpose: assemble final formal E4 report and update status for Codex review.

Outputs:

- `coworker/reports/2026-07-10-study01-e4-formal-staged-hermes.md`
- updated `summary.json`
- updated status handoff.

Boundaries for all steps:

- Do not modify Ch1-Ch6 drafts, README, `00-05`, `draft-作者备注.md`, or `E3c-E4-后续决策备忘.md`.
- Do not modify sealed E1/E2/E3a/E3b artifacts.
- Do not push.
- Do not write Ch7.
- Do not do continuous-space training under E4; that is E3c.
- Do not include true parameters, combo ids, seed, repeat_id, fold id, or candidate delta in deployable model inputs.

Report rule:

Every step writes its own report and updates the status handoff before stopping.

# Study/01 E4 — Codex Review of Step 1 Preflight

> Date: 2026-07-10  
> Reviewer: Codex  
> Report: `coworker/reports/2026-07-10-study01-e4-step1-preflight-hermes.md`  
> Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`

## Verdict: APPROVE STEP 2, WITH CLEANUP GATE

Hermes completed Step 1 correctly. It inventoried the partial untracked scripts and misplaced partial output without running heavy formal E4 work, deleting files, or modifying sealed artifacts. Step 2 may proceed as **MC generation only** after the misplaced `Study/artifacts/` directory is handled.

## Findings

1. `run_E4_mc_generation.py` is reusable for Step 2.
   - It writes to `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/` through `config.py`.
   - It uses the frozen 20 boundary combos, 14 off-grid combos, `R=500`, and the 26-point delta grid.
   - It should be the only heavy script run in Step 2.

2. `run_E4_formal_validation.py` is reusable later, but must not run in Step 2.
   - It belongs to Step 3+ analysis/model work.
   - Running it before MC generation completion would blur staged execution.

3. `Study/artifacts/` is misplaced partial output.
   - It is untracked.
   - It contains only partial boundary data, no off-grid data, and no manifest.
   - Correct E4 outputs must live under `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`.
   - Cleanup is appropriate, but deletion/move requires explicit user or Codex approval in the dispatch instruction.

## Step 2 Authorization

Approved task: run only `Study/01-study-MDM最小偏移量优化研究/code/run_E4_mc_generation.py`.

Expected Step 2 outputs:

- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/boundary_risk_curves.csv`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/offgrid_risk_curves.csv`
- any script-generated logs/manifests that belong to MC generation only

Not authorized in Step 2:

- Do not run `run_E4_formal_validation.py`.
- Do not run E4a feature ablation.
- Do not run E4d selector extrapolation.
- Do not write Ch7.
- Do not modify Ch1-Ch6, README, `00-05`, `draft-作者备注.md`, or `E3c-E4-后续决策备忘.md`.
- Do not modify sealed E1/E2/E3a/E3b artifacts.

## Cleanup Gate

Preferred cleanup: delete the misplaced untracked `Study/artifacts/` directory before Step 2.

If the dispatch explicitly says cleanup is approved, Hermes may remove `Study/artifacts/` before running Step 2 and must report the command used.

If cleanup is not explicitly approved, Hermes must not delete or move `Study/artifacts/`; it may still proceed only if it verifies the correct E4 output directory is separate and records that the misplaced directory was ignored.

## Next

Use handoff:

`coworker/handoffs/2026-07-10-study01-e4-step2-mc-generation-hermes.md`

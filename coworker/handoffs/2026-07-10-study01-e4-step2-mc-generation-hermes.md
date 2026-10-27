Role: executor
Plan: `coworker/plans/2026-07-10-study01-e4-staged-execution.md`
Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`
Codex review: `coworker/reviews/2026-07-10-study01-e4-step1-preflight-codex.md`
Report: `coworker/reports/2026-07-10-study01-e4-step2-mc-generation-hermes.md`

Follow the coworker protocol. This is Step 2 only: E4b/E4c MC generation.

Scope:

- Run only:
  `python "Study\01-study-MDM最小偏移量优化研究\code\run_E4_mc_generation.py"`
- Generate formal E4 risk curves under:
  `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`
- Stop after MC generation and write the report.

Expected outputs:

- `boundary_risk_curves.csv`
- `offgrid_risk_curves.csv`
- any generation logs/chunks/manifests produced by the MC-generation script

Preflight:

1. Read `README.md`, the Study README, the Status/Handoff file, this handoff, and the Codex review.
2. Run `git status --short`.
3. Confirm `run_E4_mc_generation.py` exists.
4. Confirm the correct output directory is `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`.
5. Check whether misplaced `Study/artifacts/` exists.

Cleanup rule:

- If the user's dispatch includes the exact sentence `Cleanup Study/artifacts approved`, delete the misplaced untracked `Study/artifacts/` directory before Step 2 and record the exact command.
- If that exact sentence is absent, do not delete or move `Study/artifacts/`. Leave it untouched, verify that the correct output directory is separate, and record that it was ignored.

Stop conditions:

- Stop if the MC-generation script would write outside `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`.
- Stop if the correct output directory already contains complete-looking final E4 files and it is unclear whether rerunning would overwrite them.
- Stop if sealed E1/E2/E3a/E3b artifacts would be touched.
- Stop if the script errors or is interrupted; preserve any chunks/logs and report exact status.
- Stop after MC generation. Do not run analysis.

Verification after run:

- Report exact command, exit code, start/end time, and elapsed time.
- Confirm row counts:
  - boundary expected: `20 combos × 500 repeats × 26 deltas = 260000` data rows plus header.
  - offgrid expected: `14 combos × 500 repeats × 26 deltas = 182000` data rows plus header.
- Confirm combo ids cover `B01`-`B20` and `O01`-`O14`.
- Confirm files are in the correct `Study/01.../artifacts/formal/E4_robustness/` path.
- Run `git status --short`.
- Confirm no Ch1-Ch6/README/00-05 files changed.

Report:

Write `coworker/reports/2026-07-10-study01-e4-step2-mc-generation-hermes.md`.

Include:

- changed files;
- cleanup action taken or explicitly skipped;
- command results;
- row counts and combo coverage;
- output paths and file sizes;
- runtime/cost summary;
- any interruptions or partial chunks;
- recommendation: `APPROVE`, `REVISE`, or `BLOCK` for Step 3 reference analysis.

Update the Status/Handoff file before stopping. Do not self-authorize Step 3.

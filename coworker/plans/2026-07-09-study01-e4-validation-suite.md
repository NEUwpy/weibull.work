# Task Plan

Goal:

Prepare the first gated Study/01 E4 validation-suite branch. Hermes should review the current Ch1-Ch6/E3b evidence chain, design a three-track E4 validation contract, run only a small smoke/pilot to prove the pipeline and artifact schema, then report back for Codex review. This first round is not a full Formal E4 run and not Ch7 manuscript writing.

Known facts:

- Workspace: `D:\weibull`.
- Project entry: `README.md`.
- Study entry: `Study/01-study-MDM最小偏移量优化研究/README.md`.
- Active status/handoff entry: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`.
- Current HEAD is `30490ce`, which synchronized Ch6 after sealed E3b and locked the existing-grid claim boundary.
- E3b sealed commit is `bedd65a`.
- E3b accepted result:
  - `Vector-MLP-L6` pooled `J1=0.547003`.
  - `L2` pooled `J1=0.632541`.
  - `L5-oracle` pooled `J1=0.571170`.
  - `L6-hindsight` pooled `J1=0.494530`.
  - seed 42/2026/3407 pooled J1: `0.547003 / 0.546133 / 0.544009`.
  - E3b contract tests: 11 passed, 0 skipped, 0 failed.
- Ch6 now supports only this claim: within the formal existing discrete grid, deployable sample-observable features contain a meaningful delta-selection signal.
- Ch6 does not prove continuous-space generalization.
- `E3c` is deferred unless the paper needs continuous-space deployment claims.
- `E4` is now being framed as a post-E3 validation suite: ablation, generalization, expanded-parameter/boundary validation.
- Existing protocol lists Formal E4 minimum checks as cross beta, cross n, cross gamma/eta, boundary parameters, failure handling, and computation cost.
- Current robustness-grid hints:
  - add `n={5,50}`;
  - add `beta={1.2,6.0}`;
  - add `gamma/eta=0.0` or near-boundary values;
  - formal E4 repeats may be `R=500`, but this first round must run far smaller smoke/pilot only.

Resumable loop protocol:

- This branch must survive context-window resets.
- The active loop state lives in `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`.
- Every executor/reviewer round must start by reading that status file, this plan, the latest report/review, and `git status --short`.
- Every executor/reviewer round must end by updating the status file with:
  - current loop stage;
  - completed work;
  - report/review path;
  - artifact paths;
  - next instruction;
  - blockers or required approvals.
- If context is running out, update the status file first, then stop.
- Do not continue automatically across review gates. Pilot -> formal E4, E4 -> E3c, and formal E4 -> Ch7 all require Codex approval.

Loop stages:

- `S0_PLAN_READY`: plan/handoff/status exist; Hermes has not completed first round.
- `S1_FIRST_ROUND_RUNNING`: Hermes is working on E4 contract + smoke/pilot.
- `S2_CODEX_REVIEW`: Hermes report exists; Codex must review.
- `S3_FORMAL_E4_AUTHORIZED`: Codex has authorized second-round formal E4 planning/execution.
- `S4_FORMAL_E4_RUNNING`: Hermes is running formal E4.
- `S5_CH7_AUTHORIZED`: Codex has accepted formal E4 and authorized Ch7 drafting.
- `S6_DONE`: E4 branch is complete enough for manuscript integration.

Boundaries:

- Allowed:
  - Read current Study/01 docs, Ch1-Ch6 drafts, E3b code, and E3b artifacts.
  - Create/update `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`.
  - Create `Study/01-study-MDM最小偏移量优化研究/code/run_E4_validation_smoke.py`.
  - Create pilot artifacts under `Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/E4_validation_smoke/`.
  - Create `coworker/reports/2026-07-09-study01-e4-validation-suite-hermes.md`.
  - Move old root-level active status/handoff/context files to `history/` only if they are clearly obsolete status files, and report the move.
  - Use small smoke/pilot data to test artifact schemas, metrics, provenance, and feasibility.
  - Propose the formal E4 contract in the report.
- Not allowed:
  - Do not run full Formal E4 in this round.
  - Do not create or update `artifacts/formal/E4_robustness/`.
  - Do not modify sealed E1/E2/E3a/E3b artifacts.
  - Do not rerun or overwrite shared formal MC data.
  - Do not modify `README.md`, `00-05`, `draft-Ch*.md`, `draft-作者备注.md`, or `E3c-E4-后续决策备忘.md`.
  - Do not write Ch7 conclusions.
  - Do not present smoke/pilot numbers as manuscript evidence.
  - Do not put true parameters, combo id, seed, or repeat id into deployable model inputs.
  - Do not silently convert continuous-space training into E4; if continuous-space training is needed, label it as E3c or a separate formal extension.

Executor autonomy:

- Choose the smallest implementation path that fits existing Study/01 patterns.
- Prefer one standalone smoke script over shared-module refactors.
- Reuse E3b helper logic where safe, but do not modify E3b outputs.
- Keep smoke computation small enough to finish quickly and make the schema reviewable.
- If a necessary formal decision is missing, stop and report the decision point instead of inventing a full experiment.

E4 validation tracks:

1. `E4a` feature ablation formalization:
   - Turn the E3b fold1/seed42 feature-ablation clue into a formal contract.
   - Candidate feature groups: full features, `n only`, scale/quantile, shape, and any minimal group justified from E3b.
   - Formal contract should specify folds, seeds, per-`n` reporting, endpoint diagnostics, near-optimal/regret, and computation cost.
2. `E4b` expanded-grid / boundary robustness:
   - Design how to test `n={5,50}`, `beta={1.2,6.0}`, `gamma/eta=0.0` or near-boundary values.
   - Specify whether the experiment evaluates Default/L1/L2, retrains E3b-style selectors, reuses any sealed model artifact, or treats missing model serialization as a blocker.
   - Report J1, failure rate, endpoint behavior, near-optimal/regret, and cost.
3. `E4c` out-of-grid / continuous-space feasibility:
   - Decide whether this should remain E4 or become E3c.
   - If continuous-space training is proposed, freeze parameter distributions, train/test split design, repeats, delta grid, failure penalty, model family, and provenance fields.
   - The first-round smoke may test feasibility only; it must not claim generalization.

Smoke/pilot expectations:

- Smoke must be small and explicitly labeled pilot.
- It may validate:
  - data generation path;
  - feature computation;
  - delta-grid loss-table schema;
  - model-input field exclusions;
  - metric aggregation fields;
  - manifest/summary/results/run-log layout;
  - report format for E4a/E4b/E4c.
- Suggested outputs under `artifacts/pilot/E4_validation_smoke/`:
  - `manifest.json`
  - `summary.json`
  - `results.csv`
  - `schema_report.json` or equivalent
  - `run_log.txt`
- Smoke may use very small repeats and a tiny subset of parameter combinations. It must state the exact scale and why it is not formal evidence.

Stop conditions:

- Stop if reading the current docs contradicts this plan.
- Stop if the smoke would require modifying formal artifacts.
- Stop if a full MDM scan or full model training is required to answer a first-round question.
- Stop if there is no clear way to separate E4 from E3c.
- Stop if model inputs would include banned true-parameter or identity fields.
- Stop if the sealed E3b selector cannot be reused and the formal contract depends on reuse; report that as a design blocker.
- Stop if the task would require writing Ch7 conclusions before E4 has been reviewed.

Verification:

- Run syntax/import checks for any new script.
- Run the smoke command and record the exact command, runtime, and exit status.
- Verify pilot artifacts live under `artifacts/pilot/E4_validation_smoke/`, not `artifacts/formal/`.
- Verify smoke manifest records pilot status, input paths, code path, git commit, dirty state, parameter subset, repeats, and output paths.
- Verify generated results have expected keys, no duplicate headers, and no leaked deployable input fields.
- Verify `git status --short` contains only the intended first-round files.
- Verify sealed E1/E2/E3a/E3b artifact files are unchanged.

Report:

- Write `coworker/reports/2026-07-09-study01-e4-validation-suite-hermes.md`.
- Include:
  - files changed;
  - commands run and exact results;
  - skipped checks with reasons;
  - current Ch7/E4 question summary;
  - proposed formal E4a contract;
  - proposed formal E4b contract;
  - proposed formal E4c or E3c decision;
  - smoke artifact list and scale;
  - smoke findings, clearly marked non-formal;
  - blockers and open decisions;
  - deviations from this plan;
  - recommendation: `APPROVE`, `REVISE`, or `BLOCK` for proceeding to a formal E4 run.
- Update `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md` before stopping:
  - set the stage to `S2_CODEX_REVIEW` if the first-round report is complete;
  - keep or set `S1_FIRST_ROUND_RUNNING` if the work is incomplete but resumable;
  - list exact next actions for the next window;
  - preserve all pilot/formal boundaries.

Codex review gate:

- Codex will review the report, diff, and pilot artifacts.
- Only after Codex approval may a second-round handoff authorize full Formal E4 or Ch7 drafting.

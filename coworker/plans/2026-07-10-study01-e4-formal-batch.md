# Task Plan

Goal:

Run the remaining Study/01 E4 validation-suite work as one gated formal batch. Hermes should first apply the Codex first-round review corrections, then execute the approved E4 formal experiments, then stop with a formal report for Codex review. This batch may produce formal E4 artifacts, but it must not write Ch7 or manuscript conclusions.

Known facts:

- Workspace: `D:\weibull`.
- Branch: `study01-e4-validation`.
- Project entry: `README.md`.
- Study entry: `Study/01-study-MDM最小偏移量优化研究/README.md`.
- Active status/handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`.
- First-round plan: `coworker/plans/2026-07-09-study01-e4-validation-suite.md`.
- First-round Hermes report: `coworker/reports/2026-07-09-study01-e4-validation-suite-hermes.md`.
- Codex first-round review: `coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md`.
- First-round smoke commit: `245bca2`.
- Current mainline commit: `ccacd35`, not `30490ce`.
- E3b sealed commit: `bedd65a`.
- E3b formal result remains existing-grid only:
  - `Vector-MLP-L6` pooled `J1=0.547003`;
  - `L2` pooled `J1=0.632541`;
  - `L5-oracle` pooled `J1=0.571170`;
  - `L6-hindsight` pooled `J1=0.494530`;
  - E3b contract tests: 11 passed.

Preflight corrections from Codex review:

1. Update `E4-validation-suite-状态交接.md` so every current-stage line says `S3_FORMAL_E4_AUTHORIZED`, and update the current mainline commit to `ccacd35`.
2. Freeze the formal E4b boundary combo list before running; do not leave "12 vs full grid vs ~20 combos" ambiguous.
3. Include a real L2/per-`n` branch in E4b/E4c reference evaluation. The first smoke only implemented Default and L1-smoke.
4. Correct the manifest metrics formula text before formal output. The true `J1` formula is:
   `sqrt(mean_i[((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2])`.
5. Do not let the first-round report's trailing whitespace style propagate into new report files.
6. Keep E4b Option C as the formal reference-boundary track, and keep NN selector boundary evaluation as a separately labeled diagnostic track (`E4d_selector_extrapolation`).

Boundaries:

- Allowed:
  - Create a formal E4 script, preferably `Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py`.
  - Create formal E4 artifacts under `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`.
  - Reuse E3b code and helper logic, but do not modify sealed E3b artifacts.
  - Generate new MDM risk curves for boundary and off-grid combos.
  - Run E4a/E4b/E4c in one batch.
  - Run `E4d_selector_extrapolation` as a separately labeled diagnostic to answer NN selector generalization pressure, if feasible.
  - Add focused E4 contract tests under `python/tests/`.
  - Update the active status handoff and write the formal report.
- Not allowed:
  - Do not modify Ch1-Ch6 drafts, README, `00-05`, `draft-作者备注.md`, or `E3c-E4-后续决策备忘.md`.
  - Do not write Ch7.
  - Do not rewrite or overwrite E1/E2/E3a/E3b formal artifacts.
  - Do not move pilot artifacts into formal.
  - Do not present `E4d_selector_extrapolation` as a deployment-ready continuous-space proof.
  - Do not do continuous-space training under E4. If training on continuous/off-grid parameter distributions is needed, stop and route it to E3c.
  - Do not put `beta`, `eta`, `gamma`, `gamma_over_eta`, seed, repeat_id, combo id, fold id, or candidate `delta` into deployable vector-MLP sample inputs.

Formal E4 output directory:

`Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`

Required outputs:

- `manifest.json`
- `summary.json`
- `run_log.txt`
- `E4_acceptance_report.md`
- `E4a_feature_ablation.csv`
- `E4b_boundary_reference.csv`
- `E4c_offgrid_reference.csv`
- `E4d_selector_extrapolation.csv` if run; otherwise `E4d_skip_reason.md`
- `boundary_risk_curves.csv`
- `offgrid_risk_curves.csv`
- `endpoint_diagnostics.csv`
- `near_optimal_diagnostics.csv`
- `cost_report.csv`
- `split_report.csv`
- `plots/` with diagnostic PNGs

Formal experiment tracks:

## E4a: Feature Ablation

Purpose:

Determine whether the E3b Vector-MLP-L6 gain comes from sample-internal scale, quantile, and shape features, rather than a complex `n` lookup.

Contract:

- Data source: existing formal main-grid MC risk curves.
- Split: same deterministic 5-fold `(beta, gamma_over_eta, n)` combo holdout as E3b.
- Seeds: `42`, `2026`, `3407`.
- MLP: same as E3b where feasible:
  - `hidden_layer_sizes=(256,128,64)`
  - `max_iter=300`
  - `early_stopping=True`
  - train-fold-only feature scaling and target scaling.
- Feature groups:
  - `full`: `n, x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, CV, g1, g2`
  - `n_only`: `n`
  - `scale_quantile`: `n, x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s`
  - `shape`: `n, CV, g1, g2`
- Report:
  - pooled `J1`
  - per-`n` `J1`
  - seed mean/std
  - endpoint rate
  - near-optimal/regret at eps `1%`, `2%`, `5%`
  - training time and memory notes.

## E4b: Boundary Reference Robustness

Purpose:

Test the boundary behavior of Default/L1/L2/oracle references. This is Option C: references only. It does not deploy the E3b NN selector at boundary.

Formal boundary combo list, eta fixed at `1.0`:

| id | beta | gamma_over_eta | n | reason |
|----|------|----------------|---|--------|
| B01 | 1.2 | 0.0 | 5 | all-low boundary |
| B02 | 1.2 | 0.0 | 20 | low beta plus zero gamma |
| B03 | 1.2 | 0.5 | 5 | low beta plus small n |
| B04 | 1.2 | 0.5 | 20 | low beta mid gamma |
| B05 | 1.2 | 1.0 | 50 | low beta large n |
| B06 | 1.2 | 0.1 | 10 | low beta with main n/gamma |
| B07 | 6.0 | 0.0 | 5 | high beta zero gamma small n |
| B08 | 6.0 | 0.0 | 20 | high beta zero gamma |
| B09 | 6.0 | 0.5 | 7 | high beta main n |
| B10 | 6.0 | 0.5 | 50 | high beta large n |
| B11 | 6.0 | 1.0 | 20 | high beta high gamma |
| B12 | 6.0 | 0.1 | 10 | high beta low gamma |
| B13 | 2.5 | 0.0 | 5 | zero gamma small n |
| B14 | 2.5 | 0.0 | 50 | zero gamma large n |
| B15 | 2.5 | 0.5 | 50 | large n main beta |
| B16 | 2.5 | 1.0 | 5 | small n high gamma |
| B17 | 1.5 | 0.0 | 10 | main beta/n zero gamma |
| B18 | 4.0 | 0.0 | 20 | main beta/n zero gamma |
| B19 | 2.0 | 0.1 | 50 | main beta/gamma large n |
| B20 | 4.0 | 1.0 | 5 | main beta/gamma small n |

Contract:

- Repeats: `R=500`.
- Delta grid: same 26-point grid `0.00, 0.02, ..., 0.50`.
- New MDM calls: `20 combos × 500 repeats × 26 deltas = 260,000`.
- Evaluate:
  - Default `delta=0.1`
  - L1 boundary global best constant
  - L2 boundary per-`n` best
  - L3 by `beta`
  - L4 by `(beta,n)`
  - L5 by `(beta,gamma_over_eta,n)`
  - L6 per-sample hindsight
- Report:
  - pooled/per-combo/per-`n` `J1`
  - failure rate and non-physical rate
  - endpoint rate
  - near-optimal/regret
  - cost/runtime.

## E4c: Off-Grid Evaluation-Only Robustness

Purpose:

Evaluate reference rules on off-grid parameter combos without continuous-space model training.

Formal off-grid combo list, eta fixed at `1.0`:

| id | beta | gamma_over_eta | n |
|----|------|----------------|---|
| O01 | 1.8 | 0.3 | 12 |
| O02 | 3.3 | 0.7 | 15 |
| O03 | 5.5 | 0.2 | 30 |
| O04 | 1.3 | 0.9 | 8 |
| O05 | 4.7 | 0.4 | 25 |
| O06 | 2.2 | 0.0 | 6 |
| O07 | 5.8 | 0.8 | 45 |
| O08 | 1.6 | 0.05 | 50 |
| O09 | 3.8 | 0.95 | 5 |
| O10 | 2.8 | 0.6 | 18 |
| O11 | 4.4 | 0.15 | 35 |
| O12 | 1.25 | 0.25 | 7 |
| O13 | 5.9 | 0.75 | 20 |
| O14 | 3.6 | 0.35 | 10 |

Contract:

- Repeats: `R=500`.
- Delta grid: same 26-point grid.
- New MDM calls: `14 combos × 500 repeats × 26 deltas = 182,000`.
- Evaluate the same references as E4b.
- Do not train on these off-grid combos.
- If the need arises to train on continuous/off-grid distributions, stop and classify it as E3c.

## E4d: Selector Extrapolation Diagnostic

Purpose:

Answer the user's NN-generalization concern without changing E4b's reference-only formal boundary contract.

Contract:

- Label as diagnostic, not as the primary E4b reference result.
- Train or reproduce an E3b-style `Vector-MLP-L6` selector using only the original formal main-grid training data.
- Evaluate it on E4b boundary and E4c off-grid samples by selecting `delta` from predicted 26-point risk curves and scoring true selected loss from the E4b/E4c generated risk curves.
- Use the same deployable feature set as E3b.
- Do not include true parameters, combo ids, seed, repeat_id, fold id, or candidate `delta` in model inputs.
- If retraining is too expensive or memory-limited, write `E4d_skip_reason.md` with timing/memory evidence and continue E4a/E4b/E4c.
- Report alongside Default/L1/L2/oracle, but keep interpretation conservative:
  - supports "selector extrapolation diagnostic"
  - does not prove continuous-space deployment.

Verification:

- Run the new formal E4 script with exact command in the report.
- Run `python -m pytest python/tests/test_study01_e3b_contract.py -q`.
- Add and run focused E4 contract tests, including:
  - output directory is `artifacts/formal/E4_robustness/`;
  - manifest status is formal, not pilot;
  - exact E4b/E4c combo lists match this plan;
  - `R=500` for E4b/E4c;
  - no duplicate headers;
  - deployable model inputs exclude banned fields;
  - L2 is actually present and grouped by `n`;
  - E4d is either present as diagnostic or has a skip-reason file.
- Verify `git diff --name-only` shows no changes to Ch1-Ch6, README, `00-05`, E3c decision memo, or sealed E1/E2/E3a/E3b artifacts.

Stop conditions:

- Stop if source E3b/E1/E2 artifacts fail integrity checks.
- Stop if the exact formal combo lists cannot be honored.
- Stop if L2 cannot be implemented as per-`n`.
- Stop if any deployable input leakage is detected.
- Stop if full E4b/E4c MDM generation has repeated failures that make `R=500` impossible without changing the contract.
- Stop if continuous-space training becomes necessary; route to E3c instead.
- Stop before Ch7 writing.

Report:

Write `coworker/reports/2026-07-10-study01-e4-formal-batch-hermes.md`.

Include:

- changed files;
- commands run and exact results;
- skipped checks with reasons;
- formal combo lists;
- runtime/cost summary;
- E4a table;
- E4b table;
- E4c table;
- E4d diagnostic or skip reason;
- endpoint and near-optimal/regret diagnosis;
- failure-rate/non-physical-rate diagnosis;
- provenance summary;
- deviations from this plan;
- recommendation: `APPROVE`, `REVISE`, or `BLOCK` for moving to Ch7 handoff.

Loop update:

- Update `E4-validation-suite-状态交接.md` before stopping.
- If formal E4 completes, set stage to `S4_FORMAL_E4_RUNNING -> S2_CODEX_REVIEW` style wording only if the report is ready for Codex review; do not set `S5_CH7_AUTHORIZED`.
- Ch7 authorization is Codex-only after formal E4 review.

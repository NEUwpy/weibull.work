# Task Plan

Goal:
Run Study/01 Formal E3a as an existing-grid pilot for deployable risk-curve learning. The experiment must test whether observable sample statistics plus a candidate `delta` can predict the loss curve well enough to select a deployable `delta` that improves on Default/L1/L2 and approaches L4/L5/L6 references.

Known facts:
- Workspace: `D:\weibull`.
- Study entry: `Study/01-study-MDM最小偏移量优化研究/README.md`.
- Existing MC scan: `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/shared_data/mc_scan_raw.csv`.
- Existing MC manifest: `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/shared_data/manifest.json`.
- `mc_scan_raw.csv` contains MDM estimates for each `(beta, eta, gamma, gamma_over_eta, n, repeat_id, delta)` but does not contain raw samples or sample features.
- The manifest records sample reproducibility through `generate_sample(beta, eta, gamma, n, repeat_id, seed)` with seed namespace `study01_v1`.
- Current parameter grid: `beta={1.5,2.0,2.5,4.0,5.0}`, `eta={1.0}`, `gamma/eta={0.1,0.5,1.0}`, `n={7,10,20}`, `delta=0.00:0.02:0.50`, `R=1000`.

Boundaries:
- Allowed:
  - Reconstruct the exact formal MC samples from the manifest solely to compute observable sample-statistic features.
  - Use true parameters from `mc_scan_raw.csv` to compute offline loss labels and oracle references.
  - Train risk-curve models for `NN-RC-L4`, `NN-RC-L5`, and `NN-RC-L6`.
  - Use a lightweight MLP regressor as the main model and a lightweight tabular regressor, preferably `HistGradientBoostingRegressor`, as a sanity baseline.
  - Write experimental artifacts under `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/`.
- Not allowed:
  - Do not rerun MDM scans unless a blocking data integrity issue proves the existing scan unusable.
  - Do not include `beta`, `eta`, `gamma`, `gamma_over_eta`, combo ID, seed, or `repeat_id` as model inputs.
  - Do not construct L4/L5 group labels from all data before splitting.
  - Do not write or revise manuscript conclusions. This task is experiment-first; paper writing happens only after acceptance.
  - Do not describe `L6` as a theoretical upper bound or as the natural main target. It is a sample-level hindsight target test.

Feature contract:
- Model input is full observable sample-statistic features plus candidate `delta`:
  `n, x_(1), x_(n), range, Q1, Med, Q3, IQR, x_bar, s, CV, g1, g2, delta`.
- Reconstruct samples only to compute these features.
- Apply z-score to dimensional lifetime features using training-set statistics only:
  `x_(1), x_(n), range, Q1, Med, Q3, IQR, x_bar, s`.
- Do not z-score `n`, `CV`, `g1`, `g2`, or `delta`. Do not rescale `delta`.

Label contract:
- Base per-sample label:
  `loss_i(delta) = ((beta_hat_i(delta)-beta)/beta)^2 + ((eta_hat_i(delta)-eta)/eta)^2 + ((gamma_hat_i(delta)-gamma)/eta)^2`.
- Predict raw loss directly. Do not use regret or `log1p(loss)` in the first implementation.
- For solver failures or invalid estimates, keep the point and set `loss_i(delta) = failure_penalty`.
- `failure_penalty = p99(valid_training_loss)` computed inside each fold from training data only.
- `NN-RC-L4`: supervised target is train-only mean loss by `(beta, n, delta)`.
- `NN-RC-L5`: supervised target is train-only mean loss by `(beta, gamma_over_eta, n, delta)`.
- `NN-RC-L6`: supervised target is per-sample `loss_i(delta)`.

Split contract:
- Run both:
  - `random sample split` as a sanity check.
  - `parameter-combo holdout` as the main judgment.
- For combo holdout, split by full `(beta, gamma_over_eta, n)` combination. Do not split repeats from the same combo across train/test.
- For each fold, construct scalers, failure penalties, and L4/L5 group labels using train data only.

Evaluation contract:
- The paper-relevant objective is selection quality, not predicted-loss MSE.
- For each test sample and each model, predict loss over the 26 candidate `delta` values and choose:
  `delta_hat_i = argmin_delta predicted_loss_i(delta)`.
- Report true selected performance:
  `J1 = sqrt(mean_i true_loss_i(delta_hat_i))`.
- Also report `failure_rate`, `delta_hat` distribution, pooled results, and per-`n` results.
- Compare against:
  Default `delta=0.1`, L1 global constant, L2 `n` lookup, oracle L4, oracle L5, L6 hindsight, `NN-RC-L4`, `NN-RC-L5`, `NN-RC-L6`, and the tabular baseline variants.

Expected artifacts:
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/manifest.json`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/results.csv`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/summary.json`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/model_comparison.csv`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/split_report.csv`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/delta_distribution.csv`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/E3a_acceptance_report.md`

Stop conditions:
- Stop if reconstructed sample features cannot be matched reproducibly to the manifest seed scheme.
- Stop if existing `mc_scan_raw.csv` has missing combos, duplicate rows, or row counts inconsistent with the manifest.
- Stop if implementation would require rerunning the full MDM scan.
- Stop if any model input would include true parameters, combo IDs, seed, or `repeat_id`.
- Stop if L4/L5 labels are accidentally computed before splitting.
- Stop if selected-delta evaluation uses predicted loss instead of true selected loss.

Acceptance decision:
- `APPROVE`: In parameter-combo holdout, `NN-RC-L5` or `NN-RC-L6` clearly improves pooled J1 over L2, failure rate does not materially increase, and no `n` stratum has catastrophic degradation.
- `REVISE`: Random split improves but combo holdout does not; improvement appears only for some `n`; MLP fails but the tabular baseline shows signal; or diagnostics show scaling/label issues.
- `BLOCK`: Neither split improves over L2, selected failure rate rises materially, or models collapse to extreme `delta` choices with worse true J1.

Report:
- List changed files.
- List commands run and exact results.
- Summarize data integrity checks.
- Summarize split definitions and held-out combos.
- Provide pooled and per-`n` comparison tables.
- State `APPROVE / REVISE / BLOCK` with concrete evidence.
- Note any deviations from this plan and why they were necessary.

# Task Plan

Goal:

Run Study/01 E3b as a formal follow-up to the approved E3a pilot. E3b tests whether a Research04-style heavy vector-output MLP, implemented under the Study/01 E3a contract, can improve risk-curve delta selection and explain the E3a endpoint behavior. This is an experiment and diagnostic task, not manuscript conclusion writing.

Known facts:

- Workspace: `D:\weibull`.
- Project entry: `README.md`.
- Study entry: `Study/01-study-MDM最小偏移量优化研究/README.md`.
- E3a plan: `coworker/plans/2026-07-08-study01-e3a-risk-curve-pilot.md`.
- E3a artifacts: `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/`.
- E3a was accepted as existing-grid pilot signal, not final Ch6 evidence.
- E3a combo-holdout pooled highlights:
  - `L2`: `J1=0.632541`
  - `NN-RC-L6`: `J1=0.590716`
  - `Tabular-L6`: `J1=0.560746`
  - `L5-oracle`: `J1=0.571170`
  - `L6-hindsight`: `J1=0.494530`
- E3a light scalar NN used `features + delta -> scalar loss`, `(32,16)`, `max_iter=40`.
- Research 04 used a heavier vector-output MLP style: `sample_features -> 26-dim risk curve`, roughly `(256,128,64)`, `max_iter=200/300`.
- Source formal MC data remains:
  - `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/shared_data/mc_scan_raw.csv`
  - `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/shared_data/manifest.json`
- Do not rerun the MDM scan.

Boundaries:

- Allowed:
  - Create `Study/01-study-MDM最小偏移量优化研究/code/run_E3b_vector_mlp.py`.
  - Create E3b artifacts under `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/`.
  - Copy or lightly reuse E3a helper logic inside the new E3b script.
  - Reconstruct samples from the manifest only to compute observable sample features.
  - Use true parameters only for offline labels, diagnostics, and oracle references.
  - Retrain `Tabular-L6` inside the E3b pipeline for same-fold comparability.
  - Add focused E3b contract tests if useful.
- Not allowed:
  - Do not modify or overwrite E3a script/artifacts.
  - Do not modify `shared_data`.
  - Do not rerun the full MDM scan.
  - Do not include `beta`, `eta`, `gamma`, `gamma_over_eta`, seed, combo id, or `repeat_id` in model inputs.
  - Do not update manuscript conclusions, Ch6 prose, evidence-index claims, or experiment-protocol conclusions.
  - Do not broaden to E3c continuous-space sampling.
  - Do not introduce PyTorch in this first E3b pass.

Executor autonomy:

- Choose the smallest implementation path consistent with the current repo.
- Prefer a standalone E3b script over shared-module refactors.
- Use `sklearn` and the active local Python environment that can import `pandas`, `numpy`, and `sklearn`.
- If full training is infeasible, stop and report timing/memory evidence instead of silently capping samples.

Experiment contract:

- Main split:
  - Use the same deterministic 5-fold full `(beta, gamma_over_eta, n)` combo holdout as E3a.
  - This is the main judgment.
- Auxiliary split:
  - Keep a random sample split as sanity check only.
- Vector-output MLP input:
  - `n, x_(1), x_(n), range, Q1, Med, Q3, IQR, x_bar, s, CV, g1, g2`
  - No `delta` input for vector-output MLP.
- Scalar tabular input:
  - Same sample features plus candidate `delta`.
- Feature preprocessing:
  - Train-fold-only z-score for dimensional lifetime features:
    `x_(1), x_(n), range, Q1, Med, Q3, IQR, x_bar, s`
  - Do not z-score `n`, `CV`, `g1`, `g2`, or `delta`.
- Labels:
  - Base raw loss remains:
    `((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2`
  - Do not train on regret or `log1p(loss)`.
  - For vector-output MLP, target is the 26-dim raw loss curve.
  - Use train-fold-only target scaling for vector-output MLP; inverse-transform predictions back to raw loss before selecting `delta`.
  - `Tabular-L6` trains on scalar raw loss, following the E3a scalar tabular form.
- Failure handling:
  - Keep failed/invalid points.
  - `failure_penalty = p99(valid_training_loss)` computed inside each fold from training data only.
  - Fill invalid train/test loss entries with that fold's failure penalty for labels/evaluation.
- L4/L5 vector labels:
  - Split first.
  - Construct L4/L5 group-mean 26-dim curves from train fold only.
  - L4 grouping: `(beta, n)`.
  - L5 grouping: `(beta, gamma_over_eta, n)`.
- Main models:
  - `Vector-MLP-L4`
  - `Vector-MLP-L5`
  - `Vector-MLP-L6`
  - `Tabular-L6`
- MLP baseline config:
  - `sklearn.neural_network.MLPRegressor`
  - `hidden_layer_sizes=(256,128,64)`
  - `activation='relu'`
  - `solver='adam'`
  - `alpha=1e-4`
  - `learning_rate_init=1e-3`
  - `max_iter=300`
  - `early_stopping=True`
  - `validation_fraction=0.15`
  - `n_iter_no_change=20`
  - `batch_size=256` or `512`
- Training data size:
  - Use full fold training samples for vector-output MLP.
  - Do not use the E3a `12000` sample cap.

Diagnostics:

- Required selection metrics:
  - pooled `J1`
  - per-`n` `J1`
  - failure rate
  - selected delta distribution
  - per-combo results for combo holdout
- Endpoint diagnostics:
  - `P(delta_hat=0)`
  - `P(delta_hat=0.5)`
  - `P(delta_hat in {0,0.02,0.48,0.5})`
  - endpoint rates by `n` and by held-out combo
  - endpoint selected-loss vs L2 selected-loss
  - compare endpoint behavior across `Vector-MLP-L6`, `Tabular-L6`, scalar E3a `NN-RC-L6` if referenced, and `L6-hindsight`
  - if endpoints remain common, inspect whether true curves support them or whether predicted curves collapse to boundaries
- Curve flatness / near-optimal diagnostics:
  - selected loss
  - oracle minimum loss
  - selected regret: `selected_loss - oracle_min_loss`
  - relative regret
  - near-optimal hit rate for eps `1%`, `2%`, `5%`
  - near-optimal set width/size where useful
- Feature ablation:
  - Run only for `Vector-MLP-L6`, seed `42`.
  - Groups:
    - full features
    - `n` only
    - scale/quantile: `n + x_min/x_max/range + Q1/Med/Q3/IQR + x_bar/s`
    - shape: `n + CV + g1 + g2`
  - Report pooled/per-`n` J1, endpoint rate, and near-optimal hit rate.
- Seed stability:
  - Run `Vector-MLP-L6` full features with seeds `42`, `2026`, `3407`.
  - Report mean/std J1, per-`n` mean/std, endpoint-rate mean/std, and best/worst seed.
- Diagnostic plots:
  - Produce basic PNGs for decision-making, not publication figures.
  - Include at least:
    - model J1 comparison
    - delta distribution comparison
    - endpoint rate by `n` and/or held-out combo
    - near-optimal/regret summary
    - representative predicted-vs-true risk curves if endpoint behavior remains important

Expected artifacts:

- `manifest.json`
- `summary.json`
- `model_comparison.csv`
- `vector_mlp_results.csv`
- `tabular_l6_results.csv`
- `split_report.csv`
- `endpoint_diagnostics.csv`
- `near_optimal_diagnostics.csv`
- `feature_ablation.csv`
- `seed_stability.csv`
- `E3b_acceptance_report.md`
- `sample_features.parquet` preferred, or `.csv` fallback
- `risk_curves.parquet` preferred, or `.csv` fallback
- `plots/` with basic diagnostic PNGs

Cache boundary:

- E3b cache files may contain true parameters and `repeat_id` as offline experiment keys and labels.
- The model-input matrices must exclude all banned fields.
- Do not fail only because parquet support is unavailable; fall back to CSV.

Decision guide:

- `APPROVE`:
  - `Vector-MLP-L6` full features improves combo-holdout pooled J1 over L2.
  - 3-seed mean improves over L2.
  - Failure rate does not materially increase.
  - No `n` stratum has catastrophic degradation.
  - Endpoint behavior is either limited or evidence-backed by true risk curves / near-optimal diagnostics.
- Strong NN signal:
  - `Vector-MLP-L6` is close to or better than `Tabular-L6`, e.g. within about `0.01` J1 or better.
- `REVISE`:
  - `Vector-MLP-L6` improves over E3a scalar NN but remains far behind `Tabular-L6`.
  - Random split improves but combo holdout does not.
  - Seed variance is large.
  - Endpoint behavior is common and not yet explained.
  - Diagnostics suggest feature scaling, target scaling, or training stability problems.
- `BLOCK`:
  - Heavy vector NN cannot improve over L2.
  - Selected delta materially worsens true J1 or per-`n` behavior.
  - Contract leakage is detected.
  - The implementation needs full MDM reruns or changes the formal data boundary.

Stop conditions:

- Stop if source data integrity fails.
- Stop if samples cannot be reconstructed from the manifest seed scheme.
- Stop if implementation would need to modify E3a artifacts or shared formal data.
- Stop if any model input includes banned true-parameter or identity fields.
- Stop if L4/L5 labels are computed before splitting.
- Stop if feature or target scalers use test data.
- Stop if selected-delta evaluation uses predicted loss instead of true selected raw loss.
- Stop if full-sample vector MLP training is infeasible; report timing/memory evidence and do not silently cap.

Verification:

- Run syntax/import checks for the new script.
- Run any new E3b contract tests directly with the Python environment that has project dependencies.
- Verify source row counts, combo counts, delta counts, duplicates, repeats, and non-success rate.
- Verify split report has 45 unique held-out combos and 9 combos per fold.
- Verify manifest model inputs contain no banned fields.
- Independently recompute pooled J1 from per-sample selected results and compare with `model_comparison.csv`.
- Verify E3a artifacts were not modified.

Report:

- Write `coworker/reports/2026-07-08-study01-e3b-vector-mlp-hermes.md`.
- Include:
  - changed files
  - commands run and exact results
  - skipped checks with reasons
  - data integrity summary
  - split summary
  - model comparison table
  - seed stability table
  - feature ablation table
  - endpoint diagnosis
  - near-optimal / regret diagnosis
  - plot list
  - deviations from this plan
  - recommendation: `APPROVE`, `REVISE`, or `BLOCK`
- Executor may suggest interpretation, but must not update manuscript conclusions or final Ch6 direction.

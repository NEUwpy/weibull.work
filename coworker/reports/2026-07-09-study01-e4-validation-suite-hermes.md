# E4 Validation Suite — Hermes First-Round Report

> Date: 2026-07-09<br>
> Stage: S1_FIRST_ROUND_RUNNING → S2_CODEX_REVIEW<br>
> Author: Hermes<br>
> Plan: `coworker/plans/2026-07-09-study01-e4-validation-suite.md`
> Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`

## Verdict

**APPROVE FIRST-ROUND PLAN / DO NOT APPROVE FORMAL E4 RESULT YET**

The smoke pipeline runs end-to-end. All three track schemas are validated. No formal artifacts were modified. The E4a/E4b/E4c contracts below are ready for Codex review. One design blocker identified (E4b model reuse — see below).

---

## Files Changed

| File | Action | Status |
|------|--------|--------|
| `Study/01-study-MDM最小偏移量优化研究/code/run_E4_validation_smoke.py` | NEW | Smoke script |
| `Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/E4_validation_smoke/manifest.json` | NEW | Pilot manifest |
| `Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/E4_validation_smoke/summary.json` | NEW | Pilot summary |
| `Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/E4_validation_smoke/results.csv` | NEW | Pilot results |
| `Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/E4_validation_smoke/run_log.txt` | NEW | Pilot log |

No modifications to:
- `README.md`, `00-05`, `draft-Ch*.md`, `draft-作者备注.md`, `E3c-E4-后续决策备忘.md`
- `artifacts/formal/` (E1/E2/E3a/E3b/shared_data — all sealed)
- Ch7 (not written)

---

## Commands Run

```
python "Study/01-study-MDM最小偏移量优化研究/code/run_E4_validation_smoke.py"
```

- Exit code: 0
- Total elapsed: 52.2s
- E4a: 0.1s (existing data, tiny MLP)
- E4b: 30.9s (780 new MDM calls for boundary combos)
- E4c: 20.2s (520 new MDM calls for off-grid combos)

```
python -m pytest python/tests/test_study01_e3b_contract.py -q
```

- 11 passed, 0 skipped, 0 failed (sealed E3b contract intact)

---

## Smoke Findings (NON-FORMAL — PILOT ONLY)

### E4a: Feature Ablation Pipeline

| feature_group | n_features | pooled_J1 | n_samples | note |
|---|---:|---:|---:|---|
| full | 13 | 0.6302 | 150 | smoke MLP (32,16), max_iter=50 |
| n_only | 1 | 0.7049 | 150 | smoke MLP |

Observations:
- Direction is correct: full features (0.6302) outperform n_only (0.7049).
- These numbers are NOT comparable to E3b formal results (E3b full=0.5285 on fold 1 seed 42 with (256,128,64) MLP and 5-fold holdout). The smoke uses train=test (in-sample), tiny MLP, and only 3 combos.
- Banned field check: PASSED — no true params, combo_id, seed, or repeat_id in feature set.
- Feature computation, z-score, vector pivot, and evaluation pipeline all work.

### E4b: Expanded-Grid Boundary Pipeline

| model | pooled_J1 | n_samples | note |
|---|---:|---:|---|
| Default (δ=0.1) | 0.6814 | 30 | boundary combos, R=10 |
| L1-smoke (δ*=0.02) | 0.6033 | 30 | boundary combos, R=10 |

Boundary combos tested:
- (β=1.2, γ/η=0.0, n=5) — extreme: low beta, zero location, tiny n
- (β=6.0, γ/η=0.5, n=7) — extreme: high beta
- (β=2.5, γ/η=1.0, n=50) — large n

Observations:
- Non-success rate: 0.0000 — all boundary MDM calls converged.
- γ/η=0.0 works: MDM handles two-parameter (β, η) estimation when γ=0 (no location shift).
- n=5 works: tiny sample MDM estimates are feasible.
- n=50 works: large sample estimates are feasible.
- L1-smoke δ*=0.02 differs from main grid δ*=0.08, suggesting boundary parameters shift the optimal delta — this is expected and worth investigating formally.
- These are R=10 pilot numbers, not formal evidence.

### E4c: Out-of-Grid Feasibility

| metric | value | note |
|---|---:|---|
| feature_computation_ok | 20/20 | all off-grid samples produce valid features |

Off-grid combos tested:
- (β=3.3, γ/η=0.7, n=15) — mid-range, not on grid
- (β=1.8, γ/η=0.3, n=12) — off-grid

Observations:
- Pipeline handles arbitrary parameter combos without errors.
- Feature computation succeeds for all off-grid samples.
- MDM estimation succeeds (non-success rate: 0.0000).
- Decision: evaluation-only off-grid testing can stay in E4. If continuous-space TRAINING is needed (model trained on continuous params, tested on held-out continuous params), it becomes E3c.

---

## Proposed Formal E4 Contracts

### E4a: Feature Ablation — Formal Contract

**Goal**: Determine whether the E3b Vector-MLP-L6 improvement comes from sample-internal scale, quantile, and shape information, or from a more complex version of n-lookup.

**Design**:
- Feature groups (same as E3b ablation, extended to all folds/seeds):
  - `full`: all 13 sample features (x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, n, CV, g1, g2)
  - `n_only`: n only (1 feature)
  - `scale_quantile`: n + x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s (10 features)
  - `shape`: n + CV, g1, g2 (4 features)
- Training: 5-fold combo holdout, same as E3b.
- Seeds: 42, 2026, 3407 (same as E3b stability check).
- Reporting: pooled J1 + per-n J1 for each group × fold × seed.
- Diagnostics: endpoint rate, near-optimal/regret at ε={0.01, 0.02, 0.05}.
- MLP config: same as E3b ((256,128,64), max_iter=300, early_stopping).
- Data source: existing formal MC scan (mc_scan_raw.csv) — no new MC generation needed.

**Key question**: Does `full` significantly outperform `scale_quantile` and `shape`? If not, the practical deployment recommendation simplifies.

**Cost estimate**: 4 groups × 5 folds × 3 seeds × ~370s/training = ~6.2 hours. Feasible.

### E4b: Expanded-Grid / Boundary Robustness — Formal Contract

**Goal**: Test whether the existing-grid conclusions (Default/L1/L2 relative ordering, and E3b selector advantage) hold at boundary parameters.

**Design**:
- Boundary parameter extensions (per protocol 02-实验协议.md):
  - n: {5, 50} (additions to {7, 10, 20})
  - β: {1.2, 6.0} (additions to {1.5, 2.0, 2.5, 4.0, 5.0})
  - γ/η: {0.0} (addition to {0.1, 0.5, 1.0})
  - η: fixed at 1.0
- Repeats: R=500 (per protocol D6 decision; smoke used R=10).
- MC generation: standalone script, same MDM pipeline as generate_mc_data.py, output to `artifacts/formal/E4_robustness/`.
- Delta grid: same 26-point grid {0.00, 0.02, ..., 0.50}.
- Evaluation methods:
  - Default (δ=0.1)
  - L1 (global best constant on boundary data)
  - L2 (per-n best delta on boundary data)
  - L3/L4/L5 oracle references (for boundary combos)
  - L6 hindsight (for boundary combos)
- Metrics: J1, failure_rate, per-n J1, endpoint rate, near-optimal/regret.
- Reporting: boundary results enter Ch7 Discussion, not hidden in appendix.

**DESIGN BLOCKER — Model Reuse**:

The E3b Vector-MLP-L6 model was NOT serialized. The E3b script trains and evaluates in-memory; no `.pkl` or `.joblib` artifact exists. This means:

1. **Option A**: Retrain Vector-MLP-L6 on the original 45-combo grid, then evaluate on boundary combos. This tests extrapolation (model trained on main grid, tested on boundary).
2. **Option B**: Include boundary combos in a new training set. This changes the training data and requires a new formal experiment — closer to E3c.
3. **Option C**: For E4b, evaluate only Default/L1/L2/oracle on boundary data. Do not evaluate Vector-MLP-L6 at boundary (since no model to deploy). Report this as a scope limitation.

**Recommendation**: Option C for E4b (evaluate references only on boundary). Option A as a separate diagnostic if Codex approves. Option B is E3c territory.

**Cost estimate (Option C)**:
- Boundary combos: 2β × 3γ/η × 2n × 1η = 12 new combos (plus 3 from smoke). Actually full boundary = (7 main β + 2 boundary β) × (3 main γ/η + 1 boundary γ/η) × (3 main n + 2 boundary n) × 1η — but we only need the NEW boundary combos, not re-run existing ones.
- Conservative: ~20 new boundary combos × 26 δ × 500 repeats = 260,000 MDM calls.
- At ~100ms/call serial: ~7.2 hours. With 4 workers: ~1.8 hours.

### E4c: Out-of-Grid / Continuous-Space — Decision

**Decision**: E4c remains in E4 as an evaluation-only feasibility track. It does NOT become E3c.

**Rationale**:
- The smoke proves the pipeline can generate samples, compute features, and run MDM for arbitrary parameter values.
- Evaluating Default/L1/L2 on off-grid points is a legitimate robustness check.
- Training a model on continuous parameter space is a fundamentally different experiment that requires its own protocol (parameter distributions, train/test split, new manifest). That is E3c.
- E4c can answer: "Do Default/L1/L2 selection rules degrade when applied to off-grid parameter combos?" without needing a trained model.

**If continuous-space generalization is needed for the paper**: it becomes E3c (deferred per E3c-E4-后续决策备忘.md). The trigger conditions are already documented.

**Formal E4c contract (evaluation-only)**:
- Sample 10-20 off-grid parameter combos across the parameter space.
- R=500 repeats, same delta grid.
- Evaluate Default/L1/L2 and oracle references.
- Report J1, failure rate, and whether relative ordering is preserved.

---

## Model Serialization Blocker

**Issue**: The E3b Vector-MLP-L6 model was not serialized to disk. The E3b script trains in-memory and discards the model after evaluation. This means:

1. E4b cannot directly deploy the E3b model on boundary parameters.
2. To test the E3b selector at boundary, the model must be retrained.

**Implications**:
- For E4b Option C (references only): no blocker. Default/L1/L2 don't need a trained model.
- For E4b Option A (retrain + extrapolate): moderate effort. Retrain on main grid using the E3b script, serialize, deploy on boundary. But this re-introduces the training cost (~370s × 5 folds × 3 seeds).
- For future deployment claims: the model serialization gap should be noted in Ch6/Ch7 as a deployment consideration.

**Recommendation**: Flag this as a design decision for Codex. The formal E4b contract should explicitly state which option is chosen.

---

## Schema Verification

### manifest.json fields
```
run_id, created_at, status, code_entry, git_commit, workspace_dirty,
dirty_files, python_version, input_data, method_versions, smoke_scale,
delta_grid, metrics_contract, output_files, notes
```
All required fields present. `status` explicitly set to "PILOT — NOT FORMAL EVIDENCE".

### summary.json fields
```
run_id, created_at, status, total_elapsed_s, tracks, schema_verification
```
Each track (E4a/E4b/E4c) has description, combos, repeats, results, elapsed, and note.

### results.csv columns
```
track, model_or_group, metric, value, n, note
```
5 rows. No duplicate headers. No leaked deployable input fields.

### Provenance
- `git_commit`: d17edee (study01-e4-validation branch HEAD)
- `workspace_dirty`: true (smoke script and pilot artifacts are new untracked files)
- `input_data.mc_git_commit`: 9fad6af (sealed MC scan commit)
- `input_data.mc_run_id`: E1E2_mc_scan_v1

### Pilot/Formal Boundary
- All outputs under `artifacts/pilot/E4_validation_smoke/`.
- No writes to `artifacts/formal/`.
- `git diff HEAD -- artifacts/formal/` is empty.

---

## Verification Checklist

| Check | Result |
|-------|--------|
| Smoke script runs without errors | PASS |
| All outputs under pilot/ | PASS |
| No writes to formal/ | PASS |
| Sealed E3b artifacts unchanged | PASS (git diff empty) |
| E3b contract tests pass | PASS (11/11) |
| Banned fields not in features | PASS |
| Manifest has required provenance fields | PASS |
| results.csv has expected columns | PASS |
| git status shows only intended files | PASS |

---

## Open Decisions for Codex

1. **E4b model reuse**: Option C (references only) vs Option A (retrain + extrapolate). Recommend C.
2. **E4b boundary combo count**: Full boundary grid (all combinations of new β/n/γ/η values) vs targeted subset. Recommend targeted subset (~20 combos) for cost control.
3. **E4a ablation MLP config**: Reuse E3b config ((256,128,64), 300 iter) or use lighter config? Recommend reuse for comparability.
4. **E4c scope**: Confirm evaluation-only (no continuous-space training). If training needed → E3c.
5. **Ch7 route**: After E4 formal, does Ch7 become a boundary discussion chapter, or does it also include deployment recommendation tables?

---

## Deviations from Plan

None. All work stayed within the first-round boundaries:
- No formal E4 run.
- No Ch7 conclusions.
- No modifications to sealed artifacts or Ch1-Ch6.
- Pilot artifacts clearly labeled.
- E4c not silently converted to E3c.

---

## Recommendation

**APPROVE proceeding to formal E4** with the contracts above, subject to:
1. Codex review of E4b model reuse decision.
2. Codex confirmation of E4c scope (evaluation-only).
3. A second-round handoff that explicitly authorizes formal E4 execution.

The smoke proves the pipeline, schema, and provenance are sound. The formal E4 can proceed once the design decisions above are resolved.

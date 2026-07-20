# Execution Report — Study01 RAW-input per-n specialist candidate (E3b_RAW_specialist)

**Task**: 2026-07-20 Study01 RAW 分样本量训练候选路线
**Executor**: Claude Code (executor role)
**Date**: 2026-07-20
**Status**: Completed; awaiting independent Codex verdict (APPROVE / REVISE / BLOCK). **No self-approval.**

---

## 1. Provenance

| item | value |
|---|---|
| Base commit | `6c955b6e5290c25f3fec297505da6b0991a6b7e5` (`6c955b6 merge: integrate approved Study02 pre-formal pipeline`) |
| Branch | `study01RAW` (new, from base commit, not merged to `main`) |
| Worktree | `C:\weibull-study01RAW` (sibling of main repo; main workspace `C:\weibull` left on `main`, untouched) |
| Remote branch | `origin/study01RAW` (created by push) |
| Code/data commit | `study01RAW` tip commit that adds `code/run_E3b_RAW_specialist.py`, the test, and the candidate artifacts (see `git log study01RAW`) |

**Location deviation (flagged):** the task specified project `D:\weibull` and worktree `D:\weibull-study01RAW`,
but the `D:` drive does not exist on this machine and the repository lives at `C:\weibull` at exactly the
specified base commit. I therefore branched from `6c955b6` at `C:\weibull` and placed the worktree at
`C:\weibull-study01RAW`. This satisfies the contract's intent (isolated branch, main workspace untouched).
Note `config.py:23` hardcodes `PLATFORM_ROOT = r"D:\weibull\python"` and the formal E3b contract test
hardcodes `PROJECT_ROOT = r"D:\weibull"`; both are pre-existing and unused by this candidate (all paths here
are `__file__`-relative).

## 2. Route implemented

> For `n ∈ {7, 10, 20}`, train an **independent** Vector-MLP-L6 whose only input is the
> ascending-sorted raw sample of that `n` (input dim = n); predict the 26-point L6 loss
> curve; select δ̂ = argmin predicted loss; evaluate the TRUE selected loss under J1.

This is an alternative NN training method inside Study01, branched off the E3b "train-on-features"
step. Compared with the current F13 Vector-MLP-L6 it changes **two things at once**:
1. **Representation**: raw sorted sample values (length n) instead of the 13 hand-crafted
   sample-statistic features.
2. **Training organization**: one specialist per n (12000 train samples each) instead of a
   single joint model trained on all n.

Per the task framing, any gap vs F13 **cannot be attributed to "RAW" alone** — representation and
training organization change simultaneously. Decomposing the two would require a 2×2 ablation not
run here.

## 3. Input / model contract (as built)

- One model per n ∈ {7,10,20}; input = ascending-sorted raw sample reconstructed by the formal
  `generate_sample(beta, eta, gamma, n, repeat_id, seed="study01_v1")`. `generate_sample` returns a
  sorted array; the script re-sorts defensively and asserts equality.
- **No** padding, mask, explicit n, hand-crafted statistics, or true parameters. Banned fields
  excluded: `{beta, eta, gamma, gamma_over_eta, seed, repeat_id, combo_id, delta}`.
- Input standardizer: `sklearn.StandardScaler` per-position, fit on the **train fold of that n only**
  (reused across the 3 seeds for a given (n, fold); TEST never enters scaling stats).
- Target: 26-dim per-sample L6 loss curve (`loss_filled`; failure penalty = p99 of valid TRAIN-fold
  loss from the full train fold, identical definition to E3b). Target standardizer: 26-dim
  `StandardScaler`, fit on train fold of that n only.
- MLP identical to E3b Vector-MLP-L6: `(256,128,64)` ReLU, Adam, `alpha=1e-4`, `lr=1e-3`,
  `max_iter=300`, `early_stopping=True`, `validation_fraction=0.15`, `n_iter_no_change=20`,
  `batch_size=256`, `random_state=seed`.
- Output 26-dim, columns strictly ordered by `DELTA_GRID`; δ̂ = argmin; final J1 uses TRUE loss at δ̂.
- Split: identical deterministic 5-fold full-combo holdout over (beta, gamma/eta, n) as E3b
  (test `split_report.csv` == formal E3b `split_report.csv`, verified by test).
- Reused MC data: the 45 `chunk_*_mdm.csv` (the source behind the gitignored `mc_scan_raw.csv`).
  **No 1.17M-call MDM rerun.** Deterministic sample reconstruction; 0% non-success rate so the
  failure penalty does not bias evaluation.

## 4. Execution

**Command**:
```bash
cd "C:/weibull-study01RAW/Study/01-study-MDM最小偏移量优化研究/code"
python run_E3b_RAW_specialist.py
```
Environment: Python 3.11.9, numpy 2.4.6, pandas 3.0.3, scipy 1.17.1, **scikit-learn 1.7.2**,
matplotlib 3.11.1 (sklearn/matplotlib were missing and pip's SSL stack was broken by TLS
interception; installed via curl-downloaded wheels from PyPI — see §10).

**45 models (3 n × 5 fold × 3 seed) — all completed**, with per-(n,fold,seed) JSON+CSV checkpoints
supporting resume (rerun skips valid checkpoints).

| metric | value |
|---|---|
| Models trained this run | 45 / 45 (0 cached) |
| Training wall time | 511.4 s total (mean 11.4 s, min 5.6 s, max 18.8 s per model) |
| Full run (load + train + aggregate) | 1134.2 s (~19 min) |
| `n_iter_` | mean 90.5, min 43, max 150 |
| Train / test samples per (n, fold) | 12000 / 3000 (3 held-out combos × 1000 repeats) |

## 5. Core results — pooled / per-n / per-seed J1

**RAW specialist (this candidate), 5-fold combo holdout pooled:**

| seed | pooled J1 | J1 n=7 | J1 n=10 | J1 n=20 | endpoint rate | failure rate |
|---|---:|---:|---:|---:|---:|---:|
| 42    | 0.549756 | 0.660730 | 0.555683 | 0.401683 | 0.498 | 0.0 |
| 2026  | 0.551947 | 0.669483 | 0.552135 | 0.401094 | 0.446 | 0.0 |
| 3407  | 0.553202 | 0.669002 | 0.555002 | 0.403118 | 0.523 | 0.0 |
| **3-seed mean** | **0.551635** | **0.666405** | **0.554273** | **0.401965** | — | 0.0 |
| (std)  | 0.001424 | 0.004971 | 0.001944 | 0.000916 | — | — |

**Reference baselines (recomputed on the same pooled combo-holdout; match formal E3b exactly):**
Default 0.633219 · L1 0.632913 · L2 0.632541 · **L6-hindsight 0.494530**.

## 6. Comparison vs current F13 Vector-MLP-L6 (joint, 13-feature route)

F13 values read from the **sealed** formal `E3b_vector_mlp/seed_stability.csv` (not overwritten).

| seed | F13 pooled | RAW pooled | Δ (RAW−F13) |
|---|---:|---:|---:|
| 42    | 0.547003 | 0.549756 | +0.002754 |
| 2026  | 0.546133 | 0.551947 | +0.005814 |
| 3407  | 0.544009 | 0.553202 | +0.009193 |
| **3-seed mean** | **0.545715** | **0.551635** | **+0.005920** |

**Per-n (3-seed mean, Δ = RAW − F13):**

| n | F13 J1 | RAW J1 | Δ | relative |
|---|---:|---:|---:|---:|
| 7  | 0.657542 | 0.666405 | +0.008864 | +1.35% |
| 10 | 0.548508 | 0.554273 | +0.005766 | +1.05% |
| 20 | 0.400233 | 0.401965 | +0.001732 | +0.43% |
| pooled | 0.545715 | 0.551635 | +0.005920 | +1.09% |

**Interpretation.** The RAW specialist is **uniformly worse than F13** — at every seed and every n —
but the gap is small in absolute terms (~0.006 J1 pooled) and **shrinks with n**, becoming
essentially tied at n=20 (+0.0017). Pattern: at n=7 seven raw values carry less signal than F13's
13 engineered statistics; by n=20 the raw sample is informative enough to nearly close the gap. The
RAW route still **beats Default/L1/L2 by ~0.08 J1** and sits ~0.057 above the per-sample hindsight
floor (0.4945).

**Framing required by the contract.** This is a full-route comparison: "RAW representation + per-n
specialist" vs "F13 features + joint training". The deficit is **not attributable to RAW alone** —
it could stem from the representation, the per-n training (each specialist sees only 12000 samples
vs F13's 36000 pooled), or both. Isolating the cause needs the 2×2 (representation × training org),
which is outside this task's single-route scope.

## 7. Selection diagnostics (3-seed pooled)

- **Selected-δ distribution** (135000 selections): strongly concentrated at small offsets —
  δ=0.00 (30314), δ=0.02 (31974), δ=0.04 (14933), then monotonically decreasing; long thin tail to
  δ=0.50 (1985). The model overwhelmingly favors small MDM adjustments.
- **Endpoint selection rate** P(δ ∈ {0, 0.02, 0.48, 0.50}): seed42 0.498, 2026 0.446, 3407 0.523
  (F13: 0.488 / 0.488 / 0.562 — similar endpoint behavior). P(δ=0) alone is 0.20–0.25.
- **Near-optimal / regret** (3-seed): near-1% = 0.331, near-2% = 0.362, near-5% = 0.419;
  mean regret = 0.0597, mean relative regret = 2.633 (large because many samples have tiny oracle-min).
- **Failure rate**: 0.000 (clean data; no NaN loss at any selected δ).

## 8. Does this justify "consider wholesale replacement with the RAW route"?

**Evidence presented (not a verdict):** No. On the same 5-fold combo holdout, same 3 seeds, same
evaluation, the RAW-input per-n specialist is **~0.006 J1 worse pooled than F13 and worse at every
n** (gap largest at n=7, near-tied at n=20). It is a viable but slightly inferior alternative — it
still dominates Default/L1/L2 — yet it does **not** clear the bar to replace the F13 joint
features route, and the deficit cannot be attributed to the raw representation alone.

**Final approval is reserved for Codex** based on the actual diff, tests, artifacts, and this report.

## 9. Verification performed (all required checks)

`python/tests/test_study01_e3b_raw_specialist.py` — **14/14 PASS**:

- 45 models complete (json + predictions csv on disk)
- RAW input_dim == n for every model (7/10/20); each input row == ascending-sorted reconstructed sample
- no banned fields / true-parameter leakage in the input contract
- input + target scalers fit on TRAIN fold only (fitted stats match train, differ from test)
- 5-fold combo holdout disjoint within fold; test combos partition all 45; **identical to formal E3b split**
- 26-dim predicted columns aligned to DELTA_GRID; `selected_delta == argmin(pred)` over all 135000 rows
- pooled + per-n J1 independently recomputable from per-sample predictions
- keys complete (15000 per n per seed, 45000 per seed) and unique
- Default/L1/L2/L6-hindsight J1 match formal E3b (proves identical data/eval basis)
- sealed formal E3/E4 artifacts unchanged (`git diff` clean on those dirs)

`git diff --check`: clean. Changes are **add-only** (3 untracked paths; no existing file modified).

**Project test baseline** (`python -m pytest python/tests/test_study01_*.py`): **63 passed, 9 failed**.
All 9 failures are pre-existing in `test_study01_e3b_contract.py` and are **unrelated to this work** —
they are `FileNotFoundError` caused by that sealed test's hardcoded `PROJECT_ROOT = r"D:\weibull"`
(the repo is at `C:\weibull` here) and its read of the gitignored `mc_scan_raw.csv` (only chunks are
committed). They fail identically on the base commit; my add-only changes neither cause nor affect
them. I did not modify that sealed test (out of task scope; would alter the sealed-evidence guard).

## 10. Deviations, skipped items, residual risks

- **D:\weibull → C:\weibull**: D: drive absent; worktree placed at `C:\weibull-study01RAW`. Documented above.
- **sklearn/matplotlib install**: not in `requirements.txt` and pip's SSL was broken by TLS
  interception; resolved by curl-fetching wheels from the PyPI JSON API and installing locally.
  sklearn **1.7.2** (formal E3b's sklearn version is not recorded in its manifest; 1.7.2 is current-
  stable and MLPRegressor behaviour is stable across 1.x for this config). Noted as a minor caveat.
- **mc_scan_raw.csv not regenerated**: the candidate rebuilds `df_full` directly from the 45 chunks
  (byte-equivalent). The gitignored aggregate was not materialized, so the pre-existing E3b data
  test still skips — this is a pre-existing environment artefact, not a candidate gap.
- **No 2×2 decomposition**: representation vs training-organization are confounded (by design — the
  task is a single candidate route). Decomposition would need a separate ablation.
- **No plot generation in this run**: matplotlib is installed and the script has no plot path, but
  the task did not require figures for this candidate; tables + CSVs carry the evidence. (Can add on
  request.)
- **Residual risk**: the small RAW<F13 gap could narrow/invert with per-n hyperparameter tuning or a
  permutation-invariant raw encoder; this run uses E3b-identical hyperparameters deliberately (fair
  route comparison), so the conclusion is "at equal hyperparameters, RAW+specialist < F13+joint".

## 11. Artifact + evidence paths

Candidate root:
`Study/01-study-MDM最小偏移量优化研究/artifacts/candidate/E3b_RAW_specialist/`

- `manifest.json` — base commit, code entry, data source, input/label/split/training contracts,
  data integrity, results, F13 comparison, per-model state + prediction file hashes.
- `summary.json` — condensed results.
- `run_log.txt` — full run log; `_raw_specialist_stdout.log` (in `code/`) — raw stdout.
- `seed_stability.csv`, `model_comparison.csv`, `split_report.csv`, `raw_specialist_results.csv`.
- `diagnostics/endpoint_diagnostics.csv`, `diagnostics/near_optimal_diagnostics.csv`,
  `diagnostics/delta_distribution.csv`.
- `models/*.json` (45) — per-model meta + scaler stats + prediction hash.
- `predictions/*.csv` (45) — per-sample keys, selected δ, true loss, oracle-min, full 26-dim predicted curve.

Code/test:
- `Study/01-study-MDM最小偏移量优化研究/code/run_E3b_RAW_specialist.py`
- `python/tests/test_study01_e3b_raw_specialist.py`

Sealed formal (read-only comparison source, unchanged):
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/seed_stability.csv`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/model_comparison.csv`

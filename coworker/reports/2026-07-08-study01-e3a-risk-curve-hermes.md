# Study/01 E3a Risk-Curve Pilot Report

## Verdict

`APPROVE` for the E3a existing-grid pilot artifacts.

The result should still be treated as pilot evidence pending Codex/user manuscript acceptance, not as a ready Ch6 conclusion. The MLP runs emitted convergence warnings at `max_iter=40`, and model fitting used a documented complete-sample training cap for runtime.

## Changed Files

- `Study/01-study-MDM最小偏移量优化研究/code/run_E3a.py`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/*`
- `python/tests/test_study01_e3a_contract.py`
- Existing pre-run files also present in the working tree: `03-论文骨架.md`, `E3-risk-curve-新窗口交接.md`, the coworker plan, and the Hermes handoff.

## Commands And Results

- `python python\tests\test_study01_e3a_contract.py` -> pass.
- `python -m py_compile Study\01-study-MDM最小偏移量优化研究\code\run_E3a.py python\tests\test_study01_e3a_contract.py` -> pass.
- `python -c "... verify_data_integrity ..."` -> `1170000` expected/actual rows, `0` duplicate rows, `45` combos, `26` deltas, `1000` repeats per combo, `0.0000` non-success rate.
- `python -u Study\01-study-MDM最小偏移量优化研究\code\run_E3a.py` -> completed in about 5 minutes and wrote all E3a artifacts.
- Independent recompute from `results.csv` matched the acceptance report; `split_report.csv` has 45 unique held-out combos, 9 per fold; manifest feature inputs contain no banned true-parameter or ID fields.

`uv run pytest` and `python -m pytest` were not usable because the active Python environments do not have `pytest`; the contract test is executable directly with `python`.

## Data Integrity

- Source scan: `artifacts/formal/shared_data/mc_scan_raw.csv`
- Rows: `1,170,000`
- Unique full parameter combos: `45`
- Delta points: `26`
- Repeats per combo: `1000`
- Non-success rate: `0`
- Sample reconstruction used manifest `seed_namespace = study01_v1`.

## Split And Training Contract

- Random split: 80/20 sample-level sanity check.
- Combo holdout: deterministic 5-fold full-combo holdout over `(beta, gamma_over_eta, n)`.
- Each combo fold: `36` train combos, `9` test combos, `936000` train rows, `234000` test rows.
- Scalers, failure penalties, and L4/L5 group labels are computed from the full training fold only.
- Model fitting is capped at `12000` complete training samples per fold, preserving each selected sample's full delta curve. Full test folds are still evaluated.

## Combo Holdout Pooled

| model | J1 | failure_rate |
|---|---:|---:|
| L6-hindsight | 0.494530 | 0.000000 |
| Tabular-L6 | 0.560746 | 0.000000 |
| L5-oracle | 0.571170 | 0.000000 |
| L4-oracle | 0.582090 | 0.000000 |
| L3-oracle | 0.585068 | 0.000000 |
| NN-RC-L6 | 0.590716 | 0.000000 |
| NN-RC-L5 | 0.609747 | 0.000000 |
| NN-RC-L4 | 0.619359 | 0.000000 |
| L2 | 0.632541 | 0.000000 |
| L1 | 0.632913 | 0.000000 |
| Default | 0.633219 | 0.000000 |

## Recommendation

`APPROVE` E3a as a valid pilot signal: `NN-RC-L6` improves pooled combo-holdout J1 over L2 by about `0.041825` with no selected failure-rate increase. `Tabular-L6` is stronger than the MLP and should be treated as a signal that tabular sample-stat structure is learnable; do not overstate it before reviewing delta distributions and deciding whether E3b/E3c are needed.

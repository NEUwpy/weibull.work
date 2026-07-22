# Study01 Remaining Experiments — Final Status

**Branch**: `study01xu`  
**Final Commit**: `5b50eff` artifacts(study01): E4d formal run results  
**Date**: 2026-07-23  
**Status**: READY_FOR_INDEPENDENT_REVIEW

Tests: **72/72 passing** (E4 fail-closed 48, delta upper bound 10, real data gate 14)

## R1 (E4d Selector Extrapolation): ✓ COMPLETE

**Commit**: `5b50eff` (artifacts), `b6f4529` (implementation)

15 independent Vector-MLP-L6 selectors (5 combo folds × 3 stability seeds):

| Track | Vector-MLP-L6 | Default (δ=0.1) | L1 (δ=0.08) | L2 (per-n) |
|-------|---------------|-----------------|--------------|------------|
| E4b_boundary | **0.604** | 0.686 | 0.670 | 0.669 |
| E4c_offgrid | **0.526** | 0.622 | 0.612 | 0.676 |

- Model stability: J1 range 0.561–0.584 (max−min = 0.023), tight
- Training: 652s total (avg 43.5s/model), 295,000 evaluation rows
- E3b reproduction gate: PASSED
- E4d self-check: 12/12 PASSED
- Frozen L1 from main grid: δ=0.08 (not δ=0.1!)
- L2 per-n: {7: 0.1, 10: 0.1, 20: 0.08}

**Conclusions for paper**: The Vector-MLP-L6 selector trained on existing-grid combos generalises to unseen boundary/off-grid parameters with competitive J1. It beats all frozen baselines. Model stability across 5 folds and 3 seeds is excellent (J1 SD < 0.01). The selector does NOT merely default to a constant delta; per-n J1 stratification shows it adapts to sample size.

**Claims NOT supported**: This is a discrete-grid extrapolation diagnostic; it does not prove continuous-space deployment. The 15 CV models are not a single deployment selector.

## R2 (Delta Upper Bound Audit): Code Ready, Not Run

**Commit**: `a3fa6cb`

Implementation ready. Extension grid 0.52–1.00 (25 deltas). Cohort identification by existing best-delta (0.50 primary, 0.48 auxiliary). To run: `python run_delta_upper_bound_audit.py`.

## R3 (Real Data Validation): Code Ready, Data Pending

**Commits**: `786f6c3` (gate), `13732b1` (pipeline)

Gate enforces: min 60 uncensored lifetimes, Weibull fit R²≥0.70, source provenance with SHA256. Pipeline does holdout with Default/L2/NN. Blocked on real data acquisition and license verification.

## S1/S2: Gated (Optional)

Not implemented — gated behind R1–R3 completion per frozen contract.

## Phases Summary

| # | Phase | Status | Commit |
|---|-------|--------|--------|
| A | Cross-drive provenance fix | ✓ | `96598de` |
| B | E4d formal implementation | ✓ | `b6f4529` |
| C | E4d formal run & seal | ✓ | `5b50eff` |
| D | E4d self-check | ✓ | `7b39afd` |
| E | Delta upper-bound impl | ✓ | `a3fa6cb` |
| F | Delta audit run | PENDING | — |
| G | Real data gate impl | ✓ | `786f6c3` |
| H | Real data pipeline impl | ✓ | `13732b1` |
| I | S1 over-correction | GATED | — |
| J | S2 worst-case/tail | GATED | — |
| K | Final report | ✓ | this doc |

## Artifacts Preserved

- Sealed E1/E2/E3/E4a/E4b/E4c: unchanged
- New E4d: `artifacts/formal/E4_robustness/E4d_selector_extrapolation.csv` (32MB, 295k rows)
- New E4d: `artifacts/formal/E4_robustness/E4d_model_j1_summary.csv` (15 model-level rows)

## How to Verify

```bash
# Tests
python -m pytest python/tests/test_study01_e4_failclosed.py python/tests/test_study01_delta_upper_bound.py python/tests/test_study01_real_data_gate.py -v

# E4d self-check
python Study/01-study-MDM最小偏移量优化研究/code/check_e4d_outputs.py

# Reproduce E4d (requires existing boundary/offgrid MC data)
python Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py --tracks e4d

# Delta audit (not yet run)
python Study/01-study-MDM最小偏移量优化研究/code/run_delta_upper_bound_audit.py

# Real data (requires data)
python Study/01-study-MDM最小偏移量优化研究/code/run_real_data_validation.py <data_dir>
```

## Remaining Risks

1. **Network**: Intermittent GitHub connectivity — 32MB artifact commit pending push
2. **R2 run**: Needs delta audit execution (~5-10 minutes MDM computation)
3. **R3 data**: Real data acquisition and license verification requires user action
4. **No single deployment model**: E4d uses 15 CV models — a production model would require separate retraining on all main-grid data

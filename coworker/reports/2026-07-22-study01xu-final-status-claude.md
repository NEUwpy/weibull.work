# Study01 Remaining Experiments — Final Status

**Branch**: `study01xu`  
**Final Commit**: TBD (E4d formal run in progress)  
**Date**: 2026-07-22  
**Status**: READY_FOR_INDEPENDENT_REVIEW (pending E4d formal artifact commit)

## Completed Phases (code + tests)

| Phase | Commit | Description | Tests |
|-------|--------|-------------|-------|
| A | `96598de` | Cross-drive path provenance fix | 48/48 |
| B | `b6f4529` | E4d formal contract (5-fold × 3-seed) | 48/48 |
| E | `a3fa6cb` | Delta upper-bound audit script (R2) | 10/10 |
| G | `786f6c3` | Real data admission gate (R3) | 14/14 |
| H | `13732b1` | Real data holdout pipeline (R3) | — |
| D | `7b39afd` | E4d output self-check script | — |

## R1 (E4d): Code Ready + Computation Running

- **Implementation**: `run_e4d_formal()` — 15 independent Vector-MLP-L6 models
- **Smoke test**: 1 fold × 1 seed trained in 36s, J1=0.608 on E4b_boundary
- **Full run**: Running in background (~15×36s ≈ 9min for training + overhead)
- **Baselines**: Default δ=0.1, L1 (main-grid global δ=0.08), L2 (main-grid per-n)
- **Gate**: E3b reproduction gate passes — fold partition matches frozen split_report.csv

## R2 (Delta Upper Bound): Code Ready, Run Pending

- **Implementation**: `run_delta_upper_bound_audit.py`
- **Extension grid**: 0.52–1.00, step 0.02 (25 deltas)
- **Cohorts**: Primary (δ=0.50), auxiliary (δ=0.48)
- **All claims conditioned on original best delta**

## R3 (Real Data): Code Ready, Data Pending

- **Gate**: `real_data_gate.py` — min 60 lifetimes, Weibull fit R²≥0.70
- **Pipeline**: `run_real_data_validation.py` — holdout with Default/L2/NN
- **Blocked on**: Real data download and license verification (needs network + user)

## S1/S2: Gated on R1–R3 Completion

No code written — these are optional per the frozen contract.

## Test Summary

```
test_study01_e4_failclosed.py         48 passed
test_study01_delta_upper_bound.py     10 passed
test_study01_real_data_gate.py        14 passed
─────────────────────────────────────────────
Total                                 72 passed
```

## Artifact Locations (existing, unchanged)

- Main-grid chunks: `artifacts/formal/shared_data/chunks/` (45 files)
- E4b boundary: `artifacts/formal/E4_robustness/boundary_risk_curves.csv`
- E4c offgrid: `artifacts/formal/E4_robustness/offgrid_risk_curves.csv`
- E3b vector MLP: `artifacts/formal/E3b_vector_mlp/` (sealed)

## Remaining Action Items

1. **Wait for E4d formal run to complete** → commit artifacts
2. **Run E4d self-check** (`check_e4d_outputs.py`) → approve or revise
3. **Run delta upper-bound audit** (`run_delta_upper_bound_audit.py`)
4. **Acquire real data** → run admission gate → run holdout validation
5. **If R1–R3 all pass**: execute optional S1/S2 cache analysis
6. **Sync Study01 status docs** (`01-证据索引.md`, etc.)

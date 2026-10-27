# Study01 P6 — Current State Audit (Pre-R3 Freeze)

**Audit date**: 2026-07-25
**Branch**: `study01xu`
**Audit commit**: `95ccb28` (post-P5b closure)
**Auditor**: Executor (Claude Code), per R3 instructions §第二阶段

## Documents Reviewed

| Document | Path | Status |
|----------|------|--------|
| README.md | `README.md` | Reviewed |
| R3 plan §4.3 | `Study/.../07-剩余实验目标与规划.md` §4.3 | Reviewed — complete contract spec |
| Experimental protocol | `Study/.../02-实验协议.md` | Reviewed — real data section in paper skeleton only |
| Paper skeleton | `Study/.../03-论文骨架.md` | Reviewed — §Ch7-Ch8 real data sections confirmed |
| Admission gate | `Study/.../code/real_data_gate.py` | Reviewed — production-ready |
| Validation script | `Study/.../code/run_real_data_validation.py` | Reviewed — **PLACEHOLDER** |
| Gate tests | `python/tests/test_study01_real_data_gate.py` | Reviewed — 17 tests, all pass |
| E4d contract | `Study/.../artifacts/formal/E4_robustness/manifest_e4d.json` | Reviewed — 15 models (5 folds × 3 seeds) |

## Finding 1: `real_data_gate.py` Is Production-Ready

The admission gate (`real_data_gate.py`) is a well-structured module implementing the frozen contract §4.3 requirements:

- ✅ `RealDataSource` class with immutable provenance slots
- ✅ Source manifest validation (required fields, SHA256 format, n constraints)
- ✅ Minimum 60 uncensored lifetimes check (`MIN_UNCENSORED_LIFETIMES = 60`)
- ✅ Weibull OLS fit pre-check with frozen R² threshold (`WEIBULL_FIT_MIN_R2 = 0.70`)
- ✅ `RealDataGateResult` with `passed`/`reason`/`diagnostics`
- ✅ `dataset-ineligible` marker file on gate failure
- ✅ 17 contract tests all pass

**Verdict**: The admission gate is ready for P6 use. No changes needed.

## Finding 2: `run_real_data_validation.py` Is a Placeholder — CRITICAL

The validation script (`run_real_data_validation.py`) is documented as implementing the full P6 pipeline but is **not production-ready**. Specific gaps:

### Gap 2a: MDM.run() Tuple Treated as Dictionary (BLOCKER)

```python
# Line 193-196 — SAME BUG as the R2 BLOCK
mdm_default = MDM(train_sample)
res_default = mdm_default.run(offset=0.1)
def_beta = res_default.get('beta', float('nan'))   # ← AttributeError!
def_eta = res_default.get('eta', float('nan'))      # ← AttributeError!
```

`MDM.run()` returns `(beta, eta, gamma, r_squared, True)` — a 5-tuple. Calling `.get()` on a tuple raises `AttributeError`. This is the **exact same bug** that fabricated 0% migration in the R2 first run (commit `5059ce2`). The R2 bug was caught by independent review and fixed in commit `76906a9`, but the fix was not propagated to this placeholder script.

### Gap 2b: L2 Delta Not Implemented

Line 164 states `"L2: use frozen main-grid per-n best delta"` but the code never computes an L2 estimate. The `run_holdout_validation()` function has no L2 column in its output.

### Gap 2c: NN 15-Selector Pipeline Not Implemented

Line 165 states `"NN: use all 15 E4d selectors (each with train-fold scalers)"` but:
- No E4d models are loaded or trained
- No scalers are loaded from main-grid train folds
- No feature vectors are constructed for real data samples
- No delta predictions are made
- No model-level aggregation is performed

### Gap 2d: ECDF Distance Not Computed from Model CDF

Lines 202-203 state `"Generate Weibull CDF from estimates and compare to holdout ECDF"` but only parameter estimates are recorded. The `empirical_cdf_distance()` function (line 101) is defined but never called with model-predicted CDF values vs holdout ECDF.

### Gap 2e: Support-Set Violations Not Checked

Per §4.3, support-set violations must be reported. No implementation exists.

### Gap 2f: No Model-Level Summary for 15 Selectors

Lines 162-164 describe NN evaluation with all 15 selectors, but no per-model aggregation or cross-model distribution reporting is implemented.

### Gap 2g: No Fail-Closed Guard

The script has no runtime check that prevents it from being executed as formal evidence. If run with the current bugs, it would silently produce garbage results (AttributeError → NaN → misleading summary).

## Finding 3: P6 Contract Requirements (from §4.3)

For reference, the frozen contract requires:

| Requirement | Status in current code |
|-------------|----------------------|
| Gate check before method comparison | ✅ `run_real_data_gate()` called first |
| Fixed n repeats with seed namespace | ⚠️ Hardcoded defaults, no contract freeze |
| Identical splits for all 3 methods | ❌ Not implemented (only Default skeleton) |
| Holdout ECDF distance (main metric) | ❌ Function defined but unused |
| Support-set violations (auxiliary) | ❌ Not implemented |
| Parameter distance (auxiliary) | ❌ Not implemented |
| Paired win rate (auxiliary) | ❌ Not implemented |
| 15 E4d selectors, no cherry-picking | ❌ Not implemented |
| Model-level then cross-model aggregation | ❌ Not implemented |
| Large-sample fit = reference only | ⚠️ Named "ref_" but not wired into metrics |
| No p-values, no repeats-as-independent | ⚠️ Not yet applicable (no repeats run) |

## Finding 4: E4d 15-Model Training Contract (Frozen, Ready for Use)

The E4d manifest confirms:
- **5 folds** × **3 seeds** (42, 2026, 3407) = **15 models**
- Training data: main_grid_train_combos_only
- MLP: 3 hidden layers (256, 128, 64), alpha=0.0001, lr=0.001, max_iter=300
- Scaler: per-fold from main-grid train folds only
- 13 features: n, x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, CV, g1, g2
- 26-dim output: J1 risk curve over frozen delta grid

## Required Actions Before P6 Can Proceed

1. **Add fail-closed guard** to `run_real_data_validation.py`: on import or at top of `main()`, raise `RuntimeError` with message that this script is placeholder code and must not be used as formal R3 evidence before P7 completion.

2. **Fix MDM tuple unpacking**: correct `res_default.get(...)` → tuple unpacking `def_beta, def_eta, _, _, _ = mdm_default.run(offset=0.1)`.

3. **All other implementation** (L2, NN, ECDF, support-set, aggregation) is deferred to P7 per the plan.

## Verdict

`run_real_data_validation.py` is **placeholder code**. It must not be executed as formal R3 evidence before P7 implementation is complete. A fail-closed guard is required.

The admission gate (`real_data_gate.py`) is production-ready and correctly enforces the frozen contract.

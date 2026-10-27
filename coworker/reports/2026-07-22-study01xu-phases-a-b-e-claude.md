# Study01 — 2026-07-22 Execution Report (study01xu)

**Branch**: `study01xu` (via `worktree/study01xu-exec`)  
**Base**: `d0a3aa7` feat(study01): gate E4d inputs and provenance  
**Executor**: Claude Code  
**Status**: IN PROGRESS (network blocked — cannot push to origin)

## Completed Phases

### Phase A — Cross-drive path provenance fix ✓
- **Commit**: `96598de` fix(study01): stable provenance path for cross-drive and external paths
- **Files**: `run_E4_formal_validation.py`, `run_E3b_RAW_specialist.py`, `test_study01_e4_failclosed.py`
- **Tests**: 48/48 passing (including 5 new `TestStableProvenancePath`)
- **Fix**: Added `_stable_provenance_path()` producing `abs://`-prefixed fallbacks for cross-drive or external paths; content hash and size unaffected

### Phase B — E4d formal contract ✓
- **Commit**: `b6f4529` feat(study01): E4d formal contract — 5-fold×3-seed Vector-MLP-L6 extrapolation
- **Files**: `run_E4_formal_validation.py`, `test_study01_e4_failclosed.py`
- **Tests**: 48/48 passing (including 6 new `TestE4dFormalContract`)
- **Implementation**:
  - Replaced placeholder `run_e4d()` with `run_e4d_formal()` (15 independent models)
  - Extracted shared helpers: `_pivot_risk_vectors`, `_build_X_from_samples`, `_fit_zscore_params`, `_train_mlp`, `_evaluate_single_model`, `_model_level_summary`
  - E3b reproduction gate: fold partition vs frozen `split_report.csv`
  - Frozen baselines: Default δ=0.1, main-grid L1, main-grid L2 (n∈{7,10,20})
  - 15 model-level J1 reporting (not pseudo-pooled)

### Phase E — Delta upper-bound sensitivity audit ✓
- **Commit**: `a3fa6cb` feat(study01): delta upper-bound sensitivity audit script (R2)
- **Files**: `run_delta_upper_bound_audit.py`, `test_study01_delta_upper_bound.py`
- **Tests**: 10/10 passing
- **Implementation**:
  - Extension grid 0.52–1.00, step 0.02 (25 new deltas)
  - Primary cohort (δ=0.50) + auxiliary cohort (δ=0.48)
  - Hashes sample key sets before viewing extended results
  - Merges original 0.00–0.50 cache with new 0.52–1.00 results
  - All improvement claims conditioned on original best delta

## Pending Phases (implemented, not yet executed)

### Phase C — Run and seal E4d
- **Code ready**: `run_e4d_formal()` in `run_E4_formal_validation.py`
- **Action needed**: Run 15-model computation (~1–1.5 hours), seal artifacts
- **Blocked by**: Network for push (results should be pushed after generation)

### Phase F — Run and seal delta upper bound audit
- **Code ready**: `run_delta_upper_bound_audit.py`
- **Action needed**: Run MDM for cohort samples on extended grid, seal artifacts

## Not Yet Started

### Phase G — Real data gate
- **Needed**: Data source identification, license verification, admission gate code

### Phase H — Real data formal validation
- **Depends on**: Phase G data availability

### Phase I — S1 Over-correction loss analysis
- **Gated on**: R1–R3 completion
- **Uses**: Existing cache only

### Phase J — S2 Worst-case and tail risk
- **Gated on**: R1–R3 completion
- **Uses**: Existing cache only

### Phase K — Final report
- **Partially ready**: This report is the draft

## Network Status
- GitHub unreachable from this machine (connection reset / timeout)
- Local commits: 96598de, b6f4529, a3fa6cb (3 commits pending push)
- Auto-retry cron configured (every 5 minutes)

## Risk Items
1. **GitHub unreachable**: Cannot push commits or verify remote state
2. **E4d formal run**: 15-model computation is expensive; should be done after push succeeds
3. **Real data**: License and source verification requires network access
4. **Unknowns**: User's other computer may have parallel changes on study01xu

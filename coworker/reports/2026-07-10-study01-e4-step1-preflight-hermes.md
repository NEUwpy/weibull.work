# Study/01 E4 — Step 1 Preflight / Inventory / Contract Freeze

> Date: 2026-07-10
> Executor: Hermes (executor role)
> Plan: `coworker/plans/2026-07-10-study01-e4-staged-execution.md`
> Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`
> Codex review: `coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md` — APPROVE (conditional)

---

## Verdict: APPROVE Step 2 (MC generation only), with one mandatory cleanup action

Step 2 may proceed after Codex/user confirms how to handle the misplaced `Study/artifacts/` directory (see §5). No blockers found in the untracked scripts. No sealed artifacts or Ch1-Ch6 at risk.

---

## 1. Documents Read

| Document | Path |
|---|---|
| Project README | `README.md` |
| Study README | `Study/01-study-MDM最小偏移量优化研究/README.md` |
| Status/Handoff | `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md` |
| Staged execution plan | `coworker/plans/2026-07-10-study01-e4-staged-execution.md` |
| Codex review | `coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md` |
| Step 1 handoff | `coworker/handoffs/2026-07-10-study01-e4-step1-preflight-hermes.md` |

---

## 2. Commands Run

```
git status --short
git log --oneline -5
git branch --show-current
git diff --name-only 30490ce HEAD -- "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/"
git log --oneline --all -- "Study/artifacts/"
find Study/artifacts/ -type f -ls
find Study/artifacts/ -type d
du -sh Study/artifacts/
wc -l Study/artifacts/formal/E4_robustness/boundary_risk_curves.csv
python -c "import pandas as pd; df = pd.read_csv(...); ..."  (read-only inspection of the CSV)
```

No heavy scripts, no formal E4, no MC generation, no writes to artifact directories.

---

## 3. Git Status

Branch: `study01-e4-validation`

```
M  Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md
?? Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py
?? Study/01-study-MDM最小偏移量优化研究/code/run_E4_mc_generation.py
?? Study/artifacts/
?? coworker/handoffs/2026-07-10-study01-e4-step1-preflight-hermes.md
?? coworker/plans/2026-07-10-study01-e4-staged-execution.md
```

Latest commit: `c71b477` (chore: E4 formal batch plan+handoff+codex review+S3_FORMAL_E4_AUTHORIZED).

Sealed artifact check: `git diff 30490ce HEAD -- artifacts/formal/` = EMPTY. No sealed E1/E2/E3a/E3b artifacts touched across the entire branch.

---

## 4. Inventory of Partial Untracked Files

### 4.1 `Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py`

| Field | Value |
|---|---|
| Size | 1139 lines, 42,775 bytes |
| Purpose | Full E4 formal validation analysis script. Handles all 4 tracks: E4a (feature ablation), E4b (boundary reference evaluation), E4c (offgrid reference evaluation), E4d (selector extrapolation diagnostic). Reads existing main-grid MC data + new boundary/offgrid risk curves, writes all E4 output CSVs, manifest, summary, run_log, acceptance report. |
| Output directory | `E4_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")` where `ARTIFACTS_DIR` is imported from `config.py`. Config resolves this to `Study/01-study-.../artifacts/formal/E4_robustness/`. **Correct path.** |
| Reads from sealed artifacts? | Yes — reads `mc_scan_raw.csv` and `manifest.json` from `shared_data/`. Read-only. Does NOT write to sealed artifacts. |
| Risk to sealed artifacts? | NONE. All writes go to `E4_OUTPUT_DIR` only. Sealed E1/E2/E3a/E3b directories are never written. |
| Risk to Ch1-Ch6? | NONE. Script only reads/writes data files. No `.md` file operations. |
| Banned fields check | `BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed', 'repeat_id', 'combo_id'}` defined at line 89. Assertion at line 265 checks no overlap with `SAMPLE_FEATURE_COLS`. Feature columns are: x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, n, CV, g1, g2 — all sample-observable. |
| MLP config | (256,128,64), max_iter=300, early_stopping — matches E3b-equivalent config per Codex review decision #3. |
| Combo lists | 20 boundary combos (B01-B20), 14 offgrid combos (O01-O14) — hardcoded and frozen. Matches the formal batch plan. |
| Reusability | HIGH. This script is the intended analysis entry point for Steps 3-5. It is well-structured, has proper provenance/manifest generation, and correctly implements the L1-L6 reference evaluation, feature ablation, and E4d diagnostic. Can be reused as-is for Step 3+ once MC data exists. |

**Notable details:**
- `R_MAIN = 1000` imported from config (E4a uses main-grid data which has R=1000). For E4b/E4c, the script reads from the MC generation output (R=500).
- The script checks for `boundary_risk_curves.csv` and `offgrid_risk_curves.csv` existence at runtime and gracefully degrades if not present (logs WARNING, skips that track).
- E4d has try/except with skip reason file generation.

### 4.2 `Study/01-study-MDM最小偏移量优化研究/code/run_E4_mc_generation.py`

| Field | Value |
|---|---|
| Size | 248 lines, 9,001 bytes |
| Purpose | MC data generation for E4b (boundary) and E4c (offgrid) tracks. Uses subprocess-parallel workers (N_WORKERS=4). Each worker handles a subset of combos, writes chunk CSVs. After all workers complete, merges chunks into `boundary_risk_curves.csv` and `offgrid_risk_curves.csv`. |
| Output directory | `E4_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")` from config. **Correct path.** Same as the analysis script. |
| R_FORMAL | 500 (hardcoded). Matches Codex review decision and staged plan Step 2. |
| Combo lists | Same 20 boundary + 14 offgrid combos as the analysis script. Frozen and consistent. |
| Fields written | combo_id, beta, eta, gamma, gamma_over_eta, n, repeat_id, delta, beta_hat, eta_hat, gamma_hat, r_squared, converged, time_ms, status. Matches the schema used by `run_E4_formal_validation.py`. |
| Chunk handling | Workers write `chunk_XX.csv` files. After all complete, `merge_chunks()` concatenates, splits by combo_id prefix (B vs O), writes final files, then deletes chunks. |
| Risk to sealed artifacts? | NONE. Only writes to `E4_OUTPUT_DIR`. |
| Risk to Ch1-Ch6? | NONE. |
| Reusability | HIGH. This is the intended MC generation script for Step 2. However, the merge step assumes all workers complete successfully. If interrupted, chunk files may persist (see §5 below). |

**Notable details:**
- Uses `generate_sample(beta, ETA, gamma, n, rid, seed=SEED_NAMESPACE)` — same sample generation as all other Study/01 experiments.
- Uses `MDM(sample).run(offset=delta)` — same MDM implementation.
- Status field per row: "success" if converged and bh>0 and eh>0, else "failure". Exception path sets "error:{ExceptionType}".
- Chunk files are intermediate: `chunk_00.csv` through `chunk_03.csv`.

### 4.3 Combo list consistency check

Both scripts define identical combo lists:
- E4B_BOUNDARY_COMBOS: B01-B20, covering beta={1.2, 6.0, 2.5, 1.5, 4.0, 2.0}, gamma_over_eta={0.0, 0.5, 1.0, 0.1}, n={5, 20, 50, 10, 7}
- E4C_OFFGRID_COMBOS: O01-O14, covering off-grid beta/gamma_over_eta/n combinations

These match the formal batch plan and the Codex-approved ~20 boundary combo target.

---

## 5. Study/artifacts/ — Misplaced Partial Output

### Finding: MISPLACED and INCOMPLETE

| Field | Value |
|---|---|
| Path | `Study/artifacts/formal/E4_robustness/boundary_risk_curves.csv` |
| Correct path | `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/boundary_risk_curves.csv` |
| Size | 7.05 MB, 51,976 data rows + 1 header |
| Created | 2026-07-10 07:05 |
| Combos covered | B01, B02, B03, B04 only (4 of 20 boundary combos) |
| Betas covered | 1.2 only |
| N values covered | 5, 20 only |
| R per combo | 500 |
| Status distribution | 51,976 success, 0 failure |
| Offgrid data | ABSENT (no offgrid_risk_curves.csv) |
| Chunk files | ABSENT (no chunk_XX.csv) |
| Manifest | ABSENT |
| Git tracked | NO (entire `Study/artifacts/` is untracked) |

### Root cause analysis

The two untracked scripts both import `ARTIFACTS_DIR` from `config.py`, which resolves to `Study/01-study-.../artifacts/formal/`. The correct `E4_robustness/` directory exists but is EMPTY. Therefore, the misplaced `Study/artifacts/` was NOT produced by the current versions of these scripts. It was likely produced by:
- An earlier prototype script that hardcoded a different path, or
- Running from a different CWD with different `__file__` resolution, or
- An intermediate development iteration before paths were finalized.

The partial data (only 4 of 20 boundary combos, 0 offgrid combos) indicates the MC generation was interrupted or was a partial test run.

### Risk assessment

- Does NOT touch sealed artifacts (different directory tree entirely).
- Does NOT conflict with the correct E4 output path.
- Is untracked — no git contamination.
- Is harmless to leave in place but confusing if mistaken for valid output.

### Recommendation

**DO NOT DELETE in this step.** Recommend Codex/user to:
1. Delete `Study/artifacts/` entirely before Step 2 starts (it is incomplete and misplaced).
2. Verify the correct output path (`Study/01-study-.../artifacts/formal/E4_robustness/`) is clean before running `run_E4_mc_generation.py`.

If reused as-is, the 4-combo partial data could be mistaken for complete boundary coverage. The data quality itself appears valid (correct schema, correct MDM calls, R=500), but it covers only 20% of the boundary combos and 0% of offgrid.

---

## 6. Sealed Artifact and Ch1-Ch6 Safety

| Check | Result |
|---|---|
| `git diff 30490ce HEAD -- artifacts/formal/` | EMPTY — no sealed artifacts modified |
| E4 commits file list | Only status handoff, plan, handoff, report, smoke script, pilot artifacts — no Ch1-Ch6, no README, no 00-05 |
| Untracked scripts write paths | Both write only to `Study/01-study-.../artifacts/formal/E4_robustness/` — does not touch E1/E2/E3a/E3b directories |
| Ch1-Ch6 drafts at risk? | NO — untracked scripts perform no `.md` file operations |
| Banned fields in features? | PASS — assertion at line 265, feature set is sample-observable only |

---

## 7. Contract Freeze Summary

The following design decisions are confirmed frozen for Step 2+:

1. **E4b boundary combos**: 20 combos (B01-B20), hardcoded in both scripts.
2. **E4c offgrid combos**: 14 combos (O01-O14), hardcoded in both scripts.
3. **R_FORMAL**: 500 (in `run_E4_mc_generation.py`).
4. **MC generation script**: `run_E4_mc_generation.py` — subprocess-parallel, 4 workers, chunk-merge pattern.
5. **Analysis script**: `run_E4_formal_validation.py` — all 4 tracks, reads MC data, writes full output suite.
6. **MLP config**: (256,128,64), max_iter=300, early_stopping — E3b-equivalent.
7. **Feature contract**: 13 sample-observable features, z-score on training set, banned fields enforced.
8. **E4b Option C**: Reference-only evaluation at boundary (no NN deployment).
9. **E4c evaluation-only**: No continuous-space training.
10. **Output directory**: `Study/01-study-.../artifacts/formal/E4_robustness/` (correct path from config.py).

---

## 8. Step 2 Readiness Assessment

**Can Step 2 proceed?** YES, with one precondition.

The MC generation script (`run_E4_mc_generation.py`) is correctly structured, writes to the correct directory, uses the correct combo lists and R=500, and does not risk sealed artifacts. It can be run to generate the full 20 boundary + 14 offgrid combos.

**Precondition:** The misplaced `Study/artifacts/` directory should be cleaned up (deleted) before Step 2 starts to avoid confusion. This is a Codex/user decision — the executor does not perform destructive cleanup in Step 1.

**Estimated runtime for Step 2:** 34 combos × 500 repeats × 26 deltas = 442,000 MDM calls. At ~60ms/call (observed from the partial data's time_ms column) with 4 parallel workers, approximately 442000 × 0.06 / 4 / 60 ≈ 110 minutes.

---

## 9. Recommendation: APPROVE Step 2

**APPROVE** proceeding to Step 2 (E4b/E4c MC generation only), subject to:

1. Codex/user confirms cleanup of `Study/artifacts/` (misplaced partial output).
2. Step 2 runs only `run_E4_mc_generation.py` — does NOT run the analysis script.
3. Step 2 stops after generating `boundary_risk_curves.csv` and `offgrid_risk_curves.csv`.
4. Step 2 output goes to `Study/01-study-.../artifacts/formal/E4_robustness/`.

No blockers identified. No code changes required for the untracked scripts. No risk to sealed artifacts or Ch1-Ch6.

# E4 Validation Suite — Codex First-Round Review

> Date: 2026-07-10
> Reviewer: Codex (reviewer role)
> Stage: S2_CODEX_REVIEW → S3_FORMAL_E4_AUTHORIZED (conditional)
> Report under review: `coworker/reports/2026-07-09-study01-e4-validation-suite-hermes.md`
> Plan: `coworker/plans/2026-07-09-study01-e4-validation-suite.md`

## Verdict: APPROVE (conditional)

The first-round smoke/pilot complies with all plan boundaries. The E4a/E4b/E4c contracts are well-structured and correctly distinguish pilot, formal, and E3c scopes. Formal artifacts and Ch1-Ch6 are untouched. The smoke artifacts are properly placed, labeled, and traceable.

This approval authorizes proceeding to formal E4 **after** the two design decisions below are confirmed in a second-round handoff.

---

## Checklist Results

### 1. First-round STOP conditions — PASS

| Stop condition | Status |
|---|---|
| No full Formal E4 run | PASS — smoke used R=10 and 3 combos per track |
| No Ch7 writing | PASS — no Ch7 file exists or was modified |
| No modifications to sealed artifacts | PASS — `git diff 30490ce HEAD -- artifacts/formal/` is empty |
| No modifications to Ch1-Ch6, README, 00-05 | PASS — E4 commits (d17edee, 245bca2) touched only: status handoff, plan, handoff, report, smoke script, pilot artifacts |
| No banned fields in deployable model inputs | PASS — verified in code (BANNED_FIELDS set defined line 116, assertion at line 281, SAMPLE_FEATURE_COLS contains only sample-observable statistics) |
| E4/E3c separation | PASS — E4c explicitly scoped as evaluation-only; continuous-space training routed to E3c |
| Model serialization blocker flagged | PASS — clearly identified as a design decision with 3 options |

**Commit verification:**
- `git log --oneline -3`: ccacd35 → d17edee → 245bca2 (E4 HEAD)
- `git diff 30490ce HEAD -- artifacts/formal/`: EMPTY (no formal artifacts changed across entire branch)
- `git status --short`: CLEAN (all committed, no stray files)

### 2. E4a/E4b/E4c contracts — PASS

The three contracts clearly distinguish:
- **Pilot**: smoke scale (3 combos, R=10, tiny MLP (32,16), train=test) — explicitly labeled "PILOT — NOT FORMAL EVIDENCE" in manifest, summary, results, and run_log.
- **Formal**: R=500, 5-fold combo holdout, 3 seeds, E3b-equivalent MLP config, full boundary grid.
- **E3c**: explicitly excluded from E4; any continuous-space TRAINING would be reclassified as E3c. The smoke only tests evaluation feasibility for off-grid parameters.

The E4a contract proposes 4 feature groups (full, n_only, scale_quantile, shape) with per-n/fold/seed reporting — this correctly extends the E3b single-fold clue into a formal contract.

The E4b contract proposes Option C (references only on boundary) as the default, with Option A (retrain + extrapolate) as a separate diagnostic. This is the correct framing given the model serialization gap.

### 3. Smoke artifact structure — PASS

```
artifacts/pilot/E4_validation_smoke/
  manifest.json    — provenance: git_commit, mc_git_commit, python_version, method versions, smoke_scale, delta_grid, metrics_contract
  summary.json     — per-track results, elapsed, banned_field_check, schema_verification
  results.csv      — 5 rows, columns: track, model_or_group, metric, value, n, note
  run_log.txt      — execution log with timestamps and git commit
```

All four expected files present (schema_report.json was listed as optional in the plan; schema_verification is embedded in summary.json — acceptable).

Manifest records: run_id, status, code_entry, git_commit, workspace_dirty, dirty_files, python_version, input_data (mc paths + provenance), method_versions, smoke_scale, delta_grid, metrics_contract, output_files, notes. All required provenance fields present.

### 4. Formal artifacts and Ch1-Ch6 untouched — PASS

- `git diff 30490ce HEAD --name-only -- artifacts/formal/` → EMPTY
- E4 commits (d17edee, 245bca2) file list contains ZERO matches to: README.md, draft-Ch*, 00-*, 01-*, 02-*, 03-*, 04-*, 05-*, 作者备注, E3c-E4-后续决策备忘.md
- The Ch1-Ch6/README changes visible in `git diff 30490ce HEAD` were from commit ccacd35 (Ch restructure), which predates the E4 commits.

### 5. Report recommendation — PASS

Report gives clear two-level verdict:
- "APPROVE FIRST-ROUND PLAN / DO NOT APPROVE FORMAL E4 RESULT YET"
- "APPROVE proceeding to formal E4" subject to 3 conditions (E4b model reuse decision, E4c scope confirmation, second-round handoff)

This is the correct framing — approve the pipeline/design, not the pilot numbers.

### 6. Banned fields — PASS

Code defines `BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed', 'repeat_id', 'combo_id'}` and asserts none overlap with `SAMPLE_FEATURE_COLS`. The feature set contains only: x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, n, CV, g1, g2 — all sample-observable statistics. No ground-truth or identity leakage.

### 7. E4b model reuse issue — PASS

Correctly flagged. The report identifies that E3b Vector-MLP-L6 was never serialized (trained in-memory, discarded after evaluation). Three options presented:
- Option A: retrain on main grid, evaluate on boundary (extrapolation test)
- Option B: include boundary in training (changes training data → E3c territory)
- Option C: evaluate only Default/L1/L2/oracle on boundary, report as scope limitation

Recommendation: Option C for E4b, Option A as separate diagnostic. This is sound.

### 8. E4c scope — PASS

Correctly decided as evaluation-only. The smoke tests that the pipeline can generate samples and compute features for arbitrary (off-grid) parameters. The report explicitly states: "If continuous-space TRAINING is needed, it becomes E3c." This matches the plan boundary: "Do not silently convert continuous-space training into E4."

---

## E3b Contract Re-verification

Re-ran `python -m pytest python/tests/test_study01_e3b_contract.py -q`: **11 passed, 0 skipped, 0 failed**. Sealed E3b contract intact.

---

## Design Decisions to Confirm Before Formal E4

These are NOT blockers for this review — they are decisions to lock into the second-round formal handoff:

1. **E4b model reuse: Option C confirmed.** E4b formal will evaluate Default/L1/L2 and oracle references (L3/L4/L5/L6-hindsight) on boundary parameters. Vector-MLP-L6 will NOT be deployed at boundary. Option A (retrain + extrapolate) may be added as a diagnostic appendix if the formal results warrant it, but only as a separately labeled experiment.

2. **E4c scope: evaluation-only confirmed.** E4c stays in E4. It evaluates reference selections at off-grid points. Any continuous-space training experiment is deferred to E3c per the existing decision memo.

3. **E4a MLP config: reuse E3b config** ((256,128,64), max_iter=300, early_stopping) for formal comparability. The smoke used (32,16)/50 — explicitly not comparable.

4. **E4b boundary combo count: targeted subset (~20 new combos)** rather than full Cartesian product of all new β × γ/η × n values, for cost control. The formal handoff should specify the exact list.

---

## Minor Observations (non-blocking)

- Typo in variable name: `E4A_SMOKK_COMBOS` / `E4A_SMOKK_REPEATS` (double-K). Cosmetic only; does not affect correctness.
- The manifest `git_commit` records d17edee (the plan commit), not 245bca2 (the smoke commit). This is because the smoke was run before the final commit was made. The manifest correctly records `workspace_dirty: true` and lists the dirty file. This is acceptable for a smoke run; the formal run should commit the script first, then run with a clean tree.

---

## Authorization

**APPROVE first-round work.**

Stage advances to `S3_FORMAL_E4_AUTHORIZED`. A second-round formal E4 handoff may be written with the confirmed design decisions above. Formal E4 execution requires the second-round handoff to explicitly list: exact boundary combo set, exact feature group definitions, exact MLP config, and output directory `artifacts/formal/E4_robustness/`.

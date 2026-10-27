# Study/01 E3b Vector-Output Heavy MLP Report

## Verdict

`APPROVE` for the E3b artifact/provenance contract now present in the working tree.

This approves the E3b result package as a valid Study/01 experiment artifact set. It does not write manuscript conclusions or promote Ch6 prose. Commit-level provenance is still pending because the E3b files are untracked and `manifest.json` records `workspace_dirty=true`.

## Final Run Evidence

- Final run started via independent `Start-Process` at 2026-07-09 11:00:08 Asia/Shanghai to avoid tool timeout killing the process.
- Final artifact timestamps are 2026-07-09 13:30:54 to 13:31:04.
- Final stdout log reached the normal `Decision: APPROVE` terminal summary.
- Final stderr log was empty.
- `run_log.txt` was updated from the final stdout capture and now records:
  - `Saved sample_features.csv (45000 unique samples from all folds)`
  - seed stability for `42`, `2026`, and `3407`
  - final `Decision: APPROVE`
- An earlier foreground attempt stopped at feature ablation because the tool wrapper timed out; it did not update the artifact set and is not the accepted run.

## Reviewer Findings Closed

| Finding | Status |
|---|---|
| Duplicate `n` header in `sample_features.csv` | Fixed in generator with `SAMPLE_KEYS + [c for c in SAMPLE_FEATURE_COLS if c not in SAMPLE_KEYS]`; final CSV has one `n` column. |
| `sample_features.csv` provenance mismatch | Fixed by final full rerun; file has 45,000 rows from all 5 folds and aligns with `risk_curves.csv`. |
| Seed stability checked only seed 42 | Fixed; final `seed_stability.csv` and `run_log.txt` cover seeds `42`, `2026`, and `3407`. |
| Scope artifacts drift | `Study/研究规划备忘录.md` is stashed as non-E3b work; E3a diff is clean. `docs/研究原则.md` and `history/260709上下文.md` remain visible untracked Study scope files and should be either intentionally included or explicitly excluded before commit. |

## Commands And Results

- `python -m py_compile Study/01-study-MDM最小偏移量优化研究/code/run_E3b_vector_mlp.py` -> pass
- `python -m py_compile python/tests/test_study01_e3b_contract.py` -> pass
- `python python/tests/test_study01_e3b_contract.py` -> 11 passed, 0 skipped, 0 failed
- `git diff --name-only -- Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive` -> no output

## Data And Artifact Integrity

- Source scan rows: 1,170,000
- Unique `(beta, gamma_over_eta, n)` combos: 45
- Delta points: 26
- Repeats per combo: 1,000
- Non-success rate: 0
- `sample_features.csv`: 45,000 rows, 45 combos, 18 unique columns, no duplicate `n`
- `risk_curves.csv`: 45,000 rows
- `sample_features.csv` keys align with `risk_curves.csv`
- `manifest.created_at`: 2026-07-09T05:31:04.585316+00:00
- `manifest.git_commit`: 04e99c5
- `manifest.workspace_dirty`: true

## Combo Holdout Pooled

| model | J1 | failure_rate | J1_n7 | J1_n10 | J1_n20 |
|---|---:|---:|---:|---:|---:|
| L6-hindsight | 0.494530 | 0.000000 | 0.591115 | 0.503582 | 0.361479 |
| Vector-MLP-L6 | 0.547003 | 0.000000 | 0.657558 | 0.549815 | 0.403679 |
| Tabular-L6 | 0.557849 | 0.000000 | 0.666695 | 0.563795 | 0.413813 |
| L5-oracle | 0.571170 | 0.000000 | 0.676581 | 0.579700 | 0.429992 |
| L4-oracle | 0.582090 | 0.000000 | 0.685935 | 0.591759 | 0.442494 |
| L3-oracle | 0.585068 | 0.000000 | 0.690009 | 0.592188 | 0.447339 |
| Vector-MLP-L5 | 0.596829 | 0.000000 | 0.708311 | 0.605144 | 0.448010 |
| Vector-MLP-L4 | 0.606229 | 0.000000 | 0.712337 | 0.617645 | 0.462204 |
| L2 | 0.632541 | 0.000000 | 0.739286 | 0.644520 | 0.488235 |
| L1 | 0.632913 | 0.000000 | 0.739733 | 0.645104 | 0.488235 |
| Default | 0.633219 | 0.000000 | 0.739286 | 0.644520 | 0.490866 |

## Acceptance Gates

- Full E3b pipeline reached final save and terminal decision without stderr.
- Oracle/reference rows match the accepted hierarchy and values:
  - L3 = 0.585068
  - L4 = 0.582090
  - L5 = 0.571170
  - L6 = 0.494530
- Seed stability:
  - seed 42: pooled J1 = 0.547003
  - seed 2026: pooled J1 = 0.546133
  - seed 3407: pooled J1 = 0.544009
- `Vector-MLP-L6` improves over L2 by 0.085538 pooled J1.
- `Vector-MLP-L6` is 0.010847 J1 from `Tabular-L6`.
- E3a artifacts are unchanged.
- Contract tests pass 11/11.

## Remaining Before Commit

- Decide whether to include `Study/01-study-MDM最小偏移量优化研究/docs/研究原则.md` and `history/260709上下文.md` in the E3b commit scope.
- Keep `stash@{0}` (`non-E3b: 研究规划备忘录.md 研究内容段落`) untouched unless the user explicitly wants it restored.
- After staging/commit, the current `manifest.git_commit=04e99c5` will not point to a commit containing the E3b generator. For stricter publication-grade commit provenance, rerun after committing the generator or add an explicit script hash provenance field in a follow-up run.

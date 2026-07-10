# Study/01 E4 Step 4 final review

## Verdict: APPROVE for mainline consolidation

Verified against the live artifacts rather than the executor report alone:

- `E4a_feature_ablation.csv`: 60 rows, 5 folds, 4 feature groups, 3 seeds; all declared numeric fields finite.
- `split_report.csv`: 45 unique combinations, 9 per fold.
- `manifest_e4a.json`: FORMAL, E4a completed, other tracks not requested, all six declared outputs exist.
- `cost_report.csv`: 63 rows after reconciliation; the E4b/E4c rows exactly preserve the tracked Step 3 values from `0147baa`.
- Step 3 files other than the intentionally consolidated cost report have no diff from `0147baa`.
- The E4a worker exited after writing the complete artifact set; total elapsed was 24,845 seconds.

Corrections required before approval were applied to the executor report:

1. Removed invalid direct ranking between main-grid E4a and boundary-grid E4b J1 values.
2. Corrected the dispersion description from seed-only to pooled fold-and-seed variation.
3. Replaced the path-encoding explanation with the reflog-confirmed single-worktree branch-switch root cause.
4. Recorded the unresolved shared-cost overwrite behavior as a hard gate before any future subset-track run.

Scope boundary: this approval covers Step 4 evidence preservation and branch consolidation. It does not authorize E4d or new Ch7 claims.

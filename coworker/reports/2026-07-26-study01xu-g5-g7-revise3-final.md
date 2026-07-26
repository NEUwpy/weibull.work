# Study01 G5-G7 REVISE v3 — Final Executor Report

**Date**: 2026-07-26
**Branch**: `study01xu` (worktree `study01-ms`)
**Executor**: Claude Code
**Status**: `READY_FOR_INDEPENDENT_REVIEW`
**Baseline**: `e48e374` (REVISE v2 tip)

---

## Final Tip

```
9a919e2 (local == origin/study01xu)
```

## Commit Chain

| # | Commit | Responsibility |
|---|--------|---------------|
| 1 | `def3df1` | **fix(figures+manuscript+references)**: Fig7 pooled J1 from summary_e4d.json, S2 beta-profile from by_beta_n.csv, S5 per-model from by_model.csv, refs [3][4][7] with DOIs |
| 2 | `9a919e2` | **audit(manuscript)**: rebuild G7 audit chain + cover letter template |

## Verification

| Check | Result |
|-------|--------|
| Tests (gate+P6+P7+P8) | **153 passed, 0 failed, 0 skipped** |
| Auto-audit (17 groups) | **ALL CHECKS PASSED** |
| SHA256SUMS_p8a (5 files) | All verified |
| git diff --check def3df1..HEAD | Clean |
| git diff --check a52c3023..HEAD | Clean |
| local == origin/study01xu | `9a919e2` |

## Key Corrections

### Fig.7 (E4d)
- Left panel: per-track pooled J1 from `summary_e4d.json` (boundary=0.6038, off-grid=0.5263), NOT `l6_J1_common_mean`
- Right panel: per-model true_loss distribution (15 models)
- Figure title and axis labels distinguish "Per-Track Pooled J1" from "Per-Model True Loss"

### S2 (Beta-Profile)
- Rebuilt from `E2_beta_profile_audit/by_beta_n.csv`
- Shows `local_gradient_slope_median` +/- IQR by beta and n
- Spearman rho annotated per n (~-0.46/-0.49/-0.53)
- No longer uses L1-L6 ladder

### S5 (E4d Per-Model)
- Uses `E4d_paired_comparisons_by_model.csv` (90 rows, 30 Default-ref)
- Shows 15 model-level `l6_J1_common` values per track
- Per-track pooled J1 from `summary_e4d.json` annotated as horizontal lines
- No longer repeats identical l6 values across 3 reference models

### Manuscript
- Figure citations to Fig.1-9 throughout
- Beta-profile: 5β×3n×20=300 total, 60 per beta
- Study1.5: correct path (`015-study-NN输入表征与样本量机制研究`), correct description
- E4a: always "retained-subset comparison"
- References [3][4][7]: verified with DOIs from local literature

### References
- [3] Xie et al. (2023) IJSSD 23(8) 2350085. doi:10.1142/S0219455423500852
- [4] 谢里阳等 (2025) 东北大学学报 46(7) 108-112. doi:10.12068/j.issn.1005-3026.2025.20240194
- [7] Yang et al. (2025) Prob. Eng. Mech. 82, 103828. doi:10.1016/j.probengmech.2025.103828

### Figures Generated (12 total, all 3 formats)
Main: Fig.6-9; Supplementary: S1-S8

### Pending User Decisions
- Target journal
- Author list and order
- Corresponding author and contact
- Funding information
- CRediT author contributions

## Status: READY_FOR_INDEPENDENT_REVIEW

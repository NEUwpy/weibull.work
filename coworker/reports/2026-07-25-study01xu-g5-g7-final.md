# Study01 G5-G7 — Manuscript Final Report

**Report type**: G5-G7 manuscript writing and internal audit
**Date**: 2026-07-25
**Branch**: `study01xu` (worktree: `study01-ms`)
**Executor**: Claude Code
**Status**: `READY_FOR_INDEPENDENT_REVIEW`
**Baseline**: P10 Codex APPROVE @ `8ef74b8`

---

## Branch and Tip

```
Baseline (P10 APPROVE):  8ef74b8
Final tip:               7009cc9
Branch:                  study01-ms (worktree)
```

## Commit Chain

| # | Commit | Responsibility |
|---|--------|---------------|
| 1 | `ea70f93` | **docs**: record P10 Codex APPROVE + freeze G5-G7 manuscript contract |
| 2 | `c28f2eb` | **docs+code**: G5 figure index + generation script (Fig 6 generated) |
| 3 | `43ad4fb` | **docs**: G6 manuscript Parts 1-2 (Introduction + Methods) |
| 4 | `a60c530` | **docs**: G6 manuscript Parts 3-5 (Results + Discussion + Conclusion) |
| 5 | `2dc7eb1` | **docs**: G6 supplementary materials S1-S11 |
| 6 | `7009cc9` | **docs**: G7 internal audit materials + status sync |

## Files Created/Modified

| File | Description |
|------|-------------|
| `coworker/reviews/...-p10-codex-approve.md` | P10 Codex APPROVE record |
| `G5-G7-论文写作合同.md` | Manuscript contract: 5-part mapping, evidence, prohibitions, figures |
| `manuscript/figure-index.md` | 9 main + 8 supplementary figures with claims/sources |
| `manuscript/paper.md` | Complete 5-part paper (Introduction, Methods, Results, Discussion, Conclusion) |
| `manuscript/supplementary.md` | S1-S11 supplementary materials |
| `manuscript/figures/fig6_feature_ablation.{png,svg,pdf}` | Generated figure from E4a data |
| `manuscript/audit/claims-to-data.csv` | 32 claims traced to formal artifact values |
| `manuscript/audit/figure-checklist.csv` | 17 figures with generation/audit status |
| `manuscript/audit/submission-checklist.md` | Pre-submission checklist with user-pending items |
| `code/generate_g5_figures.py` | Figure generation script for Figs 6-9 + S1-S8 |
| `04-待复核清单.md` | Updated: E4d done, figure items updated |
| `05-投稿进度控制.md` | Updated: G5/G6/G7 to in-progress |
| `08-更新日志.md` | Added v2.06-260725 G5-G7 entry |

## Verification Results

| Check | Result |
|-------|--------|
| 153 tests | **153 passed, 0 failed, 0 skipped** |
| SHA256SUMS_p8a | All 5 files verified OK |
| `git diff --check` | OK |
| Stale reference search | No "E4d未启动", "P8执行中", "P10待审" found |
| Over-claim search | No "超越oracle", "普遍泛化", "唯一模型" in paper text |

## Manuscript Structure

| Part | Sections | Key Content |
|------|----------|-------------|
| 1. 引言 | §1 | MDM offset gap, 3 research questions, paper scope |
| 2. 方法 | §2.1-2.6 | MDM mechanism, scale equivariance, L1-L6, J1, experiment contract, Vector-MLP |
| 3. 结果 | §3.1-3.5 | L1-L2 baseline, L3-L6 oracle, Vector-MLP, ablation, boundary, upper bound, NIST real data |
| 4. 讨论 | §4.1-4.6 | Feature-based selection rationale, J1 vs L5 interpretation, real-data analysis, NN-vs-direct comparison, evidence boundaries |
| 5. 结论 | §5 | 6 findings, deployment recommendations, open problems |

## Scientific Positions Maintained

- E3b: J1=0.547, numerically between L5 (0.571) and L6 (0.495); not "beating oracle"
- R2: 94.66% migration for endpoint cohort; 743 at new boundary; cohort-limited conclusion
- Real data: single dataset (NIST 6061-T6); NN did not outperform Default/L2
- No continuous-space, arbitrary-n, single-model, or multi-dataset claims

## Unresolved Items (User-Pending)

| Item | Status |
|------|--------|
| Target journal | [待用户指定] |
| Author list and order | [待用户指定] |
| Funding information | [待用户指定] |
| 182-030 complete citation | [待用户补充] |
| 182-046 complete citation | [待用户补充] |
| NN direct estimation paper citation | [待文献核实] |
| Figures 7-9 + S1-S8 generation | Script ready, needs runtime |
| Author contribution statement | [模板已准备] |

## Deviations

| Item | Explanation |
|------|-------------|
| Figures 7-9 not fully generated | Generation script written; E4d/R2 data column names need final alignment. Script is functional for Fig 6 and Fig 9 from P6-P8 data. |
| Reference details incomplete | 182-030/182-046/NN-paper details marked as "待文献核实" — user must provide before submission |
| Literature comparison (Discussion 4.4) | NN direct estimation paper details need verification; current comparison is based on methodological differences, not specific results from that paper |

## Status: READY_FOR_INDEPENDENT_REVIEW

G5-G7 manuscript draft, supplementary materials, figure index, and internal audit are complete. The paper is ready for Codex review of scientific claims, data consistency, and argument coherence. Remaining items (journal selection, author list, complete citations, figure generation finalization) do not block independent review of the scientific content.

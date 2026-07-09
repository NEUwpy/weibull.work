# Study/01 Ch6 Doc Sync Report

Role: executor/reviewer

## Verdict

APPROVE for this documentation sync as a Study/01 continuation step.

This round does not rerun experiments. It consumes the already sealed E3b evidence package and updates the manuscript/workspace documents so Ch6 can proceed under the existing-grid evidence boundary.

## Scope

Goal:

- Close stale "E3 frozen / not started" wording after E3b approval.
- Draft Ch6 from the sealed E3b existing-grid evidence.
- Add an E3c/E4 decision memo so Ch6 can proceed without accidentally expanding into a new experiment.
- Preserve the distinction between existing-grid evidence and continuous-space/E4 boundary claims.
- Tidy interrupted-session artifacts without treating historical handoffs as current rules.

Changed files:

- `Study/01-study-MDM最小偏移量优化研究/01-证据索引.md`
- `Study/01-study-MDM最小偏移量优化研究/02-实验协议.md`
- `Study/01-study-MDM最小偏移量优化研究/04-待复核清单.md`
- `Study/01-study-MDM最小偏移量优化研究/05-投稿进度控制.md`
- `Study/01-study-MDM最小偏移量优化研究/draft-Ch6-初稿.md`
- `Study/01-study-MDM最小偏移量优化研究/E3c-E4-后续决策备忘.md`
- `Study/01-study-MDM最小偏移量优化研究/history/E3-risk-curve-新窗口交接.md`
- `Study/研究规划备忘录.md`
- `Study/研究原则.md`

Interrupted-session cleanup:

- `E3-risk-curve-新窗口交接.md` was moved into `history/` and marked stale.
- `Study/研究原则.md` was promoted to a top-level Study principle note with a title and role note.
- `Study/研究规划备忘录.md` had a half-written "研究内容" section; it is now completed and aligned to the current Study/01 framing.

## Evidence Used

- E3b sealed package: `bedd65a`.
- E3b key result: `Vector-MLP-L6` pooled J1=0.547003 vs L2=0.632541.
- Oracle references: L3=0.585068, L4=0.582090, L5=0.571170, L6=0.494530.
- Seed stability: 42/2026/3407 pooled J1 = 0.547003 / 0.546133 / 0.544009.
- Contract test file: `python/tests/test_study01_e3b_contract.py`.

## Checks Run

- `python python/tests/test_study01_e3b_contract.py`
  - Result: 11 passed, 0 skipped, 0 failed.
- `git diff --check`
  - Result: no whitespace errors; only Windows LF/CRLF warnings.
- `rg` stale-state scan over Study/01 active files.
  - Result: no active current-state blocker remains; historical handoff contains stale wording but now has an explicit archive warning.

## Remaining Boundaries

- Ch6 uses E3b diagnostic plots and tables; publication-ready Ch6 figures are not frozen.
- E3c is not started and is not required for the current Ch6 existing-grid claim.
- E4 remains a separate decision if the paper needs broader robustness or continuous-space deployment claims.
- `08-更新日志.md` appears modified in `git status` but has no content diff in this round; likely line-ending-only workspace state.

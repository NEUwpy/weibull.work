Role: executor
Plan: `coworker/plans/2026-07-10-study01-e4-formal-batch.md`
Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`
Codex review: `coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md`
Report: `coworker/reports/2026-07-10-study01-e4-formal-batch-hermes.md`

Follow the coworker protocol. Use implementation autonomy within the plan boundaries.

This is the second-round formal E4 batch. The goal is to finish the remaining E4 validation-suite work in one execution pass, then stop for Codex review.

First apply the Codex review corrections:

1. Make the active status handoff internally consistent at `S3_FORMAL_E4_AUTHORIZED`.
2. Update the current mainline commit reference to `ccacd35`.
3. Freeze and use the exact E4b and E4c combo lists from the plan.
4. Implement real L2/per-`n` reference evaluation.
5. Correct the formal manifest J1 formula text.
6. Keep E4b Option C as the formal reference-boundary track.
7. Keep NN boundary/off-grid evaluation as a separate `E4d_selector_extrapolation` diagnostic.
8. Keep E4c evaluation-only; continuous-space training is E3c and must stop for a new plan.

Then run the formal batch:

- E4a: full feature ablation, E3b-equivalent MLP config, 5-fold combo holdout, seeds 42/2026/3407.
- E4b: boundary reference robustness, exact 20-combo list, R=500, Default/L1/L2/L3/L4/L5/L6.
- E4c: off-grid evaluation-only robustness, exact 14-combo list, R=500, Default/L1/L2/L3/L4/L5/L6.
- E4d: selector extrapolation diagnostic trained only on original main-grid data and evaluated on E4b/E4c generated risk curves; if infeasible, write a skip-reason file with evidence.

Write formal artifacts only under:

`Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`

Do not write Ch7. Do not modify Ch1-Ch6, README, `00-05`, `draft-作者备注.md`, `E3c-E4-后续决策备忘.md`, or sealed E1/E2/E3a/E3b artifacts. Do not push.

Before stopping, update the Status/Handoff file with the exact report path, artifact path, current stage, blockers, and the next instruction for Codex. If the formal batch completes, stop for Codex review; do not self-authorize Ch7.

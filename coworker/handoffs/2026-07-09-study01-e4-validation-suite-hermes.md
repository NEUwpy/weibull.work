Role: executor
Plan: `coworker/plans/2026-07-09-study01-e4-validation-suite.md`
Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`
Report: `coworker/reports/2026-07-09-study01-e4-validation-suite-hermes.md`

Follow the coworker protocol. Use implementation autonomy within the plan boundaries.

This is the first gated Study/01 E4 validation-suite round. Design the E4a/E4b/E4c validation contract and run only a small smoke/pilot to verify feasibility, artifact schema, provenance, and metrics. Do not run full Formal E4, do not write Ch7 conclusions, do not modify Ch1-Ch6 or `00-05`, and do not put smoke outputs under `artifacts/formal/`.

Read `README.md`, the Study README, the Status/Handoff file, and the Plan before editing. Stop on any contradiction, leakage risk, formal/pilot boundary confusion, or need to decide whether a continuous-space experiment is actually E3c.

This task uses a resumable loop. At the start, read the Status/Handoff file and confirm the current stage is `S0_PLAN_READY` or `S1_FIRST_ROUND_RUNNING`. Before stopping for any reason, update the Status/Handoff file with the current stage, completed work, report path, artifact paths, next instruction, and blockers. If the first-round report is complete, set the stage to `S2_CODEX_REVIEW` and stop for Codex review; do not self-authorize full Formal E4 or Ch7 drafting.

# Study01 Remaining Experiments Plan

Goal:

Complete the original Study01 experimental gaps on branch `study01xu` with one bounded task per commit: E4d selector extrapolation, targeted delta upper-bound sensitivity, and real-data repeated holdout validation. R1–R3 are the only completion criteria. Cache-only teacher-feedback diagnostics are optional after the core closes; engineering-lifetime and direct-NN comparisons remain deferred.

Known facts:

- Base is `origin/main@c50ad0c`; active branch is `study01xu`.
- E1/E2, E3 existing-grid, E4a, and E4b/E4c reference-only artifacts are sealed and reusable.
- E3c remains deferred by the current Study01 decision record.
- Dormant E4d code exists, but subset cost output and E4 repeat-count handling require correction before execution; E3b model weights were not saved, so E4d must retrain under a frozen reproduction gate.
- The engineering quantile implementation already exists in `python/studies/common/metrics.py`.
- The detailed research and commit contract is `Study/01-study-MDM最小偏移量优化研究/07-剩余实验目标与规划.md`.

Boundaries:

- Allowed: Study01 code/tests/docs, new isolated Study01 artifacts, tracked real-data acquisition metadata, and coworker plans/reports/reviews.
- Not allowed: changing sealed artifacts in place; merging Study1.5 or Study02 into Study01; starting E3c automatically; using E4 truth, true parameters, or real holdout data as deployment inputs/standardization/tuning; result-driven expansion.

Executor autonomy:

- Choose the smallest implementation path that reuses existing Study01 and shared Monte Carlo infrastructure.
- Keep implementation and formal-run commits separate when this improves provenance.
- Stop rather than silently repairing or replacing authoritative inputs.

Phases:

1. Preflight and three separate infrastructure repairs: cost merge, 500-repeat feature reconstruction, and fail-closed/provenance gate.
2. E4d contract, E3b reproduction gate, implementation, formal execution, and separate review/status promotion.
3. Delta upper-bound contract, implementation, formal execution, and review.
4. Real-data selection contract, implementation, execution, and review.
5. Optional cache-only S1/S2 gate after R1–R3.
6. Joint validation and Study01 status synchronization.

Stop conditions:

- Input provenance, keys, row counts, or seed namespace fail validation.
- A task would overwrite sealed formal evidence.
- Leakage is detected.
- Real-data provenance or complete-lifetime semantics cannot be verified.
- A scope change would require E3c, Study02, or a new model competition.
- E3b evidence-matched reproduction gate fails: seed-42 sample-level results, three-seed pooled/by-`n` stability summaries, or archived split coverage exceed their pre-E4-truth frozen tolerances.
- Real-data admission or predeclared Weibull-fit gate fails; record `dataset-ineligible` and do not run method comparison.

Verification:

- Task-specific contract tests and formula recomputation.
- E4d baselines are provenance-labelled: Default `0.1`, frozen main-grid L1, main-grid L2 only for `n=7/10/20`, and any E4-selected L1/L2 named oracle-like references.
- The E3b reproduction gate matches available sealed evidence: seed 42 at sample level, all three seeds at pooled/by-`n` summary level, and folds against `split_report.csv`; it does not invent an unavailable three-seed sample-level baseline.
- Fifteen E4d fold/seed models are summarized as model-level repeats; repeated predictions for the same E4 sample are never pooled as independent observations.
- Targeted upper-bound results are conditional on the pre-hashed original `0.48/0.50` cohorts and do not claim whole-grid sufficiency.
- Real-data source identity, URL/version/license/hash, complete-lifetime semantics, `N>=60`, admission threshold, repeats/seeds, and train-fold-only scalers are frozen before relative results are viewed.
- Real-data NN evaluation uses all 15 E3b-contract retrained fold/seed selectors fixed before E4d/real-data outcomes are inspected; predictions on one split are model repeats, not independent observations. Engineering lifetime quantiles remain out of scope.
- Source/artifact hash checks and `git diff --check`.
- Exact run commands, environment, elapsed time, and skipped checks in each report.
- Independent plan and phase review with `APPROVE/REVISE/BLOCK` verdicts.

Report:

- Each executor report lists changed files, checks and exact results, skipped checks, deviations, blockers, and artifact provenance.
- Each completed small task is committed once; no unrelated changes are bundled.
- Each infrastructure bug is a separate commit. Implementation plus contract tests share one commit; formal artifacts plus executor report share one generation commit; independent review plus status promotion are a later commit.
- Every manifest distinguishes generation-time commit from the later sealed-artifact commit.

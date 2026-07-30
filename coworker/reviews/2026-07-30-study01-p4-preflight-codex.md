# Study01 P4 preflight Codex review

- Verdict: **REVISE**
- Reviewed baseline: `fde26eaa9613a0e79c8b8cced134d0e240625635`
- Reviewed tip: `d3eb31af189740ea3f5510039722686d4ae79d6d`
- Branch: `study01-p4-formal-compare`
- Review type: full first review
- Formal authorization: **not granted**

The direction is acceptable, but the current tip is not
`READY_FOR_P4_FORMAL_AUTHORIZATION`. Do not set
`P4_FORMAL_AUTHORIZED=True` and do not start the formal run.

## Findings

| ID | Priority | Finding | Required closure |
|---|---:|---|---|
| P4-R1 | P0 | `main()` only calls `main_holdout`, and `run_track_main_holdout()` only produces Direct-MLP rows. The other five methods and the other three tracks are not implemented. The current run must fail after expensive training when the six-method row-count check sees zero rows. | Implement all four frozen tracks and all six methods before authorization. Do not defer implementation until the authorization commit. Add an authorized-state, small-fixture end-to-end test that proves every track × method cell is populated and sealed. |
| P4-R2 | P1 | Authorization is a mutable Boolean only. The formal entry does not bind the independently approved parent/tip, clean worktree, fixed formal output path, complete track set, complete seed set, or a single active run. | Freeze an exact approved-parent/authorization contract; fail closed on HEAD, clean state, script/config/input hashes, fixed output path, `ALL_TRACKS`, `SEEDS`, and run lock. Recheck drift before final sealing. |
| P4-R3 | P1 | `verify_sample_keys_identical()` compares traditional methods with each other and learning models with themselves, but never learning against traditional. It can return `ok=True` for disjoint sample sets. It also incorrectly expects all combo-holdout folds to have the same test-key set; only seeds within the same fold should match. | Make alignment track-aware and multiplicity-aware. Validate each learning model against the traditional sample subset applicable to that fold/track, and add disjoint cross-type and swapped-fold negative tests. |
| P4-R4 | P1 | Mixed learning/traditional `paired_comparison()` indexes learning rows only by physical sample key even though they are repeated by fold/seed. This produces non-unique-index shape errors or ambiguous pairing. | Materialize or construct a clearly defined evaluation layer keyed by `(sample key, fold, seed)` and broadcast physical traditional estimates exactly once per required model context. Test learning↔traditional pairing with all 15 models and assert exact pair counts. |
| P4-R5 | P1 | The stated two-layer row contract is not represented by separate formal outputs. A single traditional row cannot carry fold-specific P99 failure loss on interpolation/extrapolation tracks, while learning rows have model-specific contexts. | Freeze separate estimation-row and evaluation-row schemas/counts, or an equivalent unambiguous representation. Traditional estimates may be computed once, but evaluation losses and paired rows must use the same fold-specific failure penalty as the learning method. |
| P4-R6 | P1 | P2 sample reconstruction risks using `study01_v1`; P2 v2 is sealed with `study01_p2_v1`. The other tracks are not implemented, so the correct namespace is not bound. | Bind each track to its sealed seed namespace and independently compare reconstructed sample-content hashes against its approved artifact before estimation. No default namespace may silently serve multiple tracks. |
| P4-R7 | P1 | Direct-MLP predictions are written with `failed=False` unconditionally. Non-finite or invalid predictions can become NaN loss instead of receiving the shared failure penalty. | Reuse the approved P3 prediction-validity/failure path, or reproduce it through a shared helper rather than a local permissive path. Add NaN, Inf, invalid support, and estimator exception tests through the production track function. |
| P4-R8 | P1 | Final sealing is incomplete. `seal_outputs()` claims to reject unexpected files but does not; only three top-level files are sealed, while checkpoints/subdirectories are omitted. Resume binds only commit, one input hash, and authorization Boolean. | Use a run context that binds track/method/fold/seed, full config, scripts, all inputs, sample/split hashes, authorization commit, and checkpoint content. Use an exclusive run lock and unique atomic temporary files. At completion, remove disposable checkpoints or recursively seal an exact allowlist of every retained artifact; independently verify the seal. |
| P4-R9 | P1 | Required P4 results are not produced: parameter Bias/RMSE/MAE, loss quantiles, failure/support rates, `n`/`beta`/generalization stratification, model stability, and paired win/loss/difference. Current `summaries.json` contains only a small J1/failure summary. | Produce the frozen P4 result tables from the evaluation layer without rerunning estimators, and cover their formulas and model-first aggregation with independent recomputation tests. |
| P4-R10 | P2 | The present 53 tests mostly exercise helpers. The only `main()` test checks that unauthorized execution raises. The model-first test uses identical model losses and does not prove pooled-first aggregation would differ. | Add non-vacuous negative tests and one authorized-state, tiny-fixture production-path test covering all tracks, methods, pairing, failures, resume, drift, output inventory, and seal verification. |

## Independently verified

- `HEAD == origin/study01-p4-formal-compare == d3eb31af189740ea3f5510039722686d4ae79d6d`.
- Worktree was clean before and after review.
- `git diff --check fde26eaa..d3eb31af` passed.
- P4 suite: `53 passed`.
- Study01 suite: `183 passed, 1 warning`.
- Unauthorised script entry failed before computation as intended.
- No formal P4 output was generated and no authorization value was changed.

## Revision boundary

The next round may change only P4 implementation, P4 tests, this P4 report,
and the minimum existing Study01 status text needed to remain truthful.
Do not run the formal experiment, alter the frozen method set, tune from smoke
rankings, enter P5+, or edit the external manuscript.

Return a compact mapping:

```text
finding ID -> fixing commit -> changed files -> targeted evidence
```

Use small auditable commits. Stop at a clean, pushed exact tip with
`P4_FORMAL_AUTHORIZED=False` and status
`READY_FOR_INDEPENDENT_REVIEW`.

# Task Plan: Study01 input representation pilot

Goal:

Produce a small, auditable Study01 comparison that answers three group-meeting questions: under the same fold, seed, 26-point loss-curve target, and selected-J1 evaluation, (1) how does the current 13-feature Vector-MLP compare with a model fed a fixed-width representation of the sorted raw sample, (2) do feature inputs erase sample-size effects when explicit `n` is removed, and (3) does joint training on `n=7/10/20` hurt any sample-size group relative to three separately trained, known-`n` specialist models?

Known facts:

- The group meeting is 2026-07-20 evening; the pilot is required before it.
- Existing E3b caches contain 45,000 sample keys/features and aligned 26-point risk curves.
- Formal E3b uses 5-fold full-combo holdout, seed 42, a `(256,128,64)` MLP, train-only feature/target scaling, and selected true J1 evaluation.
- Prior Research09 found raw and feature inputs similar for direct parameter estimation, but that result does not answer Study01's delta-risk-curve task.

Boundaries:

- Allowed: add one Study01 pilot script, pilot-only artifacts outside `artifacts/formal/`, a concise standalone Study01 validation document, a concise execution report, tests for representation/split/evaluation contracts, and update the group-meeting preparation document with the result.
- Not allowed: modify or overwrite formal E3/E4 artifacts, rerun the 1.17M-call Monte Carlo scan, upgrade the result to a formal multi-fold/multi-seed claim, or change manuscript claims automatically.

Executor autonomy:

- Choose the smallest implementation consistent with existing E3b patterns.
- Use deterministic sorting plus padding/mask (or an equally auditable permutation-invariant representation) to handle `n=7/10/20` in one raw-input model.
- Reuse cached sample keys/risk curves and the formal sample reconstruction function.
- Add one matched 12-feature ablation that removes only explicit `n`; use per-`n` J1 to assess whether feature encoding hides the small-sample disadvantage.
- Add three 12-feature specialist models, each trained and scaled only within one known sample size, then route held-out samples by their observed `n`. Compare the routed ensemble with the unified 12-feature model to isolate the pooling choice, and with the current unified 13-feature model for operational relevance.

Stop conditions:

- Stop if cached keys or 26-point targets do not align, the held-out combos differ between representations, true parameters leak into model inputs, or formal artifact paths would be overwritten.
- Stop and report if runtime threatens the group-meeting deadline rather than expanding scope.

Verification:

- Contract tests for fixed-width raw representation, padding mask, no forbidden input fields, identical fold membership, and selected-J1 calculation.
- Run the one-fold/one-seed pilot and record pooled/per-n J1 for full features, unified features without `n`, routed known-`n` specialists, and raw input; also record runtime, training iterations, delta-selection diagnostics, and explicit pilot-only limitations.
- Run `git diff --check` and review the actual diff/artifacts.

Report:

- `coworker/reports/2026-07-19-study01-input-representation-pilot.md`
- Final reviewer verdict: `APPROVE / REVISE / BLOCK`.

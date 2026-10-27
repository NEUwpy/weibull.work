# Study/02 G3 — staged A-E1 execution state machine (deadlock fix) executor report

Branch: `claude/study02-a-20260715`. Tip: `0beda20` (local; 2 commits pending push -- outbound
network to github was intermittent this relay). Scope (per the relay-mode directive): implement
ONLY the minimum special-purpose staged control to make the real frozen A-E1 advance
stage-by-stage, reuse the existing scheduler/journal, add no general workflow framework or new
infrastructure, then a production-equivalent sealed smoke. **Stop** before A-E3/A-E2,
accredit-authorize, test unseal, or formal. Final status:
`implementation complete, awaiting unified Codex preflight review; formal not authorized`.

## Context (the deadlock Codex flagged)

A-E1 is 349 staged fits. `run_module` stops at the first placeholder (fit #141, `selected_top_*`);
`build_module_selection` derived EVERY stage's specs at once and required them ALL terminal before
publishing a single trace -- so stage-2 (placeholder) never executed, no trace, `formal-staged` had
no authority: a deadlock. The relay-mode fix is a minimum staged state machine on top of the
existing scheduler/journal.

## Key correctness finding (do not skip)

The frozen A-E1 **plan order is route-interleaved**, not stage-then-both-routes (verified by
enumeration):

```
stage1 F2 idx 105-140 | stage2 F2 141-176 | winner_retrain F2 177-226
stage1 V  idx 227-262 | stage2 V 263-298 | winner_retrain V 299-348
stage1-fully-before-stage2 = False
```

So when stage2 F2 is reached, stage1 V is NOT yet terminal. The first draft built both-routes
receipts at once (commit `8d6abd4`) -- that would deadlock. Fixed (`15ffcab`): receipts are
**per-route** (one route's architecture/stage2 decision per receipt); the orchestrator tracks
`stage1_by_route` / `stage2_by_route` and builds each route's receipt when that route's stage2 /
winner-retrain is first reached. The F2-vs-V baseline (which needs both routes) is still derived
at the very end by the existing `resolve_a_e1_staged_selection`, once every fit is terminal.

## What was implemented (minimum, reusing scheduler/journal)

- `_a_e1_fit_stage(plan_row)` -- classifies rows into concrete / stage2 / winner_retrain.
- `build_a_e1_stage1_selection(route=...)` -- per-route immutable PARTIAL selection trace/receipt/
  ledger over one route's architecture decision; derives `selected_top_1..4`. Does not require
  stage2 / winner-retrain / other-route evidence. Production scores from checkpoints; tests inject
  `score_fit`.
- `build_a_e1_stage2_selection(route=..., top4=...)` -- per-route partial selection over one route's
  stage2 decision; maps the winner `selected_top_{slot}:{opt}` to concrete architecture (top4[slot])
  + optimizer + frozen loss.
- `_resolve_stage2_plan_row` / `_resolve_winner_retrain_plan_row` -- concretize placeholder plan
  rows from the route's receipt at execution time (the immutable plan is never rewritten).
- `run_a_e1_staged(...)` -- drives the module: claim -> train -> record via the existing scheduler
  journal; concrete/stage1 run directly; stage2 concretizes from the stage1 top4 receipt;
  winner-retrain from the stage2 winner receipt. After every fit is terminal, the EXISTING
  `build_module_selection` (now unblocked) publishes the final trace and its internal
  `resolve_a_e1_staged_selection` derives F2/V + final aliases + the staged ledger. A partial run
  (max_fits / smoke) skips the final step and returns the execution result.

This adds only the two per-route staged receipts + the orchestrator; it reuses the scheduler
(claim/execute/record/journal), the selection engine, and the staged resolver throughout. No
general workflow framework, no new infrastructure.

## Checks and exact results

```
$ python -m pytest <9 direct-related files> -q -m "not slow" \
    -k "not emits_v2... and not includes_failed..."
222 passed, 6 deselected        # 218 prior + 4 new staged unit tests
$ python -m compileall -q code/study02a/formal_executor.py   # exit 0
```

New staged unit tests (real frozen matrix, `score_fit`-injected, no training):
- `test_build_a_e1_stage1_selection_publishes_partial_receipt_and_top4` (per route, F2 + V)
- `test_build_a_e1_stage2_selection_maps_winner_to_concrete` (per route)
- `test_staged_plan_row_resolvers_concretize_and_fail_closed`
- `test_a_e1_fit_stage_classifies_plan_rows`

`@slow` production-equivalent smoke:
- `test_run_a_e1_staged_executes_real_fits_via_scheduler` -- `run_a_e1_staged` drives REAL fits
  through the scheduler journal on the frozen A-E1 matrix (real training -> canonical checkpoint ->
  evidence; **no monkeypatch of winner/trace/authority/provenance**), `test_access_count == 0`,
  partial run via `max_fits`. Collects clean; `@slow` + clean-code-gated (runs on Codex's committed
  snapshot).

Materialize-gated / clean-code suites (formal_scheduler 28 + build_module_selection 2) were proven
on a clean `code/` tree in the prior relay and are unaffected by these additive changes.

## Honest limitations (not overclaiming)

- The full-chain smoke (stage1 -> ... -> winner-retrain -> F2/V -> final receipt) is **infeasible**
  on the frozen 349-fit matrix in a test timeframe (winner-retrain trains at up to 400000 rows).
  The `@slow` smoke proves the orchestrator integrates with the scheduler and executes real fits on
  the real matrix; the staged receipts are reached only at fit counts that are the formal-launch
  scope. The deadlock-breaker mechanism itself is unit-tested per-route.
- The orchestrator's end-to-end behavior on the FULL real matrix (all 349 fits, F2/V decision,
  final aliases) is verified by composition (per-route unit tests + the existing
  `resolve_a_e1_staged_selection` F2/V tests) but NOT by a single full-matrix run in this relay.
- `formal_state` bundle version was aligned v1 -> v3 (`0201172`, prior relay) to match the
  production builder; the unified review should confirm v3 as canonical.
- No A-E3/A-E2 concretization, no accredit-authorize execution, no test unseal, no formal launch
  (all out of scope by directive).

## Boundary held

No real formal A-E1 launch; no oracle approval created; no `formal-accredit-authorize` execution;
no test read (`test_access_count == 0`); no frozen matrix/config/metric/rule change; no public
trace/receipt/bundle field-schema change; no new infrastructure / general workflow framework.

## Status & next

`implementation complete, awaiting unified Codex preflight review; formal not authorized`.
Commits this relay: `46d02a7` (stage1 receipt) -> `8d6abd4` (orchestrator + stage2, both-routes
draft) -> `15ffcab` (per-route fix) -> `0beda20` (partial-run guard + smoke). `00-A` / `03-A`
synced to the real tip + state. Push pending network recovery.

— Claude (executor), 2026-07-19

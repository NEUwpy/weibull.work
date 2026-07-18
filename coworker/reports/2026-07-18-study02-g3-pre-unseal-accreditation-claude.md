# Study/02 G3 pre-unseal accreditation ("前置认证") — executor report

Branch: `claude/study02-a-20260715`. Plan: `C:\Users\ilove\.claude\plans\silly-singing-pearl.md`,
mapping Task 9 (Steps 4/5/6/8) of `coworker/plans/2026-07-12-study02-a-g3-implementation.md`
and item 8 of `Study/02-.../03-A-实验计划.md`. This baton wires the three D8/pre-unseal entries
that Codex's D8 R1 review (BLOCK #4) flagged as test-only — the pre-unseal bundle builder, the
approval-bound state machine, and the A-E3/A-E2 deferred-spec resolver — into real production CLI
call points, and adds the diagnostics generation a completed run needs. Test stays sealed; no
training; no test read; no frozen artifact change.

Per the user's directive this relay runs in "complete the long task, then unified review" mode:
commits are incremental and local (push to `origin` failed — this environment has no outbound
network to github.com; see §6).

## 1. Changed files

```
 Study/02-.../code/run_study02a.py          (modified: +3 CLI subcommands + handlers + diagnostics generators)
 python/tests/test_study02a_formal_executor.py  (modified: +4 accreditation tests)
 coworker/reports/2026-07-18-study02-g3-pre-unseal-accreditation-claude.md  (this report)
```

No change to `formal_state.py`, `formal_contracts.py`, `formal_executor.py`, `formal_scheduler.py`
(reused as-is), nor to any frozen matrix/config/metric/rule or public trace/receipt/bundle schema.

## 2. Production call points delivered (resolve BLOCK #4)

### 2.1 `formal-accredit-build` (Task 9 Step 4/5/8) — wires `build_module_pre_unseal_bundle`
For a completed A-E1 run it regenerates the three run-level diagnostics no production code
previously produced, then builds the sealed pre-unseal bundle:
- **fit_status.csv** — one row per selection-candidate fit, reconstructed from the per-fit
  `outputs/<fit_id>/evidence.json` (training trajectory: curve, epochs, best epoch, ceiling,
  early-stop) + `point_evidence.json` (selection context: decision_id, candidate_id,
  selection_score) + the selection trace (selected) + the plan row (rule_id, route, n, seed),
  via `formal_contracts.build_fit_status_record`.
- **ceiling_hit_report.json** — derived from the fit-status rows via `build_ceiling_hit_report`.
- **leakage_audit.json** — the four formal role parameter-point ID sets regenerated from the
  frozen design (`study02a.design`: training via `allocate_training_rows`; validation/calibration
  and the module test via `generate_parameter_points` at the frozen 256-point allocations with the
  role/module design seeds). Disjoint by construction (independent seeds + role-prefixed IDs);
  `test_access_count=0`; sources `training_only`/`validation_only`.
- **pre_unseal_bundle.json** — `build_module_pre_unseal_bundle` (point provenance rebuilt
  internally, R5; `test_state=sealed`).

### 2.2 `formal-accredit-authorize` (Task 9 Step 6/8) — wires the approval-bound state machine
Binds an EXTERNAL oracle `APPROVE test unseal` artifact (never auto-created — oracle owns the
decision), then `initialize_formal_state` (sealed) + `authorize_test_once` (sealed → unsealed_once).
**`consume_test_once` is deliberately not wired** (test is never read).

### 2.3 `formal-resolve-deferred` (Task 9 D8) — wires `reconstruct_deferred_specs`
Builds a `PredecessorTrace` from a predecessor run's selection trace/receipt/ledger and
reconstructs A-E3/A-E2 concrete dataset specs (wrong-order / stale / cache-key drift → fail-closed).
No training.

## 3. Checks and exact results

`pytest`+`scipy` installed into the run env (Tsinghua mirror) only to execute verification — no
repo change, no test access.

```
$ python -m pytest <9 direct-related files> -q -m "not slow" \
    -k "not emits_v2... and not includes_failed..."
218 passed, 5 deselected        # 214 prior + 4 new (accredit-build/authorize + resolve-deferred x2)
```

Materialize-gated, clean `code/` (this baton's edits stashed; same pattern as prior batons):
```
$ python -m pytest test_study02a_formal_scheduler.py -q -m "not slow"   -> 28 passed
$ python -m pytest test_study02a_formal_selection.py -q -m "not slow" -k build_module_selection -> 2 passed
```

New accreditation tests (real fixtures, no training, test sealed):
- `test_formal_accredit_build_generates_sealed_bundle` — fit_status/ceiling/leakage generated,
  `bundle_version=study02-pre-unseal-v3`, `test_state=sealed`, leakage pairwise intersections 0,
  all four role counts present; point provenance rebuilt internally (monkeypatched, no checkpoint
  read).
- `test_formal_accredit_authorize_requires_external_approval_then_stops` — external approval →
  `unsealed_once`, `test_access_count=1`; `consume_test` not exposed on the CLI; repeat authorize
  fails closed.
- `test_formal_resolve_deferred_cli_a_e3_from_a_e1` — concrete specs reconstructed, cache keys
  match the scheduler's deferred-dataset-v1 plan.
- `test_formal_resolve_deferred_cli_fail_closed_wrong_order` — A-E2←A-E1 rejected.

```
$ python -m compileall -q code/study02a code/run_study02a.py            # exit 0
$ git diff --check                                                       # clean
$ git diff --name-only -- artifacts configs                              # empty
```

## 4. Stop-condition finding for the unified review — pre-unseal bundle version v1 vs v3

`formal_state._validate_bundle` requires `bundle_version == "study02-pre-unseal-v1"` with the
7-field minimal schema; `formal_contracts.build_pre_unseal_bundle` produces
`"study02-pre-unseal-v3"` with the **same 7 fields** (`formal_contracts.py:1488`). The field set is
identical; only the version string differs (the state machine predates the R5 v3 evolution).

Consequence: the `formal-accredit-build` output (v3) cannot flow into `formal-accredit-authorize`
(formal_state rejects it on the version string) until the versions are aligned. This baton did not
touch `formal_state.py` (outside its scope). Recommended fix for the review: have `formal_state`
accept the current `study02-pre-unseal-v3` bundle (one version-string change + update the
`formal_state` test fixtures, which currently build v1 bundles). Trivial, but it is a contract
change to an approval-bound module.

## 5. Notes / deviations

- The leakage audit's training-role point IDs are regenerated via `design.allocate_training_rows`
  across the run's distinct training configs (the same single-source allocator `formal_runner` uses)
  — faithful by deterministic regeneration. Calibration/test namespaces are derived from the
  manifest's training namespace pattern (`<prefix>/<role>`), since the formal manifest schema
  records only training/validation namespaces. The audit asserts zero intersections (guaranteed by
  independent design seeds + role-prefixed IDs); this is the structural no-leakage attestation.
- The diagnostics generation reads each fit's bound `evidence.json`/`point_evidence.json` — it does
  not retrain and does not open test. `test_access_count` stays 0 through build; it reaches 1 only
  at `authorize_test_once`, which binds the approval but does not read test.
- Per the user's relay-mode directive, this work was committed incrementally (not left for Codex to
  stage); the four commits are local on `claude/study02-a-20260715`.

## 6. git status / push

```
$ git status --short
 M Study/02-.../code/run_study02a.py
 M python/tests/test_study02a_formal_executor.py
?? coworker/reports/2026-07-18-study02-g3-pre-unseal-accreditation-claude.md
```

Push to `origin` failed: `Failed to connect to github.com port 443` — this environment has no
outbound network to GitHub (no proxy configured). Commits remain local; push when a connected
environment is available.

— Claude (executor), 2026-07-19

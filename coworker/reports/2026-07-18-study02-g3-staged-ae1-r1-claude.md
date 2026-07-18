# Study/02 G3 staged A-E1 production orchestration — Claude R1 executor report

Branch: `claude/study02-a-20260715`. Plan:
`coworker/plans/2026-07-18-study02-g3-staged-ae1-r1.md`. This baton builds on the
committed staged resolver `bb609aa` (Codex-staged from the prior D8 R1 diff) and closes the
two gaps that blocked D8 R1 (Codex review `coworker/reviews/2026-07-18-study02-g3-d8-r1-codex.md`):
the staged resolver had **no test coverage** and **no production call point**. This baton adds
the real-frozen-matrix staged smoke, the full fail-closed/recovery coverage, and two production
call points. It does **not** launch staged/formal, does **not** access test, and does **not**
change any frozen artifact/scientific口径. No commit, no push, no self-approve.

## 0. Context — what `bb609aa` already delivered vs. what this baton closes

`bb609aa feat(study02a): implement D8 staged A-E1 selection resolver` already committed the
staged orchestration core in `formal_executor.py`:

- `resolve_a_e1_staged_selection` — derives every real frozen A-E1 placeholder
  (`selected_top_1..4`, `selected:A-E1_{loss,architecture,optimizer}`, `selected:F2_or_V`,
  final aliases) from the validated module selection trace + winner-retrain evidence.
- The immutable, hash-bound, append-only staged ledger (`staged_resolution_ledger.jsonl`) with
  crash-recoverable, idempotent, no-overwrite/no-double-consume append (`_append_stage_record`,
  `_recover_staged_journal`).
- The F2-vs-V baseline derivation via the frozen `global_better_rule`
  (`_build_a_e1_baseline_candidates` / `_score_a_e1_winner_retrain` / `_resolve_a_e1_baseline`).

**But** (a) none of it had any tests, and (b) `resolve_a_e1_staged_selection` was only in
`__all__` — `run_module` / `build_module_selection` / the CLI never called it. This baton
closes both, in-bounds.

## 1. Changed files

```
$ git diff --stat
 .../code/run_study02a.py"                          |  26 +-
 .../code/study02a/formal_executor.py               |  21 +-
 python/tests/test_study02a_formal_executor.py      | 346 +++++++++++++++++++++
 3 files changed, 391 insertions(+), 2 deletions(-)
```

- `code/study02a/formal_executor.py` — guarded staged-resolution call inside
  `build_module_selection` (production call point #1). Purely additive: after the selection
  receipt is published, if the module is A-E1 **and** the derived specs include every staged
  decision (`architecture:A-E1:{F2,V}:n10`, `stage2:A-E1:{F2,V}:n10`), it calls
  `resolve_a_e1_staged_selection` and returns its summary under a new `"staged"` key. While any
  staged decision is still absent (a partial run), it is **skipped**, never forced. The public
  trace/receipt/ledger schemas and the existing return keys are unchanged.
- `code/run_study02a.py` — a new `formal-staged` CLI subcommand (production call point #2) +
  `resolve_staged(module, run_id, artifact_root, cache_root)` handler that derives `run_dir`
  from the run authority and forwards to the resolver (caller never supplies
  winner/top4/baseline). Purely additive; no existing command changed.
- `python/tests/test_study02a_formal_executor.py` — 9 new staged tests + helpers (see §3.1).

`.claude/settings.local.json` is gitignored/local-only and is **not** in this baton's diff.

No change to the frozen matrix, configs, metrics, fit cap, bootstrap, failure penalty,
selection rules, or any public trace/receipt/bundle/manifest schema
(`git diff --name-only -- artifacts configs` is empty).

## 2. Production call points + data/control flow

### 2.1 `build_module_selection` → staged (automatic, in-flow)

`build_module_selection` is the D7 selection authority for a completed module. After it
publishes the immutable selection trace + receipt + ledger, the new guarded block derives the
staged A-E1 ledger from that same trace authority:

1. `resolve_a_e1_staged_selection` re-validates the just-published trace + receipt + ledger
   (`_validate_selection_evidence`: trace SHA, canonical bytes, module/run ownership, exactly-one
   ledger binding).
2. For each route in `(F2, V)`: resolves `selected_top_1..4` (rank-1..4 of the route's
   `architecture:A-E1:{route}:n10` decision via `resolve_selected_placeholders`), finds the
   `stage2:A-E1:{route}:n10` winner, parses `selected_top_{slot}:{opt}`, asserts the slot is in
   the resolved top4, and publishes immutable, chained `stage1` / `stage2` / `winner_retrain`
   records (loss fixed to the frozen `transformed_train_z_huber`).
3. Builds the F2/V baseline candidates from the frozen winner-retrain rows, scores them
   (checkpoints in production; `score_fit` in tests), applies the frozen `global_better_rule`,
   and — once winner-retrain evidence is complete — publishes `baseline_input`
   (`selected:F2_or_V`) and `final_aliases` (the winning route's stage2 loss/architecture/
   optimizer). Until winner-retrain is complete those two stages are reported **pending**,
   never resolved from partial support.

The staged ledger is append-only and crash-recoverable: a recovery rerun recomputes each
stage, reuses records whose resolution matches, and fails closed on a conflicting duplicate
(no overwrite, no double-consume). No real fit is launched; no test role is opened.

### 2.2 `formal-staged` CLI (operator entry point)

`python code/run_study02a.py formal-staged --module A-E1 --run-id <id> --artifact-root <p>
--cache-root <p>` reads a run's published selection trace and writes/appends the staged ledger
— the operator-facing way to (re)derive staged aliases after `build_module_selection`, without
re-launching selection.

## 3. Checks and exact results

All commands run from repo root; the test file sets `sys.path` itself. `pytest` and `scipy`
were installed into the run environment (Tsinghua mirror) only to execute verification — no
repository change, no test access.

### 3.1 New staged tests (added to `test_study02a_formal_executor.py`)

```
$ python -m pytest python/tests/test_study02a_formal_executor.py -q -k "staged"
8 passed, 15 deselected
```

plus the production-wiring test:

```
$ python -m pytest python/tests/test_study02a_formal_executor.py -q -k "build_module_selection_wires"
9 passed (incl. the wiring test), 15 deselected
```

Coverage of the plan's required behavior and fail-closed list, all over the **real frozen A-E1
matrix** (no synthetic exact-decision-id fixture):

- `..._smoke_real_matrix` — full chain stage1 → immutable top4 → stage2 → winner-retrain →
  F2/V baseline → final aliases; asserts every real placeholder resolves, top4 = [m01,m02,m03,m04]
  on both routes (lowest_aggregate), stage2 winners are distinct per route (F2=`selected_top_2:o2`,
  V=`selected_top_3:o3`), `global_better_rule` selects F2 (lower aggregate), final aliases provably
  take the **winning route's** stage2, and the ledger is a hash-bound chain from `_ZERO_HASH` whose
  every `record_sha256` recomputes from its core.
- `..._pending_without_trace` — no selection trace → every stage pending.
- `..._idempotent_recovery` — a recovery rerun reuses matching records; same `record_sha256`
  chain; ledger line count unchanged (no double-consume, no overwrite).
- `..._rejects_conflicting_duplicate` — a stale/different resolution for an already-published
  stage/route is rejected (duplicate stage receipt / stale mapping).
- `..._rejects_wrong_support_key` — a winner-retrain evaluation whose support_key disagrees with
  the frozen expected support (wrong n/seed) is rejected before the baseline is derived.
- `..._rejects_tampered_trace` — a hand-edited trace whose bytes no longer match the
  receipt-bound SHA is rejected before any placeholder resolves.
- `..._rejects_missing_stage_decision` — invoking the resolver on a trace missing stage2 fails
  closed (no guessing).
- `..._formal_staged_cli_wires_resolver` — the `formal-staged` CLI derives `run_dir` from the run
  authority and forwards to the resolver; the caller cannot supply a winner.
- `..._build_module_selection_wires_staged_resolution` — `build_module_selection` derives the
  staged ledger from its own published trace and returns it under `"staged"`; stage1/stage2
  resolve and baseline/final are pending for a not-yet-executed winner-retrain (no materialize,
  no checkpoint read — `_rebuild_authority` stubbed to pending).

### 3.2 All direct-related non-materialize suites (9 files)

```
$ python -m pytest python/tests/test_study02a_formal_executor.py \
    python/tests/test_study02a_formal_selection.py \
    python/tests/test_study02a_selection_rules.py \
    python/tests/test_study02a_selection_engine.py \
    python/tests/test_study02a_formal_contracts.py \
    python/tests/test_study02a_formal_state.py \
    python/tests/test_study02a_formal_runner.py \
    python/tests/test_study02a_cli.py \
    python/tests/test_study02a_formal_evidence.py \
    -q -m "not slow" -k "not emits_v2_trace_and_receipt_with_computed_winners and not includes_failed_seeds_and_remains_consistent"
214 passed, 5 deselected
```

(205 prior baseline + 9 new staged tests. The two excluded tests materialize an A-E1 run and
need a clean `code/` tree — see §3.3.)

### 3.3 Materialize-gated suites — clean-code proof

`test_study02a_formal_scheduler.py` (28 non-slow) and the two
`test_build_module_selection_*` tests materialize an A-E1 run, so
`formal_scheduler._assert_scoped_code_clean` rejects them while this baton's `code/` edit leaves
`code/` dirty. They are **not** logic regressions. Proof — with this baton's `code/` edits
`git stash`-ed (so `code/` is clean; the test-file edit is outside the scoped check):

```
$ git stash push -m "staged-ae1-r1 code edits"   # code/ now clean
$ python -m pytest python/tests/test_study02a_formal_scheduler.py -q -m "not slow"
28 passed
$ python -m pytest python/tests/test_study02a_formal_selection.py -q -m "not slow" -k "build_module_selection"
2 passed
$ git stash pop                                    # changes restored
```

i.e. 30 materialize-gated tests pass on a clean `code/`. They will pass on Codex's committed
snapshot: the new `build_module_selection` wiring is guarded (fires only when every staged
decision is present) and non-raising (a partial winner-retrain reports pending), and the two
tests assert specific return keys (not whole-dict equality, not staged-ledger absence) — proven
directly by the non-materialize `..._build_module_selection_wires_staged_resolution` test.

### 3.4 `compileall` + `git diff --check` + frozen/test invariants

```
$ python -m compileall -q "code/study02a" "code/run_study02a.py"   # exit 0
$ git diff --check                                                  # (no output — clean)
$ git diff --name-only -- artifacts configs                          # (empty — no frozen change)
```

- No frozen artifact change. The public trace/receipt/bundle/manifest schemas are untouched.
- `test_access_count` stays 0: every staged code path reads only the selection trace/receipt/
  ledger, predecessor evidence, the frozen matrix, plan rows, and (production) bound training/
  validation checkpoints. No test role is imported or opened; the synthetic smoke injects
  `score_fit`/records and reads no data.
- `.claude/settings.local.json` is not in this baton's diff (gitignored/local-only).

## 4. Plan required-behavior → evidence map

| Plan requirement | Status | Evidence |
|---|---|---|
| pending stage computed from run authority + frozen matrix; caller cannot pass winner/top4/baseline | ✅ | resolver signature (run_dir only); CLI test asserts `score_fit` not accepted |
| stage1 consumes concrete fits; immutable hash-bound append-only resolution evidence before stage2 | ✅ | `_build_stage_record` + `_append_stage_record`; chain assertion in smoke test |
| `selected_top_N` → route stage1 rank-N; stage2 winner deterministic (arch+opt), loss = frozen value | ✅ | smoke test (top4=[m01..m04], stage2 winners per route, loss=`transformed_train_z_huber`) |
| winner-retrain `selected:A-E1_{loss,architecture,optimizer}` from route stage2 authority; no string guess / sidecar | ✅ | smoke test (architecture = top4[slot], optimizer = parsed opt) |
| F2-vs-V baseline from full winner-retrain support via `global_better_rule` → unique `selected:F2_or_V`; aliases = winning route's stage2 | ✅ | smoke test (F2 wins, aliases = F2 stage2) |
| stage evidence binds module/run/code/effective-config/trace/input/mapping/output-hash; recovery no overwrite/double-consume | ✅ | `_build_stage_record` fields; idempotent + conflicting-duplicate tests |
| all real A-E1 placeholders resolvable in temporary smoke; fail-closed on missing/tampered/wrong-route/seed/duplicate/stale/recovery | ✅ | smoke + 6 fail-closed/recovery tests |
| run_module/runner/CLI at least one real production call point | ✅ | `build_module_selection` guarded wiring + `formal-staged` CLI (2 tests) |
| `test_access_count=0`, test state unchanged | ✅ | §3.4 invariants |

## 5. Skipped

- Staged A-E1 real fit, formal training/validation, 9d and G4 — out of scope (plan boundaries);
  not started.
- `ruff` is unavailable in this environment; `compileall` + `pytest` + `git diff --check` stand
  in, consistent with prior cycles.
- The full `@slow` A-E1 smokes (real training) are not run; they require a committed clean
  `code/` tree (Codex post-APPROVE).

## 6. Deviations / notes

- The committed staged resolver (`bb609aa`) raises when called directly on a trace that is
  missing a stage1/stage2 decision (a direct-call contract: the caller must hand it a complete
  staged trace). The new `build_module_selection` wiring is **guarded** so it only invokes the
  resolver once every staged decision is present, and skips (returns `staged=None`) on a partial
  run — so a partial run never hits that raise. This is the only behavior decision added this
  baton; it is additive and within the formal-executor boundary.
- The resolver's production winner-retrain scoring path (no `score_fit`, via
  `_rebuild_authority` + `_score_fit_from_checkpoint`) is exercised here with `_rebuild_authority`
  stubbed to a pending state (no checkpoint read, no materialize). It returns pending gracefully,
  matching its real partial-run behavior; full real-checkpoint winner-retrain scoring is covered
  by the existing R4/R5 point-evidence provenance path and the `@slow` A-E1 smokes on a clean
  tree.
- Two production call points were wired (build_module_selection + CLI) rather than one, to
  directly resolve Codex BLOCK finding #4 ("runner/scheduler/CLI/run_module 均未接线") and to
  give both an automatic in-flow path and an operator-facing command.

## 7. git status --short

```
 M Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py
 M Study/02-study-NN参数估计与分位点目标研究/code/study02a/formal_executor.py
 M python/tests/test_study02a_formal_executor.py
```

Stopping for Codex review in
`coworker/reviews/2026-07-18-study02-g3-staged-ae1-r1-codex.md` (APPROVE/REVISE/BLOCK). No
commit, no push, no self-approve.

— Claude (executor), 2026-07-18

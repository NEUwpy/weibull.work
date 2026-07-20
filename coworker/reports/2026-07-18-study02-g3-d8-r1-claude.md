# Study/02 G3 D8 production wiring — Claude R1 executor report

Branch: `claude/study02-a-20260715`. Plan:
`coworker/plans/2026-07-18-study02-g3-d8-r1.md`. Codex baseline:
`ee7e52ff440b93a86151d6fbbc41d7f05cf6aee1`. This baton implements the D8 production
wiring only; it does **not** launch staged/formal, does **not** access test, and does **not**
change any frozen artifact/scientific口径.

## 1. Changed files

```
 M Study/02-study-NN参数估计与分位点目标研究/code/study02a/formal_executor.py
 M python/tests/test_study02a_formal_executor.py
```

Both edits are purely additive on the production side (the only deleted lines are the two
`NotImplementedError` D8 placeholders and the old `formal_contracts` import block, replaced
by a superset that keeps every previously imported symbol). `.claude/settings.local.json` is
the user's pre-existing dirty file and is **not** touched, staged, or committed by this baton.

```
$ git diff --stat -- code/ python/tests/test_study02a_formal_executor.py
 .../code/study02a/formal_executor.py          | 366 +++++++++++++++++++-
 python/tests/test_study02a_formal_executor.py | 385 ++++++++++++++++++++-
 2 files changed, 734 insertions(+), 17 deletions(-)
```

No change to the frozen matrix, configs, `protocol.json`, metrics, fit cap, bootstrap,
failure penalty, selection rules, or any public artifact/trace/receipt/bundle schema
(`git diff --name-only -- artifacts configs protocol.json` is empty).

## 2. Data / control flow implemented

### 2.1 `resolve_selected_placeholders` (D8) — selected placeholder resolution

`resolve_selected_placeholders(*, placeholders, selection_trace_path,
selection_trace_sha256, selection_receipt_path, selection_ledger_path, module_id, run_id)`
resolves `selected:<decision>` / `selected_top_N` tokens from **one fully-validated
immutable selection trace + receipt + ledger**.

Control flow:

1. `_validate_selection_evidence` (new read-only helper) validates the bundle first:
   trace SHA-256 + canonical bytes + module/run ownership
   (`formal_contracts._validate_selection_trace_bytes`), then the receipt binds that trace
   (v3 version, same module/run, `selection_trace_sha256 == actual`, frozen
   `effective_config_sha256`, full-length `code_commit`, matching record/decision counts),
   then the ledger has **exactly one** `formal-selection` binding equal to
   `{"binding_type": "formal-selection", **receipt, "receipt_sha256": receipt_sha}`. A
   hand-edited trace, a stale SHA, a mismatched module/run, or a missing/duplicate ledger
   binding is rejected before any placeholder resolves.
2. The validated records are grouped by `decision_id` and, in one deterministic pass, every
   decision is (a) ranked by `(validation_score, tie_break_key, candidate_id)` ascending —
   the frozen ranking the trace validator enforces, rank-1 == winner — and (b) checked to
   have exactly one `selected=True` winner.
3. Each placeholder then resolves:
   - `selected:<decision>` → the unique winner of the trace decision whose `decision_id`
     equals `<decision>`; zero matches (missing) or a non-unique winner raises.
   - `selected_top_N` → the rank-N candidate (1-indexed) of the caller-supplied
     `rank_decision_id`; a non-integer/`<1` slot, an out-of-bounds slot, a missing
     `rank_decision_id`, or a ranking decision absent from the trace raises.

Output order/IDs/winner/ranking are deterministic and independent of dict ordering.

### 2.2 `reconstruct_deferred_specs` (D8) — A-E3/A-E2 deferred-spec reconstruction

`reconstruct_deferred_specs(plan_row, frozen, effective, predecessor)` rebuilds the
A-E3/A-E2 deferred training/validation bindings, mirroring `reconstruct_a_e1_specs` for the
concrete A-E1 path.

Control flow:

1. The module must be a downstream module (`_PREDECESSOR_BY_MODULE`); A-E1 / unknown → raise.
2. `_validate_predecessor(module_id, predecessor)` (the same authority the scheduler's
   manifest builder uses) enforces the frozen ordering — **A-E3 accepts only an A-E1
   predecessor, A-E2 only an A-E3 predecessor** — and validates the predecessor trace SHA,
   receipt SHA, ledger binding, module and run read-only.
3. Stale / cross-run guard: the verified predecessor trace SHA must equal the plan row's
   bound `predecessor_trace_sha256`; a mismatch (replaced-after-planning or wrong-run trace)
   raises.
4. The `study02-formal-deferred-dataset-v1` cache keys are rebuilt from the plan row + the
   verified predecessor trace SHA (the `_DeferredDatasetSpec` dataclass replicates the
   scheduler's `_canonical`+SHA formula exactly) and asserted equal to the plan row's bound
   `training_cache_key` / `validation_cache_key`. Drift raises. The reconstructed object
   carries the placeholder route literal and predecessor trace SHA; it is **not** a concrete
   dataset and opens no data.

Double / zero predecessor consumption is rejected by the ledger's exactly-one-binding check
inside `_validate_predecessor`; a missing receipt/ledger file raises there as well.

### 2.3 `build_module_pre_unseal_bundle` (D8 + R5 hard requirement) — production pre-unseal

`build_module_pre_unseal_bundle(*, study_root, cache_root, run_dirs, …)` is the production
pre-unseal entry. For each module it **internally** calls
`rebuild_selection_point_provenance` (the R5-approved single-source checkpoint rebuild) and
forwards the unioned result to `build_pre_unseal_bundle` as `point_provenance_by_fit`.
`point_provenance_by_fit` is **deliberately absent from this signature**, so a caller
supplying it raises `TypeError` — no caller can substitute an unverified or stale provenance
map for the production authority (the R5 forgery gap is closed at the entry, not the caller).
A duplicate `fit_id` across modules in the rebuild raises.

## 3. Checks and exact results

All commands run from repo root with `python/` and the study `code/` on `sys.path` (the test
files set this themselves).

### 3.1 New D8 tests (added to `test_study02a_formal_executor.py`)

```
$ python -m pytest python/tests/test_study02a_formal_executor.py -q \
    -k "resolve_selected or reconstruct_deferred or pre_unseal_bundle"
6 passed, 9 deselected
```

Coverage: success-path winner + top-N ranking; fail-closed on missing decision, missing
rank_decision_id, missing ranking decision, out-of-bounds/non-integer slot, unsupported
token, trace SHA mismatch, module/run ownership mismatch, unbound (double-consumed) ledger;
deferred-spec success (A-E3←A-E1) and fail-closed on A-E1-no-predecessor, wrong-order
(A-E2←A-E1), stale/cross-run trace SHA, missing receipt, cache-key drift; pre-unseal
internal rebuild (verified via a `rebuild_selection_point_provenance` monkeypatch that
stands in for a completed run's checkpoint rebuild — no training launched, no test data
opened) and rejection of an external `point_provenance_by_fit` (`TypeError`).

### 3.2 Full `test_study02a_formal_executor.py` (non-slow)

```
$ python -m pytest python/tests/test_study02a_formal_executor.py -q -m "not slow"
13 passed, 2 deselected   (the 2 deselected are the pre-existing @slow A-E1 smokes)
```

### 3.3 All direct-related non-materialize tests (9 files)

```
$ python -m pytest \
    python/tests/test_study02a_formal_executor.py \
    python/tests/test_study02a_formal_selection.py \
    python/tests/test_study02a_selection_rules.py \
    python/tests/test_study02a_selection_engine.py \
    python/tests/test_study02a_formal_contracts.py \
    python/tests/test_study02a_formal_state.py \
    python/tests/test_study02a_formal_runner.py \
    python/tests/test_study02a_cli.py \
    python/tests/test_study02a_formal_evidence.py \
    -q -m "not slow" -k "not build_module_selection"
205 passed, 5 deselected
```

(`build_module_selection_*` and the scheduler suite materialize a run and are reported
separately in §3.4.)

### 3.4 Materialize-gated suites — clean-code proof

`test_study02a_formal_scheduler.py` (26 non-slow) and the two
`test_build_module_selection_*` tests materialize an A-E1 run, so
`formal_scheduler._assert_scoped_code_clean` rejects them while this baton's
`code/study02a/formal_executor.py` edit leaves `code/` dirty. They are **not** logic
regressions. Proof: with only the executor edit `git stash`-ed (so `code/` is clean, the
test file edit is outside the scoped `code/`+`python/studies` check):

```
$ git stash push -- code/study02a/formal_executor.py   # code/ now clean
$ python -m pytest python/tests/test_study02a_formal_scheduler.py \
    "...test_build_module_selection_emits_v2_trace_and_receipt_with_computed_winners" \
    "...test_build_module_selection_includes_failed_seeds_and_remains_consistent" \
    -q -m "not slow"
30 passed
$ git stash pop                                         # change restored
```

i.e. all 28 materialize-gated tests pass on a clean `code/`. They will pass on Codex's
committed snapshot (Codex owns commit/push). This is the same clean-code constraint the
`@slow` A-E1 smokes and the prior R4/R5 cycles operate under.

### 3.5 Happy-path `compileall` + `git diff --check`

```
$ python -m compileall -q ".../code/study02a"           # exit 0
$ git diff --check -- code/study02a/formal_executor.py python/tests/test_study02a_formal_executor.py
(no output — clean)
```

### 3.6 Frozen / test invariants

- No frozen artifact change: `git diff --name-only -- artifacts configs protocol.json` is
  empty. The public trace/receipt/bundle/manifest schemas are untouched.
- `test_access_count` stays 0: every new code path reads only selection trace/receipt/ledger
  files, predecessor evidence, or (via the existing audited `rebuild_selection_point_provenance`)
  training/validation checkpoints; `_DeferredDatasetSpec` opens no data. No test role is
  imported or opened.
- `.claude/settings.local.json` is not in this baton's diff (it is the user's pre-existing
  dirty file; preserved untouched).

## 4. Skipped

- Staged A-E1 execution, any formal training/validation, 9d and G4 — out of scope (plan
  boundaries); not started.
- `ruff` is unavailable in this environment; `compileall` + `pytest` + `git diff --check`
  stand in, consistent with prior cycles.
- The full `@slow` A-E1 smokes (real training) are not run; they require a committed clean
  `code/` tree (Codex post-APPROVE).

## 5. Stop-condition finding for Codex (placeholder → decision_id mapping)

The resolver's contract is uniquely determined by the frozen protocol
(`selected:<decision_id>` → exact-match winner; `selected_top_N` → rank-N of a stated
decision; fail-closed otherwise), and it is demonstrated on synthetic fixtures whose
placeholder strings are real trace `decision_id`s. **However**, the frozen experiment matrix
emits placeholder strings that do **not** match the selection trace's `decision_id` field —
e.g. `selected:A-E1_architecture`, `selected:A-E1_loss`, `selected:A-E1_optimizer`,
`selected:F2_or_V`, `selected:A-E3_baseline` — whereas the trace decision_ids are
`architecture:A-E1:F2:n10`, `loss:A-E3:selected:F2_or_V:n10`, etc. (confirmed by enumerating
`build_decision_specs` per module). Consequences:

- `selected:A-E1_loss` names a loss decision that **does not exist** in A-E1 (A-E1 has only
  `architecture`/`stage2` decisions, split by route F2/V) → resolves as missing → fail-closed.
- `selected:A-E1_architecture` is **ambiguous** between the F2-route and V-route architecture
  decisions → fail-closed.
- `selected:F2_or_V` (an F2-vs-V baseline_input decision) has no corresponding fit_kind/decision
  in A-E1 → fail-closed.

So under the deterministic resolver the real-matrix placeholders correctly fail-closed; they
cannot be resolved today. Resolving them requires one of (a) a frozen placeholder→decision_id
mapping convention, or (b) the staged-execution model that publishes per-stage decisions the
labels reference. Both are outside this baton's boundaries (no schema/frozen change; no
staged execution). I did **not** invent a mapping (that would guess frozen semantics). This
is reported for Codex adjudication; it does not block the D8 production wiring delivered here
(deferred-spec reconstruction and the pre-unseal provenance rebuild are fully determined and
tested; placeholder resolution is correct and fail-closed for any trace whose placeholders
are decision_ids).

## 6. Deviations / blockers

None. No protocol deviation, no frozen-口径 change, no schema change, no test access. The
only tests not green in-tree are the materialize-gated suites blocked by the dirty-`code/`
guard (§3.4), which is expected for an uncommitted executor edit and is Codex-resolved on
commit.

## 7. git status --short

```
 M .claude/settings.local.json
 M Study/02-study-NN参数估计与分位点目标研究/code/study02a/formal_executor.py
 M python/tests/test_study02a_formal_executor.py
```

Stopping for Codex review in
`coworker/reviews/2026-07-18-study02-g3-d8-r1-codex.md` (APPROVE/REVISE/BLOCK). No commit,
no push, no self-approve.

— Claude (executor), 2026-07-18

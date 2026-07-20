# Study/02 G3 — controller-anchor single-replay validation (perf blocker fix) executor report

Branch: `claude/study02-a-20260715`. Authoritative start: `origin/claude/study02-a-20260715 @ fd43e38`.
Code tip after this棒: `d480c13` (local; push deferred to the end of this棒 per the relay directive —
outbound network to github was intermittent). Scope (per the relay-mode directive): eliminate the
`_validate_controller_anchors` O(N^2)-per-rebuild cost **without** weakening the journal / anchor /
claim-receipt hash chain or tamper detection, then run the 349-fit staged A-E1 full-chain sealed smoke
to completion. No second authority state, no persisted snapshot, no incremental scheduler, no
`_authority` process cache, no change to the frozen matrix / selection rule / formal schema / scientific
contract. **Stop** before A-E3/A-E2, accredit-authorize, test unseal, real formal, 9d or G4. Final
status: `scheduler anchor-validation perf FIXED and verified (40x at N=96), isolated commit d480c13,
awaiting Codex review; staged source-of-truth mismatch (_a_e1_fit_stage reads fit_kind absent from
plan.jsonl -> staged selection never fires in a full run) is a CRITICAL OPEN BLOCKER handed to Codex;
349-record smoke FAILS before any valid staged receipt (placeholder rows mis-concretized; 349 is not a
valid fit count and ~2h is not a valid staged-run time basis); A-E1 formal NOT authorized`.

## The blocker (root cause)

`_validate_controller_anchors` is called inside every `_rebuild_authority(validate_controller=True)`.
For each of the N signed anchors it ran an **independent prefix replay** `_replay(events[:seq+1])`, so the
same batch of claim/receipt files was re-read, re-structurally-validated and re-hash-bound at every
growing prefix length — O(N^2) work **per rebuild**. A staged run calls `_rebuild_authority` roughly 4
times per fit (orchestrator + claim + record + occasional stage-selection rebuilds), so the run-total was
O(N^3): the 349-fit smoke exceeded 30 min around fit 96 and had not produced a stage receipt.

Measured on clean `fd43e38` (synthetic A-E1 fits, median of 3, `validate_controller=True`,
`build_seconds_validate_off` = construction with anchors unchecked so N=96 is reachable):

| N fits | events=anchors | full (validate-on) | baseline (validate-off) | **anchor cost** |
|--------|----------------|--------------------|-------------------------|-----------------|
| 32     | 65             | 11.27 s            | 0.67 s                  | **10.60 s**     |
| 64     | 129            | 42.50 s            | 0.90 s                  | **41.60 s**     |
| 96     | 193            | 90.33 s            | 1.23 s                  | **89.10 s**     |

Anchor-cost scaling 10.60 → 41.60 → 89.10 s for 65 → 129 → 193 events ≈ **O(N^1.9)**. The
anchor-free baseline is already linear (~0.44 s fixed + ~3.6 ms/event). So the entire quadratic blow-up
lived inside the per-anchor prefix-replay loop.

## The fix (minimal, no control-flow rewrite)

`_replay` gains an **opt-in** out-param `_checkpoints: list[str] | None = None`. When provided, a single
ordered replay appends — at the end of each event's iteration (genesis and non-genesis alike) — the
canonical authority-state hash `_sha(_canonical(state_after_event_seq))`. The state dict is built by one
tiny nested helper `_snapshot_state(...)` that is now the single source of truth for both the per-event
checkpoints and the function's return value. The genesis/kind dispatch is **untouched** (the genesis
`continue` and the `if/elif/else` kind ladder are exactly as before; two 2-line capture sites were added
around them, both guarded by `if _checkpoints is not None`). When `_checkpoints is None` (every existing
caller) `_snapshot_state` runs exactly once, at the return — zero per-event overhead, byte-for-byte the
old behaviour.

`_validate_controller_anchors` now runs **one** ordered replay

```python
checkpoints: list[str] = []
_replay(run_dir, manifest, plan, events, allow_future_records=True, _checkpoints=checkpoints)
```

and compares each signed anchor against `checkpoints[seq]` (replacing the old
`_sha(_canonical(_replay(events[:seq+1], allow_future_records=True)))`). Every other anchor check
(seq, event_count, event_tail_sha256, authority_sha256, previous_anchor_sha256, controller_key_id,
HMAC, anchor path) is unchanged. So the quadratic loop is gone; each claim/receipt file is still read,
structurally validated and hash-bound **exactly once** during that single replay. No cached sidecar is
trusted, no second authority state exists, nothing is persisted.

`allow_future_records=True` matches the old per-anchor replay semantics exactly; the per-seq checkpoint
hash is identical whether extra future records are tolerated or not (the directory check never enters the
state dict — covered by `test_checkpoint_hash_independent_of_allow_future_records`). The strict full
replay at `_rebuild_authority` line ~644 (`allow_future_records=False`) is unchanged and still rejects
extra/missing records before anchor validation runs.

## Correctness — equivalence and fail-closed (new tests)

10 tests appended to `python/tests/test_study02a_formal_scheduler.py`:

- `test_single_capture_checkpoint_equals_prefix_replay_for_every_seq` — for a sequence spanning
  genesis / claim / success / failure / trailing-live-claim, **every** captured checkpoint equals the
  authority hash of an independent prefix replay at that seq; capturing does not change the return value.
- `test_replay_checkpoints_default_none_leaves_return_unchanged` — opt-in knob, default call unchanged.
- `test_checkpoint_hash_independent_of_allow_future_records` — allow/deny gives identical checkpoints.
- `test_strict_prefix_replay_rejects_future_records_at_intermediate_seq` — pins why anchor validation
  needs `allow_future_records` and why one full strict replay substitutes for N lenient prefix replays.
- `test_tampered_history_claim_detected_by_single_capture_replay`,
  `test_tampered_history_receipt_detected_by_single_capture_replay` — tampering a historical claim or
  receipt is still detected (capture never becomes a trusted sidecar); restore → passes again.
- `test_anchor_valid_hmac_but_wrong_state_rejected_by_checkpoint` — an anchor **re-signed with the real
  controller key** but carrying a wrong `state_sha256` passes the HMAC check yet is rejected by the
  `checkpoints[seq]` comparison (the new comparison is actively binding, not redundant).
- `test_full_replay_after_simulated_restart_recovers_same_authority` — a fresh `_rebuild_authority`
  (no in-memory cache) recovers the identical authority + state.
- `test_history_tamper_detected_after_simulated_restart` — tamper a historical file then re-run a fresh
  full rebuild (restart) → still fails closed.

## Full verification (clean tree, code tip `d480c13`)

- `python -m compileall` over `code/` + `python/` — OK.
- `git diff --check` on the changed files and on the commit — clean (no whitespace errors).
- Frozen hash audit — `verify_frozen_hashes(STUDY_ROOT)` OK; matrix
  `sha256(experiment_matrix.csv) == FROZEN_MATRIX_SHA256 == fad701af…f6b1` (the fix touched no frozen
  file).
- `python -m pytest python/tests/test_study02a_*.py --deselect …::test_staged_full_chain_smoke` →
  **337 passed, 1 deselected** (the 349 smoke, run separately below). Includes the 10 new tests, all
  existing scheduler/anchor/claim/receipt/journal/tamper tests, and the `@slow` staged `max_fits=3`
  production-equivalent test.

## BEFORE → AFTER (same conditions, median of 3, validate_controller=True)

| N fits | events | BEFORE full | AFTER full | **speedup** | anchor cost BEFORE → AFTER |
|--------|--------|-------------|------------|-------------|----------------------------|
| 32     | 65     | 11.27 s     | **0.945 s**| 11.9×       | 10.60 s → 0.34 s           |
| 64     | 129    | 42.50 s     | **1.60 s** | 26.6×       | 41.60 s → 0.68 s           |
| 96     | 193    | 90.33 s     | **2.24 s** | **40.3×**   | 89.10 s → 1.03 s           |

Speedup grows with N (BEFORE O(N^2), AFTER linear). AFTER `validate-on ≈ 2× baseline` (the step-1 strict
replay + the capture replay inside `_validate_controller_anchors`); the capture replay runs cache-warm
(right after step-1) so it is cheaper than the cold baseline. Residual `validate-on` cost is now ~O(N)
(0.29 + 0.0101·N seconds). Full JSON saved at `python/.bench_anchor_results.json`.

## 349-record smoke — FAIL (not partial pass): perf now reaches the end, exposing a staged source-of-truth mismatch

The anchor fix removed the perf blocker, so `test_staged_full_chain_smoke` now **advances through all
349 plan records (699 events, 349 anchors) in ~2 h (7321 s) and reaches the final `build_module_selection`**
— something impossible before. It then **FAILS** (pytest exit 1). **This is a FAIL, not a partial pass:**
the run does **not** constitute a valid full-chain staged smoke, because a stage-classification bug means
the staged selection path (stage1 → top4 → stage2 → winner) was **never executed**. Two pre-existing
latent bugs, **unrelated to the anchor fix**, are exposed only because the smoke could finally run far
enough:

1. **`_a_e1_fit_stage` reads `fit_kind` that plan.jsonl does not carry.** It does
   `plan_row.get("fit_kind", "")`, but `plan.jsonl` has **no `fit_kind` on any of its 349 rows**
   (verified) — by design: per the comment at `formal_executor.py:854-857`, `fit_kind` lives in the frozen
   matrix and plan.jsonl "renames those fields". So **every** row — including the `selected_top_*`
   stage-2 placeholders (idx 141-176 F2 / 263-298 V) and the `selected:A-E1_*` winner-retrain fits
   (idx 177-226 F2 / 299-348 V) — is classified `concrete`. `run_a_e1_staged` therefore **never calls
   `build_a_e1_stage1_selection` / `build_a_e1_stage2_selection`**: staged selection never triggers and
   **no stage1/stage2 receipts, no selection trace, no staged ledger are published** (verified: all
   absent). The placeholder fits are executed as-if-concrete; the smoke's `_smoke_fit_runner` ignores
   `architecture` (trains a fixed tiny MLP), so they "succeed" without crashing — masking the fact that
   the staged path is never exercised. `status_run` on the finished run reports `succeeded: 349,
   failed: 0` — which is itself the symptom: those 349 "succeeded" records include the **wrongly
   concretized placeholder rows**, so **349 is NOT a valid A-E1 fit count** and the ~2 h wall-clock is
   **NOT a valid basis for formal staged-run time extrapolation**.
2. **`_smoke_score_fit` KeyErrors on plan.jsonl rows.** When the final `build_module_selection`
   → `_derive_and_score_evaluations` scores the selection fits, it honours the
   `score_fit(fit_id, plan_row)` contract where `plan_row` is a plan.jsonl row (no `fit_kind`);
   `_smoke_score_fit` does `plan_row["fit_kind"]` directly → `KeyError: 'fit_kind'` at `G3-fit-0105`.

Final exception / traceback (end of the 7321 s run):

```
formal_executor.py:2024  result["final_selection"] = build_module_selection(...)
formal_executor.py:729   specs, evaluations_by_fit = _derive_and_score_evaluations(...)
formal_executor.py:870       evaluation = score_fit(fit_id, plan_row)
test_study02a_formal_executor.py:1387  kind = str(plan_row["fit_kind"])
KeyError: 'fit_kind'
========================= 1 failed in 7321.36s (2:02:01) =========================
```

`test_access_count == 0` on the finished run (verified via `status_run`): test stayed sealed throughout —
the executor never reads test data. (This does not make the run a valid staged smoke; it only confirms
the sealed-test invariant held.) No `SLOW_SMOKE_TELEMETRY` line was printed (the test fails before that
`print`). The 349 anchors of the finished run **do** validate under the new single-replay path
(`_rebuild_authority(validate_controller=True)` succeeds on the 699-event / 349-anchor run) — i.e. the
anchor fix itself is confirmed correct at full scale.

Why neither bug was caught before: the per-route staged unit tests
(`test_resolve_a_e1_staged_selection_*`) call `build_a_e1_stage1/2_selection` directly with an explicit
`route`, bypassing the orchestrator's `_a_e1_fit_stage` classification; the `max_fits=3`
production-equivalent test never reaches fit 141; and the full 349 smoke never completed (perf-blocked)
until this fix. So the orchestrator's stage-classification wiring — the thing that decides when staged
selection actually fires in a full run — was never exercised end-to-end. The `build_a_e1_stage1/2`
-selection **mechanism** is unit-tested and correct; the orchestrator's **triggering** of it is not, and
rests on a field (`fit_kind`) the plan does not carry. The proper fix (next棒, after Codex review) is for
`_a_e1_fit_stage` / scoring to resolve each fit's authoritative matrix row by `fit_id` and read the stage
type there (fail-closed on missing/duplicate/inconsistent plan↔matrix correspondence), **not** to copy
`fit_kind` back into plan.jsonl (that would create a second source of truth).

This棒 does **not** (per the directive): write `fit_kind` into plan.jsonl; modify the frozen plan/schema;
give `_smoke_score_fit` a default `fit_kind` to bypass the KeyError; or mark the known-failing smoke as
silent-pass / unconditional `xfail`. The `@pytest.mark.slow` smoke is left as the executable reproduction
entry point.

## Status

- **Scheduler anchor-validation perf — FIXED, awaiting Codex review.** `_validate_controller_anchors` is
  O(N) per rebuild (measured 40× faster at N=96); the journal/anchor/claim-receipt hash chain and tamper
  detection are unchanged; 337 study02a tests + 10 new equivalence/fail-closed tests pass; compileall /
  frozen-hash audit / `git diff --check` clean. Isolated logical commit `d480c13` (code + its tests).
  Confirmed at full scale: the 349 anchors of the failed smoke run validate under the new single-replay
  path.
- **Staged source-of-truth mismatch — CRITICAL OPEN BLOCKER (handed to Codex, NOT fixed this棒).**
  `_a_e1_fit_stage` reads `fit_kind` from plan.jsonl, which does not carry it (it lives in the frozen
  matrix). In a full run every fit is classified `concrete`, so staged selection (stage1 → top4 →
  stage2 → winner) **never fires**. This means the prior per-route unit tests validated only the parts,
  and `max_fits=3` never reached the fit-141 stage boundary — top4 unlocking was never actually verified.
- **Full-chain smoke — FAILED before any valid staged receipt.** It is a FAIL, not a partial pass; the
  349 records include wrongly-concretized placeholder rows, so 349 is not a valid fit count and the ~2 h
  wall-clock is not a valid formal staged-run time basis. `test_access_count == 0` (test stayed sealed).
- **A-E1 formal — NOT authorized.**

This棒 did not write `fit_kind` into plan.jsonl, modify the frozen plan/schema, patch `_smoke_score_fit`
with a default `fit_kind`, or silence/xfail the known-failing smoke. The `@pytest.mark.slow` smoke
remains the executable reproduction entry. Suggested next-棒 fix direction (after Codex review):
`_a_e1_fit_stage` / scoring resolve each fit's authoritative matrix row by `fit_id` and read the stage
type there (fail-closed on missing/duplicate/inconsistent plan↔matrix correspondence), without copying
`fit_kind` back into plan.jsonl.

## Scope / non-goals (respected)

- The journal remains the **sole** persistent authority; `_replay` default behaviour, return value and all
  existing call sites are unchanged.
- No persisted snapshot, no second authority state, no general incremental scheduler, no background
  service, no new framework, **no `_authority` process cache** (deferred per the directive — would need a
  separate running-tamper audit).
- No change to the frozen matrix, selection rule, formal schema or scientific contract; `test_access_count`
  stays 0 throughout; test stays sealed.
- A 2× constant factor remains (the step-1 strict replay and the capture replay are two full O(N)
  replays per `validate_controller=True` rebuild). Folding checkpoint capture into the step-1 replay
  (one call-site arg, no control-flow rewrite) would halve it; **not done this棒** — measured the anchor
  fix first, per the directive, and the smoke completes without it. Noted as a future option.
- Did NOT enter A-E3/A-E2, accredit-authorize, test unseal, real formal, 9d or G4. **Not APPROVE; A-E1
  formal NOT authorized.**

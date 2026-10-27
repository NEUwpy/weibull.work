# Study/02 G3 — point_evidence REVISE: alias-chain + accreditation authority preflight

Branch: `claude/study02-a-20260715`. Start: `origin/claude/study02-a-20260715 @ 28b1d18` (the relocation棒's
final tip — that棒 was **3** commits: `4d5c9cd` / `e9f455a` / `28b1d18`; correcting an earlier "4 commits"
miscount). This棒 closes the two fail-closed gaps from Codex's re-review. No change to formal_scheduler's output
contract, frozen matrix/plan/schema, selection rule, scientific metrics, or staged execution; **no 2 h smoke
re-run** (no staged/selection logic change).

## Codex REVISE — what was already approved (not redone)

Option (a) relocation; `4d5c9cd`'s path relocation + frozen-matrix derivation + n-recovery + failed-fit
handling; `28b1d18`'s 349-record slow-smoke PASSED evidence. This棒 only closes the two gaps below.

## Gap 1 — directory alias-chain in `_validate_selection_point_evidence_dir`

**File:** `code/study02a/formal_executor.py`.

The prior validator inlined per-entry `lstat` checks but never verified the directory components themselves
(`run_dir/selection`, `run_dir/selection/point_evidence`) were not symlink/junction/reparse, never confirmed
the resolved path stayed within `run_dir`, and re-implemented (rather than reused) the project's alias logic.
Fixed by reusing the scheduler's canonical helpers (no new framework):

- `_reject_alias(directory)` — walks the directory **and all parents** (`run_dir/selection/point_evidence`,
  `run_dir/selection`, `run_dir`), rejecting symlink/junction/reparse/hardlink. `_resolved` does not resolve
  symlinks, so `lstat` still detects them; the hardlink check is file-scoped via `is_file()`; Windows
  junctions/reparse caught via `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`.
- `_contained(run_dir, "selection/point_evidence")` — explicit "resolved within exact `run_dir`" containment
  (`relative_to`), matching how the scheduler pairs `_reject_alias` + `_contained`.
- Per-entry now mirrors the scheduler's stricter pattern: `os.scandir` +
  `entry.is_file(follow_symlinks=False)` (reject non-file/nested/broken-symlink) +
  `_reject_alias(entry, require_file=True)` (plain file, no symlink/reparse/hardlink, nlink==1). The
  `.json` suffix / fit_id / exact-set (missing/extra/unknown/duplicate) checks are unchanged.
- `_reject_alias` + `_contained` are imported from `formal_scheduler` into `formal_executor` (consistent with
  the existing `_rebuild_authority` cross-module private import). `formal_scheduler.py` is **unchanged**.

## Gap 2 — accreditation authority preflight in `accredit_build`

**File:** `code/run_study02a.py`.

`accredit_build` now runs a full `_rebuild_authority(run_dir, cache_root)` **first** and uses its
replay-verified outputs as the sole source of truth — raw `manifest.json` / `plan.jsonl` / receipt JSON are no
longer trusted as fact:

- The replay raises on any tampering (terminal-receipt content vs the event's `receipt_sha256`, `plan_sha256`,
  event-chain hash, manifest/controller-anchor drift) **before any diagnostic file is written**. It also
  requires a clean scoped `code/` tree (same as all scheduler use).
- Uses the replay's `manifest` (the full study manifest — carries `role_namespaces`, `code_commit`, `matrix`,
  `scheduler`), `verified_plan` (replay-verified, hash-bound — the raw `plan.jsonl` read is **deleted**), and
  `fit_states`.
- Per selection fit, **three-way consistency** (raise before any write): scheduler `fit_state` ==
  terminal-receipt state == (`"failed"` iff `evaluation.failed`). The receipts are trustworthy because the
  replay already hash-verified them against the event payloads. The `evidence.json` presence check (present
  iff succeeded) is kept.
- All four diagnostics (`fit_status.csv`, `ceiling_hit_report.json`, `leakage_audit.json`,
  `pre_unseal_bundle.json`) are written only at the very end, after the preflight + per-fit loop — so an
  authority-preflight or consistency failure leaves **no** generated diagnostics.

## Tests (`python/tests/test_study02a_formal_executor.py`)

- **Gap 1 — alias rejection**: `_make_dir_alias` creates a directory alias via POSIX symlink, falling back to a
  Windows junction (`mklink /J`, no privilege required); it skips (without faking coverage) only if the
  platform can create neither. `test_point_evidence_dir_rejects_alias_directory` (the point_evidence dir
  itself is an alias) and `test_point_evidence_dir_rejects_alias_selection_parent` (the `selection` parent is
  an alias — `_reject_alias` walks parents) both assert rejection; `test_point_evidence_dir_accepts_real_directory`
  is the sane positive. On this Windows host the junction path exercises the rejection for real (0 skipped).
- **Gap 2 — attack tests** (real `_rebuild_authority`, fast): a self-contained `_accredit_attack_run` does
  `materialize_run` + one `claim_next_fit` + `record_fit_succeeded` (synthetic outputs via `fe._write_outputs`).
  `test_accredit_build_rejects_tampered_terminal_receipt` / `_plan` / `_event` each tamper one artifact and
  assert `accredit_build` raises **and** none of the four diagnostics is written.
- **Gap 2 — legitimate path**: the existing `_accredit_real_matrix_run` fixture now also mocks
  `run_study02a._rebuild_authority` (returning the verified manifest/plan/fit_states matching the fixture's
  receipts), so the succeeded + failed processing path (3-way consistency, fit_status rows, bundle) is exercised
  fast. The real rebuild's tamper-detection is covered by the attack tests above; `_rebuild_authority` itself is
  exhaustively tested in `test_study02a_formal_scheduler.py` + the 349-smoke. (Mocking the slow authority replay
  for the processing test is what avoids a 2 h re-run, per Codex.)

## Checks and exact results

```
$ python -m compileall -q code/ python/                 # exit 0
$ git diff --check                                      # clean
$ verify_frozen_hashes(STUDY_ROOT)                      # OK
$ matrix sha256                                         # fad701af... == frozen FROZEN_MATRIX_SHA256
$ python -m pytest python/tests/test_study02a_*.py -q -m "not slow" \
    --deselect ...::test_staged_full_chain_smoke \
    --deselect ...::test_post_selection_authority_rebuilds_with_relocated_point_evidence
362 passed, 6 deselected                                # +3 alias +3 attack vs the prior 356
```

Attack tests (`test_accredit_build_rejects_tampered_terminal_receipt|_plan|_event`): 3 passed (real
`_rebuild_authority` raises on each tamper; no diagnostic written). Alias tests: 3 passed (junction-backed on
Windows). Focused `test_post_selection_authority_rebuilds_with_relocated_point_evidence`: passed (unchanged).
The **349-smoke PASSED (2 h 13 min) fact is unchanged** — not re-run (no staged/selection logic change).

## Documentation corrections (per contract)

- Corrected the relocation棒's commit count to **3** (`4d5c9cd` / `e9f455a` / `28b1d18`) — the earlier "4
  commits" was a chat-summary miscount, never in a tracked doc; this棒's report states the correct count.
- Authoritative tip: prior `28b1d18` → this棒 `cd4d04a` (code/tests) + the docs commit (final tip). Updated in
  `00-A-执行状态.md`, `03-A-实验计划.md`, and the relay handoff (R6 update appended).
- The "349-smoke PASSED" fact is preserved; no claim that formal is authorized.

## Boundary held

No `formal_scheduler.py` output-contract change; no frozen matrix / plan schema / `_PLAN_FIELDS` / selection
rule / artifact-trace-receipt-bundle version / scientific metric / staged-execution change; no test read
(`test_access_count == 0`); no real formal A-E1 launch; no oracle approval; no `formal-accredit-authorize`; no
A-E3/A-E2 / test unseal / real formal / 9d / G4.

## Status & next

- **Gap 1 (alias-chain) + Gap 2 (authority preflight) — CLOSED (`cd4d04a`, awaiting Codex re-review).** Both
  reuse the scheduler's existing alias-chain + replay semantics; 362 non-slow tests pass (incl. alias + attack
  tests); 349-smoke PASSED unchanged.
- **point_evidence relocation — APPROVED (prior棒, unchanged).**
- **A-E1 formal — NOT authorized.**

— Claude (executor), 2026-07-20

# Study/02 G3 — point_evidence vs scheduler output-dir validation: design + impact analysis for Codex

Branch: `claude/study02-a-20260715`. Authoritative start: `origin/claude/study02-a-20260715 @ 7824e72`. This棒 is
**executor-only / analysis-only** (per the 2026-07-17 role split: Claude = executor, Codex = sole planner +
approver). It does **not** change any code, frozen artifact, schema, contract, or test. It hands Codex the exact
root cause, the two fix shapes with precise change lists and blast radius, an invariant ledger, and a
recommendation. **A-E1 formal remains NOT authorized; test stays sealed.**

This is the CRITICAL OPEN BLOCKER the source-of-truth棒 (`10d6fcf` / report
`2026-07-20-study02-g3-staged-source-of-truth-claude.md`) newly exposed by reaching the end of the 349-fit chain
and explicitly handed to Codex as its own棒.

## 1. Root cause (verified, exact file:line)

The scheduler requires each fit's output directory to contain **exactly** its frozen `expected_outputs`, and
selection co-locates a per-fit artifact that is not in that set.

- **The strict check** — `code/study02a/formal_scheduler.py:803-810`, `_validate_success_files`:

  ```python
  expected = {item["relative_path"] for item in row["expected_outputs"]}      # {checkpoint.pt, fit_status.json, evidence.json}
  ...
  output_dir = run_dir / "outputs" / row["fit_id"]
  snapshot = _output_snapshot(run_dir, row["fit_id"])                          # os.scandir of outputs/{fit_id}/ — EVERY entry
  if {path.relative_to(run_dir).as_posix() for path in snapshot} != expected:
      raise ValueError("output directory contains missing, extra, hidden, or nested output")
  ```

  `_output_snapshot` (`formal_scheduler.py:791-800`) is a plain `os.scandir` of `outputs/{fit_id}/` with no
  exclusions; the comparison is set-equality against the frozen `expected_outputs`.

- **The co-located selection artifact** — `code/study02a/formal_executor.py:747-751`, `build_module_selection`:

  ```python
  point_evidence_paths: dict[str, str] = {}
  for fit_id, evaluation in evaluations_by_fit.items():
      artifact_path = run_dir / "outputs" / fit_id / "point_evidence.json"     # <-- inside the scheduler-authority dir
      _publish_bytes_no_replace(_canonical(serialize_point_evidence(evaluation)), artifact_path)
      point_evidence_paths[fit_id] = str(artifact_path)
  ```

  Written for **144 of 349** A-E1 fits (the `search_stage1` + `search_stage2` selection candidates). This is a
  **deliberate** R3#1 design: the per-fit canonical point records are an independent artifact whose content SHA
  (`point_evidence_sha256`) is bound into each candidate's `supporting_evidence_sha256` → selection trace →
  receipt, and pre-unseal reloads + independently rebuilds them from the bound checkpoint. `point_evidence.json`
  is a **selection-evidence** artifact, not a training artifact.

- **The collision** — `_validate_success_files` is invoked on every succeeded fit during authority replay:
  `formal_scheduler.py:584` (`_apply_success` in the live loop), `:970` (`record_fit_succeeded`), `:991`
  (`status_run`/`_rebuild_authority`). Any `_rebuild_authority()` / `status_run()` **after** selection replays the
  144 candidate success events, sees the extra `point_evidence.json`, and raises. Concretely blocked today:
  the smoke's final post-selection `status_run` (the one failing line in `test_staged_full_chain_smoke`), and the
  formal path's `resolve_a_e1_staged_selection` → `_score_a_e1_winner_retrain` → `_rebuild_authority` at
  `score_fit=None`.

- **Why it was never hit before** — pre-existing and orthogonal to the source-of-truth fix; the original
  `run_a_e1_staged` had the same `build_module_selection` → `resolve_a_e1_staged_selection` order, but the
  source-of-truth bug (`_a_e1_fit_stage` reading `fit_kind` from a plan that carries none) meant staged selection
  never fired, so `build_module_selection` was never reached. The source-of-truth fix (`10d6fcf`) made the staged
  path actually reach the end of the chain, exposing this.

The current test-side accommodation (committed in `7824e72`, `test_study02a_formal_executor.py:1757-1767`) reads
the final sealed invariant (`test_access_count == 0`) directly from `scheduler_state.json` + the raw event ledger
instead of via `status_run()`. That is a **test-only workaround**, not a fix — the production formal path still
cannot run `_rebuild_authority` after selection.

## 2. What does NOT move (load-bearing facts for both options)

These constrain the design and shrink the real blast radius:

- **`point_evidence.json` is NOT, and was never, in `expected_outputs`.** `expected_outputs` is frozen per-fit at
  claim time = `{checkpoint.pt, fit_status.json, evidence.json}` (`formal_executor.py:446-448`). The selection
  candidate IS determined by the frozen matrix (so it is known at claim time), but point evidence is a
  **post-selection lifecycle** artifact — it cannot be a pre-training-success output that must exist in the fit
  output dir before training succeeds, so it is not (and cannot be) a frozen `expected_outputs` entry. Making
  it a 4th `expected_outputs` entry is therefore **not viable** (a selection artifact cannot be required to
  exist before the training it depends on has produced a checkpoint).
- **The pre-unseal bundle is path-agnostic.** `build_pre_unseal_bundle(..., point_evidence_paths:
  Mapping[str, Path], ...)` (`formal_contracts.py:1113`) consumes the dict of paths — `load_point_evidence` each
  (`:1284-1297`), `assert_point_evidence_provenance` against the independent checkpoint rebuild (`:1317-1397`), and
  enforces they are distinct real files (`:1131-1135`, anti-alias + `is_file`). **Relocating the files requires zero
  change here** as long as the dict points at the new paths.
- **The independent point-provenance rebuild reads the checkpoint, not the artifact.**
  `rebuild_selection_point_provenance` (`formal_executor.py:886-940`) reads `outputs/{fit_id}/checkpoint.pt`
  (`:817-818`) and rebuilds canonical point records from it; it does **not** read `point_evidence.json`. The link
  between a (relocated) published artifact and its checkpoint is preserved by `assert_point_evidence_provenance`
  (field-by-field compare of published vs rebuilt — `selection.py:708-757`). **Relocation does not touch this.**
- **`_output_snapshot` underpins 5 distinct invariants** (`formal_scheduler.py`): pre-claim emptiness (`:924`),
  failed-fit emptiness (`:581`, `:966`), orphaned-output detection (`:944`), and the success equality (`:808`).
  Any option that loosens the snapshot/equality must reason about all 5, not just the failing line.

## 3. Option (a) — relocate `point_evidence.json` out of the scheduler-authority fit dir

**Shape.** `outputs/{fit_id}/` reverts to being **purely** the scheduler-authority training artifacts; the
selection-evidence artifact moves to a selection-owned location, e.g. `run_dir/selection/point_evidence/{fit_id}.json`
(or the per-fit-subdir mirror `run_dir/selection/{fit_id}/point_evidence.json` — functionally identical; pick one
for layout consistency with `outputs/{fit_id}/`).

**Precise change list (production code):**

| Site | File:line | Change |
|---|---|---|
| WRITER | `formal_executor.py:749` | `run_dir/"outputs"/fit_id/"point_evidence.json"` → `run_dir/"selection"/"point_evidence"/f"{fit_id}.json"`. **No extra mkdir needed**: `_publish_bytes_no_replace` (`formal_contracts.py:480`) already does `destination.parent.mkdir(parents=True, exist_ok=True)`, and raises `FileExistsError` if the destination exists (`:478-479`) — the no-replace + create-once semantics carry over unchanged to the new path. |
| READER (hardcoded scan) | `run_study02a.py:269-292` | Currently `for fit_dir in sorted((run_dir/"outputs").iterdir()): ... fit_dir/"point_evidence.json"`. Change discovery to read from the new location while still joining on `evidence.json` from `outputs/{fit_id}/` for the `FitResult` build (`:272-286`). `point_evidence_paths[fit_id]` (`:292`) is unchanged in shape, only its source path. |

**Unchanged (verified):** `formal_contracts.py` bundle (path-agnostic); `rebuild_selection_point_provenance`
(checkpoint-only); `_validate_success_files` / `_output_snapshot` and all 5 invariants; frozen `expected_outputs`;
selection trace / receipt / supporting-hash / `point_evidence_sha256` binding (the SHA is over the record content,
not the path); `_PLAN_FIELDS`; matrix; configs.

**Tests touched (mechanical, path-only):** `test_study02a_formal_executor.py:1133` (fixture writes a
`point_evidence.json` — repoint to the new location); `:1757-1767` (the test-only sealed-check workaround — once the
blocker is fixed, the smoke's final assertion can revert to the real `status_run()`/`_rebuild_authority()` sealed
read, which is the whole point of fixing this). Any other test asserting the on-disk path
(`grep -rn '"point_evidence.json"' python/tests/`).

**Pros.** (1) The scheduler's core anti-tamper invariant — "a fit's output dir is exactly its hash-bound training
artifacts" — is preserved **byte-for-byte**; zero scheduler change. (2) Clean domain separation: training-authority
artifacts vs selection-evidence artifacts no longer share a directory. (3) Small, localized, reviewable diff
(1 writer line + 1 reader block + mechanical test repoints). (4) Selection-evidence provenance is unchanged in
strength (content SHA + independent checkpoint rebuild + field-by-field assert).

**Cons / risks.** (1) `point_evidence.json` is no longer physically co-located with its checkpoint; auditors must
follow the `point_evidence_paths` dict (already the abstraction the bundle uses). (2) Any external/consumer
assumption of the old path outside the grepped set — verified absent: a `grep` of all of `code/` for the hardcoded
`outputs/.../point_evidence.json` pattern returns exactly two sites (`run_study02a.py:271`, `formal_executor.py:749`),
both in the change list. (Parent-dir creation and no-replace are handled by the existing `_publish_bytes_no_replace`
helper — no new I/O logic.)

## 4. Option (b) — teach the scheduler to tolerate the co-located selection artifact

Two sub-variants, both riskier than they look because of §2's 5-invariant point.

**b1 — exclude `point_evidence.json` in `_output_snapshot` itself.** Touches all 5 invariant call sites. Weakens
pre-claim emptiness (`:924`: a stale `point_evidence.json` could pre-exist before a claim), failed-fit emptiness
(`:581`/`:966`), and orphan detection (`:944`). **Not recommended** — broad, subtle, anti-tamper-regressing.

**b2 — loosen only the success equality at `:808-810`.** Compute `snapshot`, then compare
`(snapshot_relative_paths - ALLOWED_EXTRA) == expected` where `ALLOWED_EXTRA = {"outputs/{fit_id}/point_evidence.json"}`
(or a name-based allowance). Leaves the other 4 call sites intact.

  - **Orphan detection (`:944`) still needs an exemption** — else the post-selection replay flags
    `point_evidence.json` as an orphaned output on candidate fits. So b2 already ripples beyond one line.
  - **The scheduler must decide who is allowed the extra file.** It cannot know selection-candidacy at validation
    time (selection is a post-training layer). So the allowance is necessarily **universal** (every fit's output
    dir gains a phantom permitted slot), or the scheduler grows a selection-aware dependency (selection-layer
    concept leaking into the authority model).
  - **Permanent invariant weakening.** "A fit output dir is exactly its training artifacts" becomes "…its training
    artifacts plus possibly a selection artifact." This is a contract change to the scheduler's authority model,
    which is the system's primary anti-tamper surface.

**Precise change list (production code, b2):**

| Site | File:line | Change |
|---|---|---|
| equality check | `formal_scheduler.py:808-810` | subtract an allowed-extra set before set-equality. |
| orphan detection | `formal_scheduler.py:944` (+ `:581`/`:966` if failed candidate fits can carry it) | exempt the same artifact, or accept changed orphan semantics. |
| (optional) snapshot | `formal_scheduler.py:791-800` | if the allowance is name-based, centralize it here. |

**Unchanged:** the writer (`formal_executor.py:749`) and the hardcoded reader (`run_study02a.py:269-292`) stay as-is
— the appeal of (b).

**Pros.** No file relocation; the two hardcoded-path consumers are untouched.

**Cons / risks.** (1) Scheduler output-contract / authority-semantics change on the system's primary anti-tamper
surface. (2) Selection-layer concept leak into the scheduler (or a universal phantom-slot weakening). (3) Ripples to
orphan detection even in the "contained" b2 form. (4) Every fit's validation now permits a file the frozen
`expected_outputs` does not name — the strict "exactly the claimed outputs" guarantee that makes the authority
replay a meaningful tamper check is permanently relaxed. For a research-integrity-critical pipeline, this is the
wrong trade vs. (a)'s localized relocation.

## 5. Recommendation

**Option (a) — relocate.** It is the smaller *semantic* change (the scheduler authority model is untouched), the
smaller *integrity* change (no invariant weakened), and the actual diff is tiny and mechanical (1 writer + 1 reader
block + test repoints). Option (b) trades a marginally smaller diff for a permanent weakening of the core
anti-tamper invariant and a concept leak — a bad trade here. The only real cost of (a) is losing physical
co-location of `point_evidence.json` with its checkpoint, which the existing `point_evidence_paths` abstraction
already paper-overs and which `assert_point_evidence_provenance` already re-binds cryptographically.

Suggested relocated path: `run_dir/selection/point_evidence/{fit_id}.json` (flat, one file per fit, consistent with
the bundle's anti-alias + one-per-fit expectation). If Codex prefers the per-fit-subdir mirror
`run_dir/selection/{fit_id}/point_evidence.json`, the change list is identical.

**For Codex to decide:** (1) option (a) vs (b) vs a third shape Codex sees; (2) the exact relocated path layout;
(3) whether the smoke's final sealed-check should revert to the real `status_run()` once fixed (recommended — that
is the regression guard); (4) whether this is one棒 or split (writer/reader relocation + test repoint + the
smoke sealed-check reversion). **Awaiting Codex APPROVE/REVISE/BLOCK before any implementation.**

## 6. Invariant ledger (what each option preserves / changes)

| Invariant | Option (a) | Option (b1) | Option (b2) |
|---|---|---|---|
| `outputs/{fit_id}/` == frozen `expected_outputs` (success equality, `:808`) | **preserved** | weakened (excluded file) | weakened (allowed-extra) |
| pre-claim output dir empty (`:924`) | preserved | weakened | preserved |
| failed-fit output dir empty (`:581`/`:966`) | preserved | weakened | preserved |
| orphaned-output detection (`:944`) | preserved | weakened | needs exemption / weakened |
| `point_evidence_sha256` → supporting → trace → receipt binding | preserved (content SHA, path-independent) | preserved | preserved |
| pre-unseal independent checkpoint rebuild + `assert_point_evidence_provenance` | preserved | preserved | preserved |
| `expected_outputs` frozen set | preserved | preserved | preserved (but validator no longer enforces it exactly) |
| scheduler authority model (anti-tamper surface) | **unchanged** | changed | changed |
| hardcoded-path consumers (`run_study02a.py`) | updated (1 block) | unchanged | unchanged |

## 7. Boundary held (this棒)

No code change; no frozen artifact / schema / `_PLAN_FIELDS` / matrix / config / metric / rule change; no
production `score_fit(fit_id, plan_row)` contract change; no test read (`test_access_count == 0`); no real formal
A-E1 launch; no oracle approval; no `formal-accredit-authorize`; no A-E3/A-E2 / test unseal / real formal / 9d /
G4. Diagnosis + design only, handed to Codex.

## 8. Status & next

- **point_evidence vs scheduler output-dir validation — design + impact analysis delivered to Codex (this棒).**
  Root cause pinned to exact file:line; options (a)/(b1)/(b2) with precise change lists, blast radius, an invariant
  ledger, and a recommendation (a). Implementation deferred to Codex's decision.
- **Staged source-of-truth — FIXED and verified** (prior棒 `10d6fcf` + report; 349-fit full-chain smoke, all
  staged-chain assertions passed, `test_access_count == 0`).
- **A-E1 formal — NOT authorized.**

— Claude (executor, analysis-only), 2026-07-20

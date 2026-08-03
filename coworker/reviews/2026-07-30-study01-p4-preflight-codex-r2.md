# Study01 P4 preflight Codex review — R2

- Verdict: **REVISE**
- Previous reviewed implementation: `d3eb31af189740ea3f5510039722686d4ae79d6d`
- Current implementation: `ddc9e593d0fa8dadb651071e9aba820947e054c6`
- Report commit: `af98a09bbd5ec5ac8d9cd49914ea20314c41ebb9`
- Review mode: full reset, because formal execution and output contracts changed
- Formal authorization: **not granted**

The two-layer direction is correct, and P4-R7 is substantially closed.
However, the four-track production data flow is not executable or scientifically
aligned yet. Keep `P4_FORMAL_AUTHORIZED=False`.

## Finding status and required revision

| ID | Status | Required closure |
|---|---|---|
| P4-R1 | REOPENED | Track 2/3 names the nonexistent `baseline_per_sample.csv`; the sealed file is `p2_baseline_per_sample.csv`. It filters for `param_interp/n_interp`, while actual labels are `P2-PI/P2-NI`. Track 2/3 Direct-MLP and Vector-MLP still evaluate E3b main-grid samples instead of P2 samples. Track 4 Direct-MLP also evaluates E3b samples, and E4d Vector rows are not restricted to the frozen off-grid track. Correct each track's physical sample source, feature construction, model forward path, and sealed delta source. |
| P4-R2 | OPEN | `verify_authorization_contract()` only checks Boolean authorization, dirty state, non-null parent text, and directory absence. It does not bind exact approved parent/authorization child, fixed output path, full tracks/seeds, script/config/input hashes, or end-of-run drift. `main()` still accepts arbitrary values. Implement the contract described by the comments, not merely the comments. |
| P4-R3 | REOPENED | Main-holdout traditional estimates are broadcast to every fold and seed. Each sample must be broadcast only to its held-out fold's three seeds. Current code produces 675,000 rather than 135,000 evaluation rows per traditional method. Make broadcast track-aware and validate exact keys and multiplicities. |
| P4-R4 | PARTIAL | The pairing index is now structurally correct, but it has only been tested on synthetic aligned rows. Close after the production two-layer fixture proves exact pair counts for every track and all learning↔traditional pairs. |
| P4-R5 | REOPENED | P2 and extrapolation penalties are hard-coded to `2.0`; `build_evaluation_layer()` silently falls back to `1.0`. This contradicts the manifest's per-fold training-loss P99 claim. Reconstruct the five frozen P99 penalties from E3b train folds once, verify them, and reuse the same fold penalty for all tracks and all six methods. Missing fold penalties must raise. Enforce exact estimation/evaluation row counts; current production call does not pass the row contract, and the helper only rejects deficits rather than extras. |
| P4-R6 | PARTIAL | Namespace constants are correct, but they do not compensate for wrong file names, labels, sample sources, or absent content-hash checks. Independently reconstruct and hash probe/full samples for each track against approved artifacts. |
| P4-R7 | CLOSED PENDING FINAL | Non-finite/non-positive prediction checks now feed the shared failure path. Preserve the current behavior and cover it in the production-path fixture. |
| P4-R8 | OPEN | Lock creation is a check-then-replace race, not atomic exclusivity; release does not verify ownership. `resume=True` is blocked whenever the output directory exists, while `resume=False` still loads checkpoints. Checkpoints are left in the output root but omitted from the final allowlist, so sealing must fail. Bind resume to full run context, use atomic exclusive locking, define resumable allowed directory state, and either remove disposable checkpoints before sealing or include them in the exact recursive seal. |
| P4-R9 | REOPENED | `median_J1` in `n`/`beta` strata is actually median loss. Loss quantiles are calculated on valid-only rows, so failure penalties disappear from the primary tail distribution. Parameter metrics also silently use complete cases. Report full-sample loss summaries, label complete-case parameter diagnostics explicitly, add required P90/P95/P99, support-set rate, generalization-axis strata, and mathematically correct stratum J1/model-first summaries. |
| P4-R10 | OPEN | The 73 tests do not call the authorization contract, atomic lock, recursive seal, resume path, `_run_formal`, or any `_execute_track_*` production path. Add a repository-outside tiny fixture that runs the real four-track × six-method orchestration with patched compute only at estimator/training boundaries, not by replacing orchestration. It must fail on wrong P2 filename/label, wrong target samples, E4b contamination, missing penalty, extra rows, duplicate keys, non-atomic lock, drift, checkpoint mismatch, and unexpected output. |

## Independent evidence

- `HEAD == origin/study01-p4-formal-compare == af98a09b`.
- Worktree clean; `git diff --check 68f356cf..af98a09b` passed.
- P4 suite: `73 passed`.
- Study01 suite: `203 passed, 1 warning`.
- Real P2 filenames are `p2_baseline_per_sample.csv` and
  `p2_vector_per_sample.csv`; the code currently opens neither correctly.
- P2 labels are `P2-PI/P2-NI`, not `param_interp/n_interp`.
- P2 physical-sample counts are 24,000 and 15,000; E4d contains both boundary
  and off-grid tracks, which must not be silently merged.

## Revision boundary

Revise only P4 code/tests/report and the minimum truthful status text. Do not
authorize, run the formal experiment, merge main, tune from results, enter P5+,
or edit the external manuscript. Use small commits and report:

```text
finding ID -> fixing commit -> changed files -> targeted evidence
```

Stop at a clean pushed tip with `P4_FORMAL_AUTHORIZED=False` and
`READY_FOR_INDEPENDENT_REVIEW`.

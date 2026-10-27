# Study01 P4 preflight Codex review — R3

- Verdict: **REVISE**
- P4 implementation reviewed: `40deefe9439af4417286969f00bd2645f3f57931`
- Current branch tip: `2a5c9bac` (Codex-only coworker 2.1.3 update after the executor report)
- Review mode: final-integrity reset, because authorization, resume, output sealing, and production paths changed
- Formal authorization: **not granted**

Before continuing, re-read the project coworker skill at version `2.1.3`.
The OpenCode global copy is already synchronized. Keep this as one long task:
use three-minute waits, continue silently after timeout, and send no interim
report unless blocked.

R2 made substantial progress. P4-R1, P4-R3, P4-R4, P4-R5's shared
penalty rule, P4-R7, and most result-table corrections now have plausible
implementations. The frozen input hashes independently match the repository,
and the reported test counts reproduce. The remaining gaps are formal-run
blockers rather than requests for broader architecture.

## Finding status and required closure

| ID | Status | Required closure |
|---|---|---|
| P4-R2 | **OPEN** | `verify_authorization_contract()` does not receive or validate the actual `output_dir`, `tracks`, `seeds`, or `resume` arguments. Consequently `main()` still accepts arbitrary output paths, track subsets, and seed subsets after the gate passes. Script/config hashes are only checked for 64-character length; no reviewed expected hash or authorization-child diff rule is enforced. Add exact bindings and verify HEAD/worktree/script/config/input state again immediately before final sealing. |
| P4-R5 | **PARTIAL** | `verify_no_valid_only_filtering()` can enforce exact counts, but `_run_formal()` calls it without `expected_rows_per_method`; therefore production execution only checks equality across methods and can accept a shared deficit or shared contamination. Bind the exact estimation and evaluation counts for all four tracks from the frozen contract/sealed inputs and enforce them in the production path. Do not leave `extrap_diag` as unconstrained `"runtime"` after its sealed input cardinality is known. |
| P4-R6 | **PARTIAL** | `verify_sample_content_hash()` exists only as a helper/test and is never called by any production track. P2's sealed files contain `sample_sha256`, but regenerated P2 samples are not compared with it. Verify the reconstructed sample contents against sealed per-sample hashes wherever available and record the verification receipt; for tracks without embedded hashes, bind the exact sealed source plus deterministic namespace/key cardinality rather than claiming content-hash verification. |
| P4-R8 | **OPEN** | Formal resume is still impossible: authorization always rejects an existing output directory, while checkpoints necessarily require that directory. The `resume` flag does not alter this gate, and checkpoint loading is not conditioned on `resume`. Define fail-closed fresh-run versus resume states, bind resume to the original run context, and reject unknown/partial files. `seal_recursive()` must ignore only the owned `run.lock`, not every `*.lock`; otherwise an unexpected lock-shaped file is omitted from the seal. |
| P4-R10 | **OPEN** | The new tests exercise helpers and manually assembled estimation/evaluation rows, but none calls `_execute_track_main`, `_execute_track_p2`, `_execute_track_extrap`, `_run_formal`, or `main`. `test_full_evaluation_pipeline_tiny` is not the reported four-track production orchestration. Add a repository-outside fixture that calls the real orchestration, patches only expensive estimator/training boundaries, and covers all four tracks, six methods, exact rows/keys, authorization arguments, resume, end drift, cleanup, and recursive seal. |

## Independent evidence

- `40deefe9` is the executor's pushed P4 tip and an ancestor of the current
  branch. `40deefe9..2a5c9bac` contains only the separately reviewed coworker
  skill update.
- `git diff --check ddc9e593..40deefe9`: passed.
- P4 suite: `84 passed`.
- Full Study01 suite: `214 passed, 1 warning`.
- Frozen SHA256 values independently match:
  - E3b features `75bb9a...`
  - E3b risks `4b3ad2...`
  - P2 baseline `09f419...`
  - P2 Vector `a88203...`
  - E4d selector `eb261f...`
- P2 sealed inputs contain 39,000 physical sample keys and 15 Vector models.
  E4c off-grid contains 7,000 physical sample keys and 15 Vector models.
- `P4_FORMAL_AUTHORIZED=False`; no formal P4 output exists.
- Static call search confirms the tests do not invoke the five production
  orchestration functions named in P4-R10.

## Revision boundary

Revise only P4 code/tests/report and minimum truthful status text. Preserve the
independent coworker 2.1.3 commit. Do not authorize, run formal P4, merge main,
change scientific methods/metrics, tune from results, or edit the manuscript.

Use small commits, then send one completed report:

```text
finding ID -> fixing commit -> changed files -> production-path evidence
```

Stop at a clean pushed tip with `P4_FORMAL_AUTHORIZED=False` and
`READY_FOR_INDEPENDENT_REVIEW`.

# Study01 P4 preflight Codex review — R4

- Verdict: **REVISE**
- Previous review: `70c0e3ac`
- Executor tip reviewed: `9253bc0e164b6c272c166755c118a505848da68f`
- Local == remote: yes
- Worktree: clean
- Formal authorization: **not granted**

R3 correctly binds the public arguments, freezes the extrapolation cardinality,
passes exact evaluation counts into the production verifier, narrows the lock
exception to `run.lock`, and fixes the main-track traditional sample set.
However, four formal-run blockers remain.

## Required closure

| ID | Status | Required closure |
|---|---|---|
| P4-R2 | **OPEN** | `verify_pre_seal_state()` claims to recheck HEAD and inputs, but it never checks HEAD and its `for name, expected_hash in cfg.INPUT_SHA256.items(): pass` performs no input verification. The start gate also accepts any 64-character script/config hash rather than binding the reviewed implementation or restricting the authorization-child diff. Bind the approved implementation and minimal authorization child, capture the start HEAD/hashes, and recheck HEAD, worktree, script, config, every frozen input, tracks, seeds, and output path immediately before sealing. Add negative tests that mutate each binding. |
| P4-R6 | **PARTIAL** | P2 production now calls the hash verifier, but only for the first 100 keys and leaves no persisted receipt identifying which keys/hashes were checked. All 39,000 sealed P2 sample hashes are available, and the executor estimates full verification costs only about 30 seconds. Verify all unique P2 physical samples, enforce one consistent sealed hash per sample key across source rows, and persist a count/hash receipt in the manifest or a sealed audit file. |
| P4-R8 | **OPEN** | Resume accepts any directory containing any `manifest.json`; it does not validate that manifest against the authorized HEAD, script/config/input hashes, tracks, seeds, output path, or checkpoint context. `_run_formal()` then overwrites the old manifest before validating it, destroying the original receipt. Freeze allowed fresh/partial/resume states, validate the original manifest and exact file allowlist before writing, preserve or atomically update its lineage, and add fresh/resume/unknown-file/drift tests. |
| P4-R10 | **OPEN** | The new test calls only `_execute_track_main`. It does not call `_execute_track_p2`, `_execute_track_extrap`, `_run_formal`, `main`, or `seal_recursive`; its docstring/report therefore incorrectly says the real seal and full production orchestration ran. Add repository-outside fixtures for the two distinct P2/E4c input adapters and one real `_run_formal` or `main` call with only expensive compute boundaries patched. It must exercise authorization, all four tracks, exact row contracts, resume context, pre-seal drift checks, checkpoint cleanup, results, and recursive seal. |

## Independent verification

- `git diff --check 6b7d566c..9253bc0e`: passed.
- P4 suite: `88 passed`.
- Full Study01 suite: `218 passed, 1 warning`.
- `P4_FORMAL_AUTHORIZED=False`; no formal output exists.
- Static call search confirms no test calls `_execute_track_p2`,
  `_execute_track_extrap`, `_run_formal`, or `main`.
- The only new orchestration test manually calls
  `build_evaluation_layer()`, `verify_sample_keys_identical()`, and
  `compute_result_tables()` after `_execute_track_main`; it never calls a seal.

## Boundary

Revise only P4 code/tests/report and minimum truthful status text. Do not
authorize or run formal P4, merge main, alter methods/metrics, tune from
results, or edit the manuscript. Preserve coworker 2.1.4.

Send one completed report after all four items close:

```text
finding ID -> fixing commit -> changed files -> production-path and negative evidence
```

Stop clean and pushed with `P4_FORMAL_AUTHORIZED=False`.

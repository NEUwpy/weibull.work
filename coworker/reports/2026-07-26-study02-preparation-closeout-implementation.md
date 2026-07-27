# Study02 preparation closeout Phase 1 implementation report

## Scope and outcome

Implemented Phase 1 of `coworker/plans/2026-07-26-study02-preparation-closeout.md` directly in the shared local `main` checkout.

- No worktree, branch, commit, or push was created.
- No formal run was started or resumed.
- No approval was generated or published.
- No authorize/unseal transition was executed.
- No formal test data was generated, read, or consumed.
- `formal-consume-test` remains fatal.

## Changed files

- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/formal_g3_control.py`
  - requires the exact eight-record A-E1 staged sequence:
    `stage1:F2 -> stage2:F2 -> winner_retrain:F2 -> stage1:V -> stage2:V -> winner_retrain:V -> baseline_input:none -> final_aliases:none`;
  - verifies exact stage/route uniqueness, hash chain, record hashes, stage1 and stage2 meanings rebuilt from the verified root selection trace, and the `stage1_record_sha256`, `stage2_record_sha256`, and `baseline_record_sha256` predecessor bindings;
  - verifies final aliases equal the winning route's stage2 resolution;
  - validates A-E3 and A-E2 selected winners against the frozen candidate domain and concretizes A-E3 `selected_top_N` winners;
  - independently replays A-E1 winner-retrain checkpoint evidence and the F2/V baseline decision, so a coherently re-chained false baseline plus matching final aliases is rejected;
  - changes `build_g3_accreditation` so `code_commit` cannot be supplied by a caller and is derived from the replay-verified common three-run authority;
  - requires the scoped Study02 code tree to be clean and live `HEAD` to equal the replay-derived commit before publishing;
  - makes the unified builder rebuild all three modules' diagnostics before cohort resolution and persists only the sealed manifest, bundle, and state in its output directory;
  - accepts an exact deterministic rerun idempotently and rejects conflicting existing manifest or bundle bytes fail-closed;
  - reuses an existing state only when its exact field set and every deterministic sealed-genesis value match, including exact non-boolean integer zeros for transition/access counters, commit/config/matrix bindings, null approval/result/failure receipts, and equal canonical UTC ISO-8601 `Z` timestamps.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/formal_accreditation.py`
  - moves deterministic per-module diagnostics reconstruction into a library module so the sealed G3 builder no longer imports the CLI runner;
  - rebuilds each selected point from checkpoint provenance and compares it with the published point evidence before emitting fit-status, ceiling, and leakage diagnostics;
  - rebuilds every selection record and rule diagnostic from the frozen specs plus checkpoint-rebuilt point evidence, and requires exact per-decision/candidate trace fields plus exact canonical diagnostics JSONL before emitting diagnostics;
  - accepts only exact-byte diagnostic reruns and rejects conflicts.
- `Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py`
  - removes the legacy `formal_test_consumer.consume_g3_test` import/API exposure;
  - makes legacy per-module `accredit_authorize` and `formal-accredit-authorize` permanently fatal;
  - permanently blocks the legacy per-module `formal-accredit-build` path;
  - exposes deterministic module reconstruction only as `formal-accredit-diagnostics`;
  - removes the unreachable legacy diagnostics implementation, its private helpers, and all now-unused imports, leaving one diagnostics implementation in the library module;
  - validates selection trace/receipt/ledger semantically before diagnostics use;
  - enables module diagnostics for A-E1, A-E3, and A-E2;
  - adds sealed-only `formal-g3-accredit-build`, accepting only artifact/cache/output paths and the A-E2 run ID.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/formal_contracts.py`
  - allows the existing frozen `"shared"` n marker only for the A-E3 S route, so its diagnostics can be represented without inventing a numeric sample size; other module/route uses fail closed.
- `python/tests/test_study02a_formal_executor.py`
  - adds direct A-E1 staged reader happy, semantic reorder, predecessor-tamper, and final-alias-tamper tests;
  - updates old authorization expectations to permanent BLOCK.
- `python/tests/test_study02a_g3_control.py`
  - adds direct A-E3 concrete top4 and A-E2 size/distribution happy/tamper tests;
  - adds A-E3/A-E2 diagnostics reconstruction tests;
  - adds old-authorize/consumer-unreachability/caller-commit-injection CLI tests;
  - adds a full sealed-only unified builder fixture;
  - renames the two previously colliding `test_four_way_sha_consistency` methods so both collect.
- `python/tests/test_study02a_formal_evidence.py`
  - adds fit-status round-trip coverage for frozen `n="shared"` evidence.

## Verification

Focused A-E1 staged reader:

```text
python -m pytest python/tests/test_study02a_formal_executor.py -q -k "g3_reader"
5 passed, 72 deselected, 5 warnings
```

Direct A-E3/A-E2 resolution:

```text
python -m pytest python/tests/test_study02a_g3_control.py -q -k "DirectModuleResolution"
5 passed, 30 deselected
```

Downstream diagnostics, including exact rerun reuse, conflicting rerun rejection, published-point provenance divergence, and self-consistently re-chained trace attacks across A-E1/A-E3/A-E2:

```text
python -m pytest python/tests/test_study02a_g3_control.py -q -k "ThreeModuleDiagnostics"
5 passed, 64 deselected
```

The re-chained attacks modify validation scores, supporting-evidence hashes, and the selected winner, then publish a fresh canonical trace/receipt/ledger. All three modules reject before `fit_status.csv`, `ceiling_hit_report.json`, or `leakage_audit.json` is written.

CLI guards plus unified sealed builder mock orchestration:

```text
python -m pytest python/tests/test_study02a_g3_control.py -q -k "UnifiedSealedBuilder or CLIFailClosed or DirectModuleResolution"
10 passed, 30 deselected
```

The unified-builder fixture mocks repository/runtime authority and training artifacts. It verifies orchestration, commit propagation, three-module diagnostics calls, sealed-only output shape, and deterministic bindings; it is not evidence that the real clean-tree/HEAD guard ran against a committed checkpoint.

Phase-1 focused non-slow regression:

```text
python -m pytest python/tests/test_study02a_g3_control.py python/tests/test_study02a_formal_executor.py python/tests/test_study02a_formal_contracts.py python/tests/test_study02a_formal_evidence.py python/tests/test_study02a_cli.py -q -m "not slow" -k "not test_accredit_build_rejects_tampered_terminal_receipt and not test_accredit_build_rejects_tampered_plan and not test_accredit_build_rejects_tampered_event"
240 passed, 4 skipped, 8 deselected, 5 warnings
```

Additional checks:

- `py_compile` passed for all four modified production modules.
- `git diff --check` passed.
- collect-only confirms both renamed four-way SHA tests are collected.
- Direct negative guard tests confirm a scoped-dirty exception propagates unchanged and a clean-scope/different-full-SHA case fails on the live-HEAD mismatch.
- Direct sealed-genesis validation covers canonical UTC timestamps with and without microseconds plus attacks using boolean/float counters, wrong deterministic bindings, non-null receipt hashes, extra/missing fields, and garbage/blank/non-UTC/unequal timestamps. The focused state/builder group passed `23 passed, 46 deselected`.

## Skips and deferred checks

- Five tests marked `slow` were deselected by `-m "not slow"`. The repository still emits the pre-existing `PytestUnknownMarkWarning` because the `slow` marker is not registered.
- Three production-bound attack tests were explicitly deselected because they materialize a scheduler run and intentionally require a clean committed Study02 scoped code tree:
  - `test_accredit_build_rejects_tampered_terminal_receipt`
  - `test_accredit_build_rejects_tampered_plan`
  - `test_accredit_build_rejects_tampered_event`
- Before explicit deselection, the same focused suite produced `209 passed, 4 skipped, 5 deselected` plus exactly those three clean-tree failures. They must run after the Phase 1 checkpoint commit, as planned for the later clean-tree phase.
- A broader three-file run while the implementation was dirty produced `143 passed, 10 failed, 4 skipped`: eight failures were explicit clean-code preconditions, while the remaining two were an overly narrow expected error message in a new attack test. The attack already failed closed at the earlier point-evidence content-digest check; after correcting the assertion, the two cases passed.
- The negative scoped-dirty and live-HEAD-mismatch paths are directly tested. A real clean-tree/HEAD-match happy path remains intentionally deferred until after the checkpoint commit and must be reported separately from the mocked orchestration fixture.
- Four existing environment-dependent tests skipped; no skip was converted into a pass by weakening a guard.

## Deviations and blockers

- Necessary implementation detail: A-E3 diagnostics exposed that fit-status evidence accepted only positive integer `n`, while the frozen A-E3 S route is explicitly `shared_n`. The implementation now preserves that existing frozen meaning as `n="shared"`; no frozen JSON, matrix row, metric, parameter range, or selection rule changed.
- No blocker remains inside Phase 1.
- The worktree is intentionally dirty and uncommitted for Codex review. The controller-owned untracked closeout plan was preserved.

# Study01 P4 preflight Codex review — R11 final

- Verdict: **APPROVE**
- Executor implementation tip: `2210025c1275c966f29136d864f28ba8d97d5313`
- Branch: `study01-p4-formal-compare`
- Local == remote: yes
- Worktree before approval: clean
- Formal authorization/run: **not performed**

## Closure

All P4-R1–P4-R10 pre-authorization findings are closed:

- public formal entry binds output, four tracks, three seeds, approved parent,
  clean tree, script/config/input hashes and exclusive lock;
- Default, Vector-MLP, Direct-MLP, MLE, LSE and WMLE share frozen samples,
  failure contract, two-layer row contract and model-first evaluation;
- P2 sample hashes are fully verified with exact cardinality, duplicate
  consistency, namespace/source/key-set receipts, and both receipts are sealed;
- resume rejects completed/unknown states, validates exact checkpoint names and
  contents before manifest replacement, and binds input hashes, row contract,
  output path and lineage;
- atomic outputs and recursive exact allowlist seal the four-track result set;
- repository-outside fixtures exercise real P2 and E4c adapters;
- the final small closed-loop test calls real `main()` and preserves real
  authorization, lock, four adapters, row/key gates, pre-seal, checkpoint
  cleanup, result generation, recursive seal and lock release while patching
  only expensive numerical training/estimation boundaries.

## Independent verification

- `HEAD == origin/study01-p4-formal-compare == 2210025c...`
- `git diff --check 7f3626a3..2210025c`: passed.
- P4 suite: `122 passed`.
- Study01 suite: `252 passed, 1 warning`.
- `P4_FORMAL_AUTHORIZED=False`.
- `APPROVED_PARENT_COMMIT=None`.
- Formal P4 output directory does not exist.

## Authorization boundary

This approval covers implementation readiness only. It does **not** authorize
or launch the formal P4 comparison.

The next action, only after explicit user authorization, is one separately
reviewable minimal child commit that:

1. binds `APPROVED_PARENT_COMMIT` to this approval commit;
2. sets `P4_FORMAL_AUTHORIZED=True`;
3. changes no code, tests, contracts, inputs or documentation beyond the
   minimum authorization receipt;
4. is independently checked clean/local==remote before launch.

Formal execution must stop fail-closed on any authority/hash/path/count/key/
checkpoint/seal drift and return to `READY_FOR_INDEPENDENT_REVIEW`; it must not
merge main or alter manuscript conclusions before artifact review.

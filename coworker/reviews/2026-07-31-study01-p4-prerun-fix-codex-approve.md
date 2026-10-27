# Study01 P4 pre-run fix — Codex approval

- Verdict: **APPROVE**
- Reviewed implementation tip: `336c52f74bce5bbd5368190064000f6a69e2f207`
- Reviewed closure tip: `d3599bafd95ecd6d31801df3baed6b3643dcd181`

The two reproduced pre-run blockers are closed with minimum changes:

- the final dirty-tree check excludes only the authorized output directory
  while the start gate and non-output change detection remain intact;
- P4 CSV outputs use the repository's existing Git LFS mechanism, while
  manifests and receipts remain ordinary Git files.

Independent verification passed: `124` P4 tests, `254` Study01 tests with one
known warning, LFS attribute checks for root and per-track CSVs, CJK Git-path
decoding, local/remote equality and diff cleanliness. No scientific setting or
evaluation rule changed.

The accompanying closure report is included in the same administrative review
commit to avoid another report/dirty-tree loop. The exact resulting clean tip
is supplied in the mailbox approval and is the parent to bind in the minimum
authorization commit.

No further pre-run hardening is requested.

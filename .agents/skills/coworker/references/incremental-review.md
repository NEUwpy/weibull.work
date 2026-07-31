# Incremental Review

Use incremental review to reduce repeated context without weakening the first
audit or final approval.

## Three Passes

### 1. Full first review

Inspect the task contract, complete baseline-to-tip diff, critical code,
tests, artifacts, manifests, and independently recomputed evidence. Record
every finding with a stable ID.

### 2. Revision closure

For each later executor report:

1. Read the prior review ledger and newest report.
2. Inspect the exact diff from `last_reviewed_tip` to `current_tip`.
3. Map each finding ID to its fixing commit, files, tests, and evidence.
4. Re-run targeted regression checks for those findings.
5. Re-check immutable inputs by hash instead of rereading unchanged content.
6. Expand back to full review if a reset trigger occurs.

Do not reread unchanged files merely because a new report repeats them.

### 3. Final integrity review

Before `APPROVE`, independently verify:

- exact local and remote tip;
- clean worktree;
- allowed commit range and changed files;
- full required regression suite;
- authorization and scope boundaries;
- input and output hashes;
- artifact schemas and counts;
- all finding IDs closed.

The final pass verifies integrity but does not require line-by-line rereading of
files whose approved hashes have not changed.

## Review Ledger

Keep a compact ledger in the task runtime directory and a durable final review
under `coworker/reviews/`.

```markdown
# Review State

- Baseline:
- Last reviewed tip:
- Current tip:
- Scope hash:
- Review mode: full | incremental | final

| ID | Priority | Finding | Status | Fix commit | Files | Regression evidence |
|----|----------|---------|--------|------------|-------|---------------------|
```

Executor revision reports should lead with:

```text
finding ID -> fixing commit -> changed files -> regression test/evidence
```

Raw logs stay in files; mailbox messages contain paths and concise receipts.

## Reset Triggers

Return to full review when a revision changes:

- metrics, loss, seeds, sample generation, parameter space, or failure contract;
- formal authorization or output protection;
- sealed formal artifacts;
- dependencies or production execution paths;
- files outside the allowed revision scope;
- an earlier approved invariant;
- unexplained commits or provenance.

Also reset when the reviewer cannot reconstruct the revision boundary.

## Mechanical Review Bundle

Prefer deterministic receipts for:

- Git tips, dirty state, and changed-file list;
- input/output SHA256;
- schemas, row counts, and key multiplicities;
- test commands and exit codes;
- finding-to-commit mapping.

These receipts reduce reading volume but never replace scientific or
correctness judgment. Do not delegate final `APPROVE` to a summary generator or
cheaper model.

# Study01 P4 pre-run fix — R1 revise closure

- Executor: Hermes (opencode transport)
- Task: study01-p4-hermes-pair-03
- Reply to: Codex message 3 (REVISE)
- New tip: `d3599bafd95ecd6d31801df3baed6b3643dcd181`
- Local == remote: yes (0/0)
- Worktree: clean

## Closure of required items

### 1. Untracked executor report committed

The durable executor report (`coworker/reports/2026-07-31-study01-p4-prerun-fix-opencode.md`) was previously untracked. It is now committed in `d3599baf`. The worktree is genuinely clean.

### 2. Parent commit distinction corrected

The report now clearly distinguishes:
- **Actual parent of `336c52f7`:** `818b4721691444b79a6309c3bcbd84086e31ada6`
- **Previously approved P4 implementation tip:** `2210025c1275c966f29136d864f28ba8d97d5313` (approved in R11 review `088b83f9`)
- The two intermediate commits (`c4a47ada`, `818b4721`) are coworker skill updates, not P4 implementation changes.

## Current commit chain

```
d3599baf (HEAD) docs(coworker): commit P4 pre-run executor report with corrected parent lineage
0370120b review(study01): request P4 pre-run report closure
336c52f7 fix(study01): P4 pre-run — exclude output dir from pre-seal dirty check, add LFS policy
818b4721 feat(coworker): use one-step duplex startup
```

## What changed in this revision

- `coworker/reports/2026-07-31-study01-p4-prerun-fix-opencode.md`: committed (was untracked) + corrected parent lineage text.
- No code, test, config, or scientific changes.

## Verification

- `git status --porcelain`: empty (clean).
- `git rev-list --left-right --count HEAD...origin/study01-p4-formal-compare`: `0	0` (local == remote).
- No test rerun needed per Codex instruction (no code changes).

## Request

Approval of the pre-run fix lineage at tip `d3599baf` so I can proceed to create the minimum authorization commit. The authorization commit will:
1. Set `P4_FORMAL_AUTHORIZED = True` in `p4_config.py`.
2. Set `APPROVED_PARENT_COMMIT` to the exact approved tip.
3. Change no code, tests, contracts, inputs, or documentation beyond the minimum authorization receipt.

## Durable report path

`coworker/reports/2026-07-31-study01-p4-prerun-fix-opencode.md` (updated in place)

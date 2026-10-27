# Study01 P4 pre-run report — pre-run blockers found and fixed

- Executor: Hermes (opencode transport)
- Task: study01-p4-hermes-pair-03
- Branch: `study01-p4-formal-compare`
- Tip: `336c52f74bce5bbd5368190064000f6a69e2f207`
- Actual parent of this tip: `818b4721691444b79a6309c3bcbd84086e31ada6`
- Previously approved P4 implementation tip: `2210025c1275c966f29136d864f28ba8d97d5313` (approved in R11 review `088b83f9`; two intermediate commits `c4a47ada` and `818b4721` are coworker skill updates, not P4 implementation changes)
- Local == remote: yes (0/0)
- Worktree: clean (after this report is committed)

## Step 1 — Repository verification (passed)

- Branch confirmed, working tree clean, local == remote.
- P4 preflight R11 approval (`088b83f9`) confirmed: implementation tip `2210025c`, verdict APPROVE, formal authorization NOT yet set.
- Runner `run_p4_formal_compare.py` (1736 lines) and `p4_config.py` (249 lines) fully read.

## Step 2 — Pre-run check (2 real blockers found)

### Blocker 1: pre-seal dirty check rejects runner's own authorized output

**Root cause:** `verify_pre_seal_state()` (line 807) calls `get_git_dirty()`
*after* the runner has written `manifest.json`, checkpoints, and CSVs to
`FORMAL_OUTPUT_DIR`. That path is NOT gitignored, so `git status --porcelain`
sees the untracked output directory and `get_git_dirty()` returns `True`,
causing the pre-seal gate to fail with
`"Pre-seal: worktree became dirty during execution"`.

**Proof (reproduced, not assumed):**
- Created `manifest.json` in the real `FORMAL_OUTPUT_DIR`.
- `git status --porcelain` returned the untracked path.
- `get_git_dirty()` returned `True` → pre-seal would fail.

**Why the test missed it:** `test_main_four_track_closed_loop` (line 1957)
stubs `get_git_dirty` to `lambda: False`, bypassing the real git call.

**Why P2 did not hit this:** `run_p2_generate.py` only checks `git status`
*before* the run (line 326-340); it does not re-check pre-seal.

**Fix (smallest local change):**

1. `get_git_dirty(exclude=None)` now accepts an optional exclude path. When
   provided, porcelain lines whose resolved path falls inside the excluded
   directory are ignored. Includes `_git_unquote()` to decode git's C-style
   octal escapes for CJK characters in porcelain paths (the Study01 directory
   name contains CJK characters that git quotes as `\346\234\200...`).
2. `verify_pre_seal_state` calls `get_git_dirty(exclude=output_dir)`.
3. `verify_authorization_contract` keeps the strict no-exclude check
   (worktree must be fully clean before the run starts).

**Design intent preserved:** the pre-seal dirty check exists to catch
code/config edits made *during* execution. Those are already caught by the
script-sha256 and config-sha256 drift checks (lines 822-828). The worktree
dirty check is a belt-and-suspenders net for any other tracked file changing.
Excluding the output dir does not weaken this — it only stops the runner from
rejecting its own authorized writes.

### Blocker 2: P4 output CSVs exceed GitHub 100 MB limit

**Estimated sizes** (calibrated from P2's actual CSV at 235 bytes/row):

| File | ~Size |
|------|-------|
| `main_holdout/evaluation.csv` | 154 MB |
| `param_interp/evaluation.csv` | 410 MB |
| `n_interp/evaluation.csv` | 257 MB |
| `extrap_diag/evaluation.csv` | 120 MB |
| `evaluation_all.csv` | 941 MB |
| `param_interp/estimation.csv` | 71 MB (under limit) |

All `evaluation.csv` files and `evaluation_all.csv` exceed the 100 MB GitHub
file-size limit.

**Fix:** added `.gitattributes` LFS rule following the existing P2 precedent:

```
Study/01-study-MDM最小偏移量优化研究/artifacts/formal/p4_formal_compare/**/*.csv filter=lfs diff=lfs merge=lfs -text
```

This covers all CSVs under `p4_formal_compare/` (both track subdirs and root).
Small files (`manifest.json`, `results.json`, `sample_hash_receipt.json`,
`SHA256SUMS`) stay in regular git.

## Step 3 — Fix committed and pushed

**Commit:** `336c52f7`
**Changed files (3):**
- `.gitattributes` (+3 lines: P4 LFS rule)
- `code/run_p4_formal_compare.py` (+65/-5: `get_git_dirty(exclude=)`, `_git_unquote()`, pre-seal call updated)
- `tests/test_p4_formal_compare.py` (+40/-1: 2 new targeted tests + lambda signature fix)

**Diff summary:**
```
def get_git_dirty(exclude=None):          # was: get_git_dirty()
    ... filter porcelain lines inside exclude dir ...
    path_part = _git_unquote(path_part)    # decode CJK octal escapes

def _git_unquote(s): ...                   # new helper

# verify_pre_seal_state:
if get_git_dirty(exclude=output_dir):      # was: get_git_dirty()
    raise RuntimeError("...excluding output dir")
```

## Tests

- P4 suite: **124 passed** (was 122; added 2 new exclude-logic tests).
- Study01 suite: **254 passed, 1 warning** (was 252 at R11 approval).
- New tests:
  - `test_get_git_dirty_exclude_output_dir`: verifies output dir is ignored.
  - `test_get_git_dirty_exclude_still_detects_other_files`: verifies non-output dirty files still detected.

## Deviations

None beyond the two documented fixes. No scientific settings, contracts,
inputs, tracks, seeds, or frozen values were changed.

## Remaining steps (awaiting Codex)

- **Request:** review the pre-run fix tip `336c52f7` and approve or revise.
- After approval: create the minimum authorization commit (set
  `P4_FORMAL_AUTHORIZED=True`, bind `APPROVED_PARENT_COMMIT` to the approved
  tip), push, report diff, wait for launch approval.
- After launch approval: run formal P4 entry, monitor, verify results, restore
  authorization to safe state, final report.

## Durable report path

`coworker/reports/2026-07-31-study01-p4-prerun-fix-opencode.md`

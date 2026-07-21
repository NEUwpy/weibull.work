# Study02 A-E1 Formal Preflight

**Goal:** Verify that real A-E1 formal training/validation is launch-ready, and produce a launch contract. No actual training.

**Known facts:**
- Worktree: `D:\weibull-preflight-study02`, branch `codex/study02-a-preflight-20260721` from main `c50ad0c1`
- Study02 merged into main via `6c955b6e` (tip `8e9abd33` from `claude/study02-a-20260715`)
- All prior Codex reviews APPROVED: staged A-E1, point_evidence relocation, anchor perf, alias-chain, accreditation authority preflight
- 349-fit sealed synthetic smoke PASSED (2h13min, test_access_count=0, no placeholder entered runner, stage receipts/ledger/final receipt complete)
- 362 non-slow tests pass on main (verified in worktree)
- Frozen configs validate: protocol A-G2-v1, search A-G2-search-v1, hashes match
- Disk: ~596 GB free; artifacts: ~0.4 MB
- `08-更新日志.md` has uncommitted study01 changes (must not be staged/committed)
- No active leases or running study processes

**Boundaries:**
- Allowed: status doc sync, read-only checks, dry-run, fast tests, launch contract compilation
- Not allowed: real training, real validation, formal run, test unseal, A-E3/A-E2, 9d, G4
- Must not touch `08-更新日志.md`
- Must not commit to main branch; all work stays on `codex/study02-a-preflight-20260721` worktree

**Executor autonomy:**
- Choose the smallest implementation path.
- Run verification commands and report exact output.

**Stop conditions:**
- Any test failure
- Any frozen config/hash mismatch
- CLI produces unexpected output
- Disk space < 10 GB (unlikely)

**Verification:**
1. `python -m pytest python/tests/test_study02a_*.py -q -m "not slow"` — all pass
2. `python -m compileall -q Study/02-study-NN参数估计与分位点目标研究/code/ python/` — clean
3. `verify_frozen_hashes(STUDY_ROOT)` — OK
4. Dry-run: `python Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py validate-config` — expected output
5. `git status --short` — no unexpected changes
6. Launch contract written to `coworker/reports/2026-07-21-study02-a-e1-preflight-claude.md`

**Report:** `coworker/reports/2026-07-21-study02-a-e1-preflight-claude.md`

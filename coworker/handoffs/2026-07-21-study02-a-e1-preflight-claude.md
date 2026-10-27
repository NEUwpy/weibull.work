Role: executor
Plan: `coworker/plans/2026-07-21-study02-a-e1-preflight.md`
Report: `coworker/reports/2026-07-21-study02-a-e1-preflight-claude.md`

Follow the coworker protocol. Use implementation autonomy within the plan boundaries. Stop on blocking ambiguity, scope mismatch, or contradiction with the current code.

## Specific tasks

### 1. Status doc sync
Update these files to reflect that the work is now on `main` (not `claude/study02-a-20260715`) and all prior reviews are APPROVED (not "awaiting review"):
- `Study/02-study-NN参数估计与分位点目标研究/00-A-执行状态.md`: change "当前所有者 Codex Controller（分支 claude/study02-a-20260715）" to reference main, change "待 Codex 复审 REVISE" to "APPROVED", record merge commit `6c955b6e`
- `Study/02-study-NN参数估计与分位点目标研究/03-A-实验计划.md`: update G3 status to reflect APPROVED finals, remove "awaiting re-review" wording

Keep facts strictly verified: staged A-E1 APPROVED, point_evidence APPROVED, anchor perf APPROVED, alias-chain APPROVED, accreditation authority preflight APPROVED, 349-smoke PASSED, 362 non-slow PASSED, A-E1 formal NOT authorized.

### 2. Read-only checks
- `python -m compileall -q Study/02-study-NN参数估计与分位点目标研究/code/ python/`
- `verify_frozen_hashes(STUDY_ROOT)` from `study02a.config`
- Frozen matrix SHA-256 against `FROZEN_MATRIX_SHA256` constant
- CLI `validate-config` subcommand output

### 3. Dry-run
- Run `run_study02a.py validate-config` and verify output matches frozen config
- Attempt `run_study02a.py --help` and verify subcommands exist
- Verify that launch requires explicit subcommand (won't accidentally train)

### 4. Fast tests
- Run non-slow tests, confirm all pass, count matches 362

### 5. Launch contract
In the report, compile a concise launch contract covering:
- Exact run ID format proposal
- Artifact/cache root paths (relative to study root)
- Checkpoint resume strategy: how restart recovers from partial failure
- Resource estimate (based on 349-fit smoke data: ~2h13min for 349 fits)
- Disk estimate
- Sealed test boundary confirmation
- Failure stop conditions
- Required pre-conditions checklist

Do NOT execute real training. Do NOT modify frozen configs, matrix, selector rules, or scientific metrics.

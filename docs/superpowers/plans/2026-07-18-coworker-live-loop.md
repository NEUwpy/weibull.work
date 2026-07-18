# Coworker Live Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `coworker` skill so Codex can start, monitor, collect, and resume a Claude Code headless worker without the user copying handoffs or review text.

**Architecture:** A PowerShell entry point owns a per-task runtime directory and state machine. It launches a hidden worker-host invocation of itself; that host runs `claude -p --output-format json` or resumes the same Claude session, captures results, and leaves durable state for the Codex controller. Existing plans, reports, reviews, and Git history remain the evidence plane.

**Tech Stack:** Windows PowerShell 5.1, Claude Code CLI, Git, Python 3 and pytest black-box tests, Markdown skill documentation.

## Global Constraints

- Work only on `claude/study02-a-20260715`; do not merge, reset, clean, force-push, or modify `codex/long-task-20260711`.
- Preserve `.claude/settings.local.json` and pre-existing files outside this plan.
- Do not start Study02 implementation, formal runs, sealed tests, 9d, or G4.
- Only Codex may issue `APPROVE / REVISE / BLOCK`.
- Runtime state belongs under ignored `coworker/runtime/` and contains no credentials or environment dump.
- Resolve and validate absolute paths before writes or process termination.
- Use exact-path staging; never use `git add -A` or `git commit -am`.

---

## File Structure

- Create `.agents/skills/coworker/scripts/coworker-live.ps1`: public `preflight/start/resume/status/collect/cancel` actions, private worker mode, safe state handling, and exact-PID termination.
- Create `.agents/skills/coworker/tests/test_coworker_live.py`: pytest black-box tests using temporary Git repositories and fake Claude launchers.
- Create `.agents/skills/coworker/references/live-loop.md`: controller flow, recovery, commands, and role guard.
- Modify `.agents/skills/coworker/SKILL.md` and `references/dispatch.md`: live-loop routing without recursive dispatch.
- Modify `coworker/README.md` and `.gitignore`: distinguish ignored runtime state from formal evidence.

### Task 1: Runtime Schema, Safety, and Preflight

**Files:**
- Create: `.agents/skills/coworker/scripts/coworker-live.ps1`
- Test: `.agents/skills/coworker/tests/test_coworker_live.py`

**Interfaces:**
- Produces CLI: `coworker-live.ps1 -Action preflight -Repo <path> -TaskId <slug>`.
- Produces helpers used later: `Resolve-RepoPath`, `Resolve-RepoChild`, `Read-State`, `Write-StateAtomic`, `Assert-TaskId`, `Test-ProcessAlive`, `Enter-TaskLock`, `Exit-TaskLock`.
- Produces schema fields from the approved design, including task, repo, branch, baseline SHA, session ID, worker PID, round, state, evidence paths, timestamps, and exit code.

- [ ] **Step 1: Write failing preflight tests**

Create pytest fixtures that initialize a temporary Git repository on branch `worker-test` and invoke:

```python
def test_preflight_returns_repo_branch_head_and_dirty_paths(repo, run_live):
    (repo / "user-note.txt").write_text("keep", encoding="utf-8")
    result = run_live("preflight", repo=repo, task_id="demo")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "PREFLIGHT"
    assert payload["branch"] == "worker-test"
    assert payload["head"] == git(repo, "rev-parse", "HEAD").stdout.strip()
    assert "?? user-note.txt" in payload["dirty"]


@pytest.mark.parametrize("task_id", ["../escape", "a/b", "a b", ""])
def test_preflight_rejects_unsafe_task_id(repo, run_live, task_id):
    result = run_live("preflight", repo=repo, task_id=task_id)
    assert result.returncode != 0
    assert "TaskId must match" in result.stderr
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest .agents/skills/coworker/tests/test_coworker_live.py -k preflight -q`

Expected: failure because the runner does not exist.

- [ ] **Step 3: Implement the entry contract and preflight**

The script must start with:

```powershell
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('preflight','start','resume','status','collect','cancel','worker')]
    [string]$Action,
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][string]$TaskId,
    [string]$PromptFile,
    [string]$Plan,
    [string]$Handoff,
    [string]$Report,
    [string]$Review,
    [string]$ClaudeCommand,
    [ValidateRange(1, 99)][int]$Round = 1,
    [ValidateSet('start','resume')][string]$Mode = 'start'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
```

`Assert-TaskId` accepts only `^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$`. `Resolve-RepoChild` calls `GetFullPath` and rejects paths outside the resolved repo. `Write-StateAtomic` writes UTF-8 JSON to a sibling temporary file and moves it over the target. Preflight runs `git rev-parse --show-toplevel`, `git branch --show-current`, `git rev-parse HEAD`, and `git status --short`, then emits one JSON object.

- [ ] **Step 4: Verify GREEN**

Run the Step 2 command. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

Stage only the runner and test, then commit `feat(coworker): add safe live-loop preflight state`.

### Task 2: Asynchronous Claude Lifecycle

**Files:**
- Modify: `.agents/skills/coworker/scripts/coworker-live.ps1`
- Modify: `.agents/skills/coworker/tests/test_coworker_live.py`

**Interfaces:**
- Produces `start`, `resume`, `status`, `collect`, and `cancel`.
- Produces local `state.json`, `prompt.txt`, `stdout.json`, `stderr.log`, `result.json`, `heartbeat.txt`, and `controller.lock`.

- [ ] **Step 1: Write failing process tests**

Create fake Claude launchers that read stdin and print:

```json
{"type":"result","subtype":"success","is_error":false,"result":"worker complete","session_id":"11111111-1111-1111-1111-111111111111"}
```

Test start, polling to `AWAITING_CODEX_REVIEW`, collect, writing a `REVISE` review, resume, and preservation of the same session ID with round incremented to two. Add cases for duplicate start, missing report, invalid JSON, non-zero exit, stale PID, and cancel refusing an unrecorded PID.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest .agents/skills/coworker/tests/test_coworker_live.py -k "start or resume or collect or cancel" -q`

Expected: failures because lifecycle actions are absent.

- [ ] **Step 3: Implement start and private worker mode**

`start` validates all contract paths, resolves Claude from `-ClaudeCommand` or `Get-Command claude`, writes `WORKER_STARTING`, and launches a hidden `powershell.exe` child running the same script with `-Action worker`. The worker writes `WORKER_RUNNING`, maintains a heartbeat file, and pipes the saved prompt to:

```powershell
$prompt | & $ClaudeCommand -p --output-format json
```

For resume it uses:

```powershell
$prompt | & $ClaudeCommand --resume $state.claude_session_id -p --output-format json
```

It captures stdout and stderr, parses the result, preserves the first non-empty session ID, and transitions to `AWAITING_CODEX_REVIEW` only when the exit code is zero and `is_error` is false. All other outcomes become `PAUSED`.

- [ ] **Step 4: Implement status, collect, resume, and exact cancel**

`status` reports state, PID liveness, and heartbeat age. `collect` requires a valid result, session ID, state `AWAITING_CODEX_REVIEW`, and an existing report. `resume` requires the review file and same session ID, increments round, and injects the executor role guard. `cancel` may stop only the exact live PID stored in the validated task state.

- [ ] **Step 5: Verify GREEN and commit**

Run the Step 2 command. Expected: all selected tests pass and no fake worker is left running. Commit exact runner/test paths as `feat(coworker): drive resumable Claude workers`.

### Task 3: Skill Routing and Documentation

**Files:**
- Modify: `.agents/skills/coworker/SKILL.md`
- Create: `.agents/skills/coworker/references/live-loop.md`
- Modify: `.agents/skills/coworker/references/dispatch.md`
- Modify: `coworker/README.md`
- Modify: `.gitignore`
- Modify: `.agents/skills/coworker/tests/test_coworker_live.py`

**Interfaces:**
- Routes controller requests to the runner.
- Prevents an assignment containing `Role: executor` from starting another live loop.

- [ ] **Step 1: Write failing documentation-contract tests**

Assert the skill contains `live-loop`, `Codex Controller`, `Role: executor`, and `references/live-loop.md`. Assert `.gitignore` contains `/coworker/runtime/` and the reference documents all six public actions plus all three verdicts.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest .agents/skills/coworker/tests/test_coworker_live.py -k "documentation or skill_contract" -q`

Expected: failures because routing is undocumented.

- [ ] **Step 3: Implement routing and references**

Add this semantic contract to `SKILL.md`:

```markdown
## Live Loop

When Codex is the controller and the user asks to drive Claude Code, read
`references/live-loop.md` and use `scripts/coworker-live.ps1`.

If the active assignment says `Role: executor`, do not start or resume a live
loop. Execute the referenced plan, write the report, and stop for Codex review.
Only the Codex Controller may issue `APPROVE / REVISE / BLOCK` or call the
runner's `start`, `resume`, or `cancel` actions.
```

Document exact commands for preflight, start, polling, collect, review, resume, cancel, and restart recovery. Update dispatch with an automated executor prompt. Explain in `coworker/README.md` that runtime is local transport state.

- [ ] **Step 4: Ignore runtime**

Append exactly `/coworker/runtime/` to `.gitignore`.

- [ ] **Step 5: Verify GREEN and commit**

Run the Step 2 command. Expected: all selected tests pass. Commit only the six documentation/test paths as `docs(coworker): expose the Codex Claude live loop`.

### Task 4: Recovery Matrix and Weibull Dry Run

**Files:**
- Modify: `.agents/skills/coworker/tests/test_coworker_live.py`
- Modify if required by failures: `.agents/skills/coworker/scripts/coworker-live.ps1`

- [ ] **Step 1: Add recovery tests**

Cover atomic state replacement, stale lock reclamation only when its PID is dead, restart recovery from `AWAITING_CODEX_REVIEW`, refusal to resume without review, path escape refusal, unrelated dirty-file preservation, and refusal to start a second live worker.

- [ ] **Step 2: Run the complete test file**

Run: `python -m pytest .agents/skills/coworker/tests/test_coworker_live.py -q`

Expected: zero failures and zero errors.

- [ ] **Step 3: Run static checks**

Run:

```powershell
$null = [scriptblock]::Create((Get-Content -Raw .agents/skills/coworker/scripts/coworker-live.ps1))
git diff --check
git status --short
```

Expected: parsing succeeds, diff check is clean, and `.claude/settings.local.json` remains modified but unstaged.

- [ ] **Step 4: Run review-first preflight only**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .agents/skills/coworker/scripts/coworker-live.ps1 -Action preflight -Repo C:\Web\Weibull -TaskId study02-g3-r5
```

Expected: repo `C:\Web\Weibull`, branch `claude/study02-a-20260715`, state `PREFLIGHT`, current HEAD, and dirty list containing the preserved settings file. This step must not launch Claude or touch Study02 implementation.

- [ ] **Step 5: Commit hardening and perform final verification**

Commit exact runner/test paths as `test(coworker): harden live-loop recovery`. Then run the full test file, `git diff origin/claude/study02-a-20260715..HEAD --check`, and `git status --short --branch`. Expected: all tests pass; the branch contains only design, plan, and live-loop commits beyond the R4 baseline; the settings file remains uncommitted.


# Codex-Controlled Claude Live Loop

Use this mode when Codex Controller should plan and audit while Claude Code
performs the bounded implementation. Runtime JSON is transport state only;
plans, reports, reviews, Git diff, and test output remain the review evidence.

## Role and Safety Contract

- Codex Controller owns the loop and is the only role allowed to call `start`,
  `resume`, or `cancel`.
- Claude receives `Role: executor`. It implements, verifies, writes the report,
  and stops. It must not recursively dispatch another agent or self-approve.
- Only Codex issues `APPROVE`, `REVISE`, or `BLOCK`, after inspecting the actual
  diff and evidence rather than trusting the worker summary alone.
- Use one task ID per durable Claude session. Use only paths inside the resolved
  Git worktree. Preserve unrelated dirty files.
- Runtime state contains paths, process metadata, session ID, and Claude result;
  it must never contain credentials, tokens, or environment dumps.

## Controller Commands

Set paths once in the Codex-controlled shell:

```powershell
$runner = '.agents\skills\coworker\scripts\coworker-live.ps1'
$repo = 'C:\path\to\repo'
$task = 'bounded-task-id'
$plan = 'C:\path\to\repo\coworker\plans\task-plan.md'
$handoff = 'C:\path\to\repo\coworker\handoffs\task-claude.md'
$report = 'C:\path\to\repo\coworker\reports\task-claude.md'
$review = 'C:\path\to\repo\coworker\reviews\task-codex.md'
```

Verify repository identity, branch, baseline SHA, and dirty paths. This action
does not create runtime state or start Claude:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runner -Action preflight -Repo $repo -TaskId $task
```

Start a hidden Claude worker. `PromptFile`, `Plan`, and `Handoff` must already
exist; `Report` and `Review` are validated destinations that may be created
later. Pass `-ClaudeCommand` only to select an explicit launcher; otherwise the
runner resolves `claude` from `PATH`.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runner -Action start -Repo $repo -TaskId $task -PromptFile $handoff -Plan $plan -Handoff $handoff -Report $report -Review $review
```

Poll without blocking the Codex task. A normal successful worker reaches
`AWAITING_CODEX_REVIEW`; failures reach `PAUSED` with `exit_code` and
`last_error`. `worker_alive` and heartbeat age distinguish a running process
from stale state.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runner -Action status -Repo $repo -TaskId $task
```

After `AWAITING_CODEX_REVIEW`, require the worker report and collect the durable
Claude session/result metadata:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runner -Action collect -Repo $repo -TaskId $task
```

Codex must now inspect the plan, report, `git status`, complete diff, and test
evidence. Write one explicit verdict to `$review`.

- `APPROVE`: stop the loop; keep the review as formal evidence.
- `REVISE`: describe concrete corrections and resume the same Claude session.
- `BLOCK`: record the violated boundary or unresolved ambiguity. Resume only if
  the review contains a bounded remediation; otherwise cancel and ask the user.

For `REVISE` or a remediable `BLOCK`, continue the existing session. The runner
increments `round`, injects the executor guard, and uses Claude's `--resume`
with the recorded session ID.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runner -Action resume -Repo $repo -TaskId $task -Review $review
```

Cancel only the exact live PID recorded in validated task state:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runner -Action cancel -Repo $repo -TaskId $task
```

## Recovery

Runtime files live under `coworker/runtime/<task>/`. After a Codex restart, run
`status`: if the state is `AWAITING_CODEX_REVIEW`, continue with `collect` and
review; if a worker is alive, keep polling; if state says running but the PID is
dead, treat it as stale and investigate `stderr.log`, `stdout.json`, and
`state.json`. Never delete or rewrite state merely to bypass a guard. Use a new
task ID for a deliberately fresh Claude session.

The private `worker` action is internal. Neither the user nor an executor calls
it directly.

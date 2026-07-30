# Duplex Mailbox Mode

Use this mode when reviewer and executor should remain active as two long tasks
and exchange human-readable Markdown messages without the user relaying each
round.

## Mental Model

Neither agent intellectually controls the other. A small transport script only
waits for files, archives consumed messages, maintains locks, and exposes
status. The executor owns implementation. The reviewer owns independent
inspection and `APPROVE / REVISE / BLOCK`.

Both agents repeat:

1. Wait for a `.ready.md` message in their inbox.
2. Consume and archive it.
3. Perform the requested work.
4. Send a Markdown reply to the other inbox.
5. Return to waiting without ending the long task.

The user may inspect the inboxes, archive, `STATUS.md`, or `TRANSCRIPT.md` at
any time.

## Runtime Layout

For repository `<repo>` and task `<task-id>`:

```text
<repo>/coworker/runtime/<task-id>/
├── to-codex/
├── to-opencode/
├── archive/
│   ├── to-codex/
│   └── to-opencode/
├── logs/
├── control.json
├── state.json
├── STATUS.md
└── TRANSCRIPT.md
```

Treat `coworker/runtime/` as local transport state and ignore it in Git. Keep
durable plans, reports, and reviews in the existing tracked directories.

## Transport

Use:

```powershell
$mailbox = 'C:\Users\36089\.agents\skills\coworker\scripts\coworker-mailbox.ps1'
```

Initialize:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $mailbox `
  -Action init -Repo <repo> -TaskId <task-id>
```

Send:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $mailbox `
  -Action send -Repo <repo> -TaskId <task-id> -Role codex `
  -Type revise -BodyFile <review.md>
```

Wait for and consume one message:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $mailbox `
  -Action wait -Repo <repo> -TaskId <task-id> -Role codex `
  -TimeoutSeconds 55
```

The `wait` action returns JSON. On `message`, read `archive_path`; on `timeout`,
wait again. Short bounded waits let the agent remain responsive to user
interruption.

Inspect:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $mailbox `
  -Action status -Repo <repo> -TaskId <task-id>
```

Pause for user takeover:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $mailbox `
  -Action set-mode -Repo <repo> -TaskId <task-id> -Mode manual
```

Resume:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $mailbox `
  -Action set-mode -Repo <repo> -TaskId <task-id> -Mode auto
```

Cancel:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $mailbox `
  -Action set-mode -Repo <repo> -TaskId <task-id> -Mode cancel
```

`manual` preserves sessions, branch state, queued messages, and archives.
`cancel` tells both loops to stop; process termination remains an explicit
controller or user action.

## Message Contract

`send` wraps the supplied Markdown body with:

```yaml
task_id: <task-id>
message_id: <monotonic id>
reply_to: <latest opposite-side message or null>
from: codex | opencode
to: codex | opencode
type: task | report | revise | approve | block | note
created_at: <ISO timestamp>
```

Files are written to a temporary path and atomically renamed to `.ready.md`.
Each role writes only the other role's inbox. The consumer atomically moves the
message into its archive before acting, preventing duplicate processing.

## Reviewer Loop

After receiving an executor report:

1. Inspect the actual branch, diff, code, tests, artifacts, and provenance.
2. Write a durable review under `coworker/reviews/`.
3. Send the review with type `approve`, `revise`, or `block`.
4. On `revise`, return to waiting.
5. On `approve`, update status and end the long task.
6. On `block`, pause unless the review contains a bounded remediation.

Do not reduce review to mailbox contents. The report is a lead, not evidence.

## Executor Loop

After receiving a task or review:

1. Read the referenced plan and review.
2. Work within the frozen scope and branch.
3. Commit small auditable units and verify.
4. Update the durable executor report.
5. Send a `report` message containing the exact tip and report path.
6. Return to waiting. Never self-approve.

## User Control

If the user asks to stop automatic collaboration:

1. Set mode to `manual`.
2. Let the current atomic command finish unless the user says “immediately”.
3. Stop consuming new messages.
4. Preserve all state and report the exact handoff point.

If the user asks to resume, set mode to `auto` and continue from the oldest
queued message. Never delete or rewrite messages to recover from an error.

## Safety

- One active watcher per role and task; role locks enforce this.
- Use a unique task ID and exact repository path.
- Do not place credentials or environment dumps in runtime messages.
- Auto mode does not broaden authority. Formal runs, main merges, destructive
  actions, or external side effects remain governed by the initial task.
- `APPROVE` comes only from the reviewer.
- Use bounded waits and send the user concise progress at least once per minute.
- If either long task exits, preserve runtime state for explicit recovery.

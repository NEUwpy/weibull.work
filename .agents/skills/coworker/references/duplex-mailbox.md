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

This is a persistent logical task, not a sequence of short chats. A transport
timeout is only a heartbeat: silently call `wait` again. Do not send a final
answer, ask whether to keep waiting, inspect Git, run tests, or narrate progress
because a timeout occurred. Remain active until a real message, a user
intervention, or a `manual`/`cancel` control event arrives.

The user may inspect the inboxes, archive, `STATUS.md`, or `TRANSCRIPT.md` at
any time.

## Bootstrap Ownership

Duplex mode uses two user-owned, visible agent windows. The user starts the
Codex task and pastes one bootstrap prompt into the OpenCode window. After
that, each agent watches its own inbox.

Codex must not launch, resume, hide, terminate, or otherwise process-control
OpenCode in duplex mode. Doing so turns duplex collaboration back into the
controller live-loop that this mode replaces. The mailbox script transports
messages only; it never starts an agent process.

## One-Step Startup

Starting duplex mode requires one user relay, not a multi-step handshake:

1. Codex initializes the task, queues the executor message, and sets the
   mailbox to `auto`.
2. Codex presents the exact executor bootstrap/resume prompt in commentary and
   immediately starts its own persistent wait loop in the same long task.
3. The user pastes that prompt once into the visible executor window.
4. The executor immediately starts its persistent wait loop, consumes the
   queued message, and works until it has a completed report or blocker.

Do not ask the user to report “watcher started”, relay “Codex started”, or
perform any second confirmation. If the executor starts later, the queued
message remains ready and Codex keeps waiting. If either watcher exits, preserve
the queue and restart it with one resume prompt; do not introduce another
acknowledgement round trip. `auto` still does not broaden task authority.

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

Treat `coworker/runtime/` as local transport state and ignore it in Git. Its
archive and `TRANSCRIPT.md` are the default durable record for iterative
coordination. Add a tracked plan, report, or review only when the user, project
rules, or a genuine final milestone requires it.

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
  -TimeoutSeconds 180
```

The `wait` action returns JSON. On `message`, read `archive_path`; on `timeout`,
silently wait again inside the same long task. The three-minute bound is a
transport heartbeat, not an agent stopping condition. A timeout does not update
semantic task status.

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

While the executor is working, only wait. Do not inspect its branch, diff,
tests, logs, or half-written report. After receiving a completed executor
`report`:

1. Inspect the actual branch, diff, code, tests, artifacts, and provenance.
2. Write the review as a runtime mailbox body. Add a tracked review only when
   it is an explicit project deliverable.
3. Send it with type `approve`, `revise`, or `block`, tied to the exact reviewed
   tip.
4. On `revise`, return to waiting.
5. On `approve`, update status and end the long task.
6. On `block`, pause unless the review contains a bounded remediation.

Do not reduce review to mailbox contents. The report is a lead, not evidence.
Treat `note` as informational unless it explicitly requests action. Do not turn
an interim status note into an unsolicited review.

## Executor Loop

After receiving a task or review:

1. Read the referenced plan and review.
2. Work within the frozen scope and branch.
3. Commit coherent auditable units and verify.
4. Prepare the report as a runtime mailbox body. Update a tracked executor
   report only at a required deliverable milestone, and do so before checking
   and claiming a clean tip.
5. Send a `report` message containing the exact tip and an optional tracked
   report path.
6. Return to waiting. Never self-approve.

Do not send routine interim reports. Send a message before completion only when
blocked, when the frozen contract requires a decision, or when the user
intervenes.

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
- Do not create tracked files solely for mailbox transport, review receipts or
  approval receipts.
- Use three-minute bounded waits and silently repeat on timeout.
- Do not emit progress merely to prove the watcher is alive.
- Do not end the long task after any number of consecutive timeouts.
- If either long task exits, preserve runtime state for explicit recovery.

Before releasing a transport or lifecycle change, run the skill validator, the
mechanical test suite, and an end-to-end dry run in a temporary Git repository.
The dry run must cover one-step startup, queued-message consumption, the reply
path, automatic archival, and a clean Git worktree with runtime files ignored.

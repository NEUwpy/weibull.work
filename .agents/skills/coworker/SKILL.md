---
name: coworker
description: >
  Coordinate multi-agent coding work across Codex, Hermes/MiMo, OpenCode/DeepSeek,
  Claude Code, or similar agents. Use this skill for planning, requirement
  alignment, handoff, execution reports, secondary review, final approval, or a
  long-running duplex mailbox collaboration where agents exchange Markdown
  messages until approval or user takeover.
  Keep plans concise: clarify goals, boundaries, autonomy, stop conditions, and
  verification instead of writing step-by-step scripts for capable executors.
metadata:
  version: "2.1.4"
  updated_at: "2026-07-31T01:44:13+08:00"
---

# Coworker

Use this skill to run a small planner -> executor -> reviewer loop without turning the plan into a novel.

## Core Rules

1. **Align before planning.** If the user's goal, scope, or success criteria are unclear, ask until the blocking ambiguity is resolved. Do not silently invent missing requirements.
2. **Plan as a contract.** State goal, facts, boundaries, executor autonomy, stop conditions, verification, and report format. Do not prescribe implementation minutiae unless the user asks for an exact patch.
3. **Dispatch by reference.** Do not repeat project rules in every prompt. Send role + plan path + report path, and let the project entry docs and this skill carry the standing protocol.

## Default Roles

- **Planner / reviewer:** clarifies requirements, writes the contract, reviews diff and evidence, issues `APPROVE / REVISE / BLOCK`.
- **Executor:** chooses the implementation path inside the plan boundary, edits files, runs checks, reports evidence and deviations.
- **Secondary reviewer:** reviews without editing unless explicitly reassigned as executor.

Do not let multiple executors edit the same files in the same working tree at the same time. Use separate worktrees or disjoint file scopes for parallel work.

## Progressive Disclosure

Read only what the current task needs:

- `references/protocol.md`: role loop, plan shape, report/verdict formats, and anti-bloat rules.
- `references/dispatch.md`: short handoff prompts and CLI dispatch examples.
- `references/duplex-mailbox.md`: two long-running agents exchange visible
  Markdown messages through watched inboxes until approval, pause, or takeover.
- `references/incremental-review.md`: preserve first-pass and final-review
  rigor while reviewing later revisions from the last reviewed tip.
- `references/version-resolution.md`: resolve and synchronize global and
  project-local copies without silently using an older skill.

For tiny one-command tasks or pure factual answers, skip the coworker loop.

## Collaboration Modes

- **Manual:** the user carries prompts and reports between agents.
- **Duplex mailbox:** reviewer and executor remain active as separate long
  tasks, wait on separate inboxes, and communicate through archived Markdown
  messages. Use this when the user asks to watch the interaction, avoid manual
  relaying, or retain the ability to pause and take over.

In duplex mode, read `references/duplex-mailbox.md` completely before starting.
For iterative reviews, use `references/incremental-review.md`. When more than
one coworker copy exists, resolve it before acting.

A duplex session is one persistent logical task. Keep waiting after transport
timeouts; do not end the agent turn merely because no message arrived. Treat
only a completed report, a blocker, a control change, or a user intervention as
an event. Never inspect or review the executor's half-finished work while it is
still implementing.

Enter duplex auto mode only through the user-mediated startup handshake:
prepare the executor bootstrap prompt, tell the user that Codex is ready, and
keep the mailbox in `manual` until the user confirms the executor watcher has
started. Then switch to `auto` and begin the persistent reviewer wait.

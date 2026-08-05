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
  version: "2.5.0"
  updated_at: "2026-08-02T22:37:40+08:00"
---

# Coworker

Use this skill to run a small planner -> executor -> reviewer loop without turning the plan into a novel.

## Core Rules

1. **Align before planning.** If the user's goal, scope, or success criteria are unclear, ask until the blocking ambiguity is resolved. Do not silently invent missing requirements.
2. **Plan as a contract.** State goal, facts, boundaries, executor autonomy, stop conditions, verification, and report format. Do not prescribe implementation minutiae unless the user asks for an exact patch.
3. **Dispatch compactly.** Do not repeat project rules in every prompt. Send the role, goal, boundaries, and only the references that already exist. A tracked plan or report path is optional, not a prerequisite for collaboration.

## Research Mentor Checkpoints

For long-running research or evidence-driven work, use `$mentor` as an independent perspective at important transitions, not as a continuous supervisor. Invoke it when freezing the overall research plan, reviewing a direction-changing subtask plan, accepting a key subtask result, interpreting decisive evidence, moving to the next research stage, or when the user explicitly requests convergence or mentor review.

- Put required mentor checkpoints in the task contract or handoff. If several triggers describe the same transition, invoke `$mentor` once.
- Skip mentor review for routine implementation, mechanical reruns, and ordinary fixes that do not change the research direction or evidence conclusion.
- When the user requires a checkpoint, do not advance until `$mentor` says the work can continue or its minimum necessary correction is resolved.
- Let `$mentor` pause a transition without taking over the task. Do not build an automatic supervision system, scheduler, or control plane around it.

## Proportionality

- **Use minimum sufficient evidence.** Choose the lightest implementation that makes the result trustworthy, traceable, and rerunnable. Paper use, a “formal” experiment, or a long run does not by itself require production-grade authorization, control planes, attack tests, or a full pipeline. Stop hardening when the result is adequately supported.
- **Prefer the smallest implementation.** Reuse an existing capability when it fits. Otherwise, build the smallest script needed for the current goal. Consider a shared framework only when a second concrete consumer exists or the user explicitly requests one; do not build one-off infrastructure for hypothetical reuse.
- **Check review escalation.** Before adding a blocking finding, ask:
  1. Does it materially affect the research conclusion, result correctness, or basic reproducibility?
  2. Is it reasonably likely in the actual workflow, rather than a theoretical extreme or adversarial scenario?
  3. Are existing tests, manual checks, or run records already sufficient?
  4. Is this fixing a real defect, or merely layering more strictness because the workflow is already strict?

  If the first three questions do not clearly justify blocking, record the item as a recommendation instead.
- **Keep coordination subordinate.** Mailbox messages and their automatic
  archive are the default record for iterative coordination. Do not create or
  commit repository files merely to carry a prompt, receipt, revision closure,
  or approval.
- **Validate the tool before use.** A change to startup, transport, waiting,
  reporting, or approval behavior is not ready for normal work until the skill
  validator, mechanical tests, and a temporary-repository end-to-end duplex
  check all pass. Do not make the research task serve as the coworker test bed.

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

Start duplex mode with one user relay only. Queue the task, set the mailbox to
`auto`, present the executor bootstrap prompt, and immediately begin the
persistent reviewer wait in the same long task. The user pastes that prompt
once; the executor starts waiting and consumes the queued task immediately.
Never require “watcher started”, “Codex started”, or another acknowledgement
round trip.

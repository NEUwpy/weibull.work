---
name: coworker
description: >
  Coordinate multi-agent coding work across Codex, Hermes/MiMo, OpenCode/DeepSeek,
  Claude Code, or similar agents. Use this skill for planning, requirement
  alignment, handoff, execution reports, secondary review, or final approval.
  Keep plans concise: clarify goals, boundaries, autonomy, stop conditions, and
  verification instead of writing step-by-step scripts for capable executors.
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

For tiny one-command tasks or pure factual answers, skip the coworker loop.

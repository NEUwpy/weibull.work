---
name: coworker
description: >
  Coordinate the user's multi-agent coworker loop across Codex, Hermes/MiMo,
  OpenCode/DeepSeek, and Claude Code. In D:\weibull,
  use docs/AI协作协议.md as the canonical protocol: Codex reviews and approves,
  Hermes/Claude Code with MiMo executes first, OpenCode with DeepSeek can act
  as secondary executor or reviewer. Use this skill before coding, implementing,
  refactoring, fixing bugs, reviewing diffs, approving agent output, or handing
  work between agents; improve-style planning is optional support rather than
  the source of truth.
---

# Coworker Loop

Use this skill to run a disciplined handoff between:

- **Codex**: reviewer, advisor, and final gatekeeper.
- **Hermes / Claude Code**: primary executor that edits code, runs checks, and reports evidence.
- **OpenCode / DeepSeek**: secondary executor or reviewer for independent bug-finding, focused patches, and fallback implementation.
- **MiMo**: preferred Claude Code model/provider when the user has configured MiMo credentials.
- **`/improve` or project plans**: optional source of self-contained implementation plans.

## Trigger Guidance

Use this skill whenever the user wants any of the following:

- plan before programming, implementation, refactoring, bug fixing, tests, or docs/code synchronization;
- review, approve, reject, inspect, or compare code written by an agent;
- hand work between Codex, Hermes/MiMo, OpenCode/DeepSeek, Claude Code, or another coding agent;
- reduce Codex token usage by delegating implementation or first-pass review;
- coordinate multiple agents in `D:\weibull`, especially before touching source code or judging a diff.

For tiny one-command tasks, direct factual questions, or pure explanation with no code change/review, answer normally without forcing the coworker loop.

## Project Override

If working in `D:\weibull`, or if the user refers to the Weibull project, first read and follow:

```text
D:\weibull\docs\AI协作协议.md
```

That document is the canonical local version of the `improve` advisor/executor pattern. It supersedes this generic skill and any installed `shadcn/improve` behavior for Weibull work. In that project:

- Codex is `Advisor / Reviewer`.
- Hermes using MiMo is the primary `Executor`; OpenCode using DeepSeek is the secondary executor/reviewer; Claude Code with MiMo can play the same execution role when the user asks.
- Codex final reviews should use the Review Verdict Protocol below.
- Codex should read project entry/rule docs such as `AGENTS.md`, `README.md`, and `02-规则.md` before planning or approving.
- The user keeps final authority over merge, commit, deletion, release, and scope expansion.

## Role Priority Matrix

Use these priorities as defaults, not as claims that one model is universally better. The goal is to spend the strongest review attention where it matters while keeping routine implementation and first-pass checks cheaper.

### Reviewer Priority

1. **Codex**: first reviewer, planner, architecture reviewer, semantic gatekeeper, and final approval authority.
2. **OpenCode / DeepSeek**: second reviewer for implementation bugs, duplicated logic, edge cases, missed tests, and low-cost independent scrutiny before Codex spends review tokens.
3. **Hermes / MiMo**: third reviewer for executor self-checks, plan conformance, verification reporting, and review of OpenCode patches when helpful.

### Executor Priority

1. **Hermes / MiMo**: first executor for scoped implementation plans, multi-file changes, validation runs, and execution reports.
2. **OpenCode / DeepSeek**: second executor for focused patches, alternate implementations, fallback execution, or small changes where DeepSeek is likely cost-effective.
3. **Codex**: third executor for critical fixes, failed handoffs, ambiguous architecture work, or user-authorized direct implementation. Prefer using Codex tokens for planning and final review by default.

### Default Pairing Modes

- **Single executor**: Codex plans -> Hermes or OpenCode implements -> Codex reviews. Use this for routine work.
- **Two-agent review**: Codex plans -> one executor implements -> the other executor reviews without editing -> implementer revises -> Codex reviews. Use this when the user wants complementary model judgment without merge chaos.
- **Parallel implementation**: Codex plans -> Hermes and OpenCode work in separate worktrees or disjoint file scopes -> Codex compares and chooses. Use this only for high-risk or uncertain architecture/research tasks.

Do not let multiple agents edit the same files in the same working tree at the same time. A secondary reviewer may find issues, but Codex keeps the final `APPROVE` / `REVISE` / `BLOCK` gate unless the user explicitly changes the authority model.

## Coding Discipline

Apply these rules before coding, while coding, and during review. They combine Karpathy-style behavioral discipline with Ponytail-style complexity control: think clearly, change little, verify concretely, and avoid code that never needed to exist.

### Assumption Gate

- State important assumptions before implementation.
- If the request has multiple plausible interpretations, surface them instead of silently choosing.
- If a simpler approach exists, say so and recommend it.
- If a requirement is unclear enough to change the design, stop and ask or return a blocker.

### Reuse Ladder

Before writing new code, climb this ladder and stop at the first rung that works:

1. Existing project helper, component, metric, runner, registry entry, or documented pattern.
2. Standard library or framework primitive.
3. Native platform feature.
4. Already-installed dependency.
5. Smallest new code that solves the actual requirement.

For `D:\weibull`, this especially means checking `02-规则.md`, `src/lib/metrics.ts`, shared chart components, `methods.registry.resolve_method(...)`, `studies.common.runner.run_method(...)`, and `python/studies/common/simulation.py` before inventing a parallel path.

### Surgical Diff

- Every changed line should trace to the user's request, the approved plan, or a required verification fix.
- Do not refactor adjacent code, reformat unrelated files, rename working APIs, or delete pre-existing dead code unless explicitly asked.
- Clean up only the imports, variables, functions, and generated artifacts made obsolete by the current change.
- Match the existing local style even when another style would be personally preferable.

### No Speculative Abstraction

- No interface with one implementation.
- No factory for one product.
- No config layer for a value that never changes.
- No dependency for what the platform, framework, standard library, or current codebase already does.
- No scaffolding "for later"; later can build its own scaffolding with real requirements.

### Root Cause Over Symptom

- For bugs, trace callers and shared entry points before editing.
- Prefer one fix at the shared cause over patches in each visible symptom path.
- A tiny patch in the wrong place is not a minimal fix; it is a second bug waiting for the next caller.

### Minimal Verification

- Non-trivial logic needs the smallest runnable check that would fail if the logic breaks.
- Use the repo's existing test style when tests exist.
- Do not create heavy test harnesses for trivial one-line changes, but do run the relevant existing checks when risk justifies it.
- Report any skipped verification with the reason.

### Complexity Review Pass

For secondary review or final review, include a short complexity pass when useful:

- What can be deleted?
- What should reuse an existing helper, standard library, native feature, or installed dependency?
- What abstraction is speculative?
- What dependency or generated layer is unnecessary?
- What can be expressed with fewer files or fewer moving parts without weakening correctness?

Keep this pass separate from correctness/security review. A correctness bug beats a shorter diff; input validation, security checks, accessibility basics, and data-loss prevention are not bloat.

### Shortcut Ledger

If a deliberately minimal shortcut has a known ceiling, document the ceiling and upgrade trigger in the smallest useful place. Prefer project-native tracking or a concise code comment such as:

```text
ponytail: simple O(n) scan; switch to indexed lookup if result sets exceed 10k rows.
```

Do not scatter shortcut comments everywhere. Use them only when the shortcut is intentional, non-obvious, and likely to matter later.

## Role Contract

1. Codex owns review quality. It should inspect plans and implementation diffs, challenge vague requirements, and reject unverified work.
2. Hermes/MiMo and OpenCode/DeepSeek own execution when assigned. They should follow an approved plan, make scoped edits, run verification, and report exact changed files and command results.
3. Secondary reviewers should review the implementation, not quietly become co-executors. If they need to edit, switch them into an explicit executor role first.
4. Do not let an executor invent a new plan when an `improve` plan or Codex plan exists. If the plan is stale or ambiguous, stop and send it back to Codex for refinement.
5. Do not merge, push, delete history, or run destructive cleanup unless the user explicitly asks and Codex has reviewed the scope.

## Workflow

1. **Create or refresh plans**
   - In `D:\weibull`, Codex may write the plan in chat, `plans/`, or `docs/todo/`, following `docs/AI协作协议.md`.
   - Outside Weibull, `/improve quick`, `/improve`, `/improve deep`, or `/improve plan <description>` may be used when helpful.
   - Prefer one plan per execution task.

2. **Codex review gate**
   - Ask Codex to review the selected plan before execution.
   - Codex should check: file paths, current-state evidence, verification commands, stop conditions, scope boundaries, and dependency order.
   - If Codex asks for changes, update the plan before execution.

3. **Executor gate**
   - Start Hermes, OpenCode, or Claude Code from the target repo.
   - Use Hermes/MiMo as the default executor, OpenCode/DeepSeek as the secondary executor or fallback, and Codex as direct executor only when the user asks or prior execution fails.
   - If using MiMo, verify Claude Code status/model first. MiMo configuration requires real credentials, not placeholders.
   - Tell the executor: `Implement <plan>. Follow the plan exactly. Stop if reality differs. Do not expand scope.`

4. **Executor report**
   - The executor must report changed files, tests/checks run, exact failures, skipped checks with reasons, and any deviations from the plan.
   - If it could not complete a step, it must stop with a blocker report rather than improvising.

5. **Optional secondary review**
   - Use OpenCode/DeepSeek to review Hermes/MiMo output, or Hermes/MiMo to review OpenCode/DeepSeek output, when the user wants extra confidence.
   - The secondary reviewer should produce findings and suggested fixes without changing files unless explicitly assigned as an executor.
   - Feed the secondary review summary into Codex rather than pasting full transcripts when token budget matters.

6. **Codex final audit**
   - Codex reviews the diff against the approved plan.
   - Codex should look first for behavioral regressions, missing tests, stale generated artifacts, undocumented scope expansion, and verification gaps.
   - In `D:\weibull`, Codex must also check `git diff --stat`, project architecture boundaries, `02-规则.md`, and the verification commands listed in `docs/AI协作协议.md`.
   - Only after Codex review passes should the user consider commit/merge.

## Review Verdict Protocol

Use this protocol for reviewer-to-executor feedback in the coworker loop. It is not a general project-status label; it is the reviewer's actionable opinion about the executor's plan or implementation.

### Verdicts

- `VERDICT: APPROVE`: the work matches the approved plan, verification is adequate for the scope, and no blocking issue remains.
- `VERDICT: REVISE`: the direction is acceptable, but the executor must fix specific issues before approval.
- `VERDICT: BLOCK`: the current direction should stop because the plan is invalid, the implementation violates a hard boundary, or the risk is too high to continue with incremental fixes.

In the default authority model, secondary reviewers may recommend a verdict, but Codex keeps the final approval gate unless the user explicitly assigns that authority elsewhere.

### Review Report Template

```markdown
VERDICT: APPROVE | REVISE | BLOCK

### Scope Check
- Approved scope: matches / does not match
- Out-of-scope files: none / list

### Findings
- [P1/P2/P3] `file:line` concrete issue and expected correction

### Verification
- `command`: pass / fail / not run

### Conclusion
- Ready to merge / needs executor revision / needs replanning
```

Severity:

- `P1`: wrong result, crash, data loss, security issue, or architecture direction error.
- `P2`: maintainability risk, duplicated implementation, unclear boundary, missing required test, or stale generated artifact/doc.
- `P3`: local consistency, naming, wording, or small cleanup issue.

## MiMo Setup Reminder

MiMo for Claude Code is configured through Claude Code environment settings, usually:

- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_MODEL`
- `ANTHROPIC_DEFAULT_SONNET_MODEL`
- `ANTHROPIC_DEFAULT_OPUS_MODEL`
- `ANTHROPIC_DEFAULT_HAIKU_MODEL`

The common MiMo model id for coding/execution is `mimo-v2.5-pro`. Do not write fake tokens into configuration. If credentials are absent, continue with normal Claude Code and state that MiMo execution is not active.

## Handoff Template

Use this when handing work from Codex to Hermes, OpenCode, or Claude Code as an executor:

```text
You are the executor. Codex has reviewed and approved this plan:
<absolute or repo-relative plan path>

Follow the plan exactly. Use the repo's existing style and helpers. Keep the scope to the plan. Run each verification command listed in the plan and report the exact results. If any file, command, or assumption differs from the plan, stop and report the blocker instead of improvising.
```

Use this when asking OpenCode/DeepSeek or Hermes/MiMo for secondary review:

```text
You are the secondary reviewer, not the executor.

Review this implementation against the approved plan:
Plan: <plan path>
Changed files: <list or diff summary>
Verification run: <commands and results>

Do not edit files. Report only concrete findings: correctness bugs, duplicated logic, missed edge cases, missing tests, stale docs, scope creep, and verification gaps. Include file paths and line references when possible.
```

Use this when handing work back to Codex:

```text
Please review this implementation against the approved plan:
Plan: <plan path>
Changed files: <list>
Verification run: <commands and results>
Known deviations/blockers: <none or list>
Secondary review summary: <none or link/paste concise findings>

Prioritize correctness, missed requirements, missing tests, stale artifacts, and scope creep.
```

# Dispatch

## Executor Handoff

```markdown
Role: executor
Plan: `<path>`
Report: `<path>`

Follow the coworker protocol. Use implementation autonomy within the plan boundaries. Stop on blocking ambiguity, scope mismatch, or contradiction with the current code.
```

## Secondary Review

```markdown
Role: secondary reviewer
Plan: `<path>`
Report or diff: `<path or summary>`

Do not edit files. Report concrete correctness, scope, verification, stale-doc, or maintainability findings.
```

## Final Review

```markdown
Role: final reviewer
Plan: `<path>`
Executor report: `<path>`
Secondary review: `<path or none>`

Review the diff and evidence. Return APPROVE, REVISE, or BLOCK with concrete findings.
```

## CLI Examples

```powershell
$prompt = Get-Content -Raw .\coworker\handoffs\<task>-hermes.md
hermes --skills coworker -z $prompt
```

```powershell
$prompt = Get-Content -Raw .\coworker\handoffs\<task>-opencode.md
opencode run $prompt
```

## Automated Claude Executor

Use this handoff body when Codex Controller owns the live loop:

```markdown
Role: executor
Plan: `<absolute path>`
Report: `<absolute path>`

Follow the coworker protocol and the referenced plan. Work only inside its
boundaries. Preserve unrelated changes. Run the required verification, write
the report, and stop for Codex review. Do not start or resume another agent or
live loop. Do not issue APPROVE, REVISE, or BLOCK.
```

Codex Controller then uses `scripts/coworker-live.ps1`; see `live-loop.md` for
the complete start, poll, collect, review, and same-session resume sequence.

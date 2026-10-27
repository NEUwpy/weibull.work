# Dispatch

## Executor Handoff

```markdown
Role: executor
Plan: `<path>`
Report: `<optional path; otherwise use the archived mailbox message>`
Mentor checkpoints: `<required research transitions, or none>`

Follow the coworker protocol. Use implementation autonomy within the plan boundaries. Stop on blocking ambiguity, scope mismatch, contradiction with the current code, or a required `$mentor` checkpoint. Do not invoke the mentor for routine implementation steps or turn it into continuous supervision.
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
Executor report: `<path or archived mailbox message>`
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

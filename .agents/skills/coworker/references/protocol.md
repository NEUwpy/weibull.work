# Coworker Protocol

## Alignment Gate

Before writing a plan, confirm the user's actual goal, scope, and success criteria. If a missing detail would change the design, ask. If it is non-blocking, record it as an assumption or open question.

## Plan Shape

Use this shape by default:

```markdown
# Task Plan

Goal:

Known facts:

Boundaries:
- Allowed:
- Not allowed:

Executor autonomy:
- Choose the smallest implementation path that fits existing project patterns.

Stop conditions:

Verification:

Report:
```

Plans are contracts, not scripts. Prefer checkpoints, boundaries, and validation over imagined future steps. Treat executor agents as competent.

## Reports

Executor reports should include:

- changed files
- checks run and exact results
- skipped checks with reasons
- blockers
- deviations from the plan

## Verdicts

Use:

- `APPROVE`: scope matches, evidence is adequate, no blocking issue remains.
- `REVISE`: direction is acceptable, but concrete fixes are needed.
- `BLOCK`: the plan or implementation violates a hard boundary or needs replanning.

Keep review findings concrete and file-specific.

## Iterative Reviews

Use stable finding IDs. The first review is complete; later REVISE rounds
normally inspect only the last-reviewed-tip to current-tip diff plus targeted
regressions. Before APPROVE, run a final integrity pass. Read
`incremental-review.md` for reset triggers that require returning to a full
review.

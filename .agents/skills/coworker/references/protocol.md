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

Mentor checkpoints:
- Required at: `<research transitions only, or none>`

Verification:

Report:
```

Plans are contracts, not scripts. Prefer checkpoints, boundaries, and validation over imagined future steps. Treat executor agents as competent.

For long-running research or evidence-driven work, name only the transitions where `$mentor` is required. Suitable checkpoints include freezing the overall research plan, accepting a direction-changing subtask, interpreting decisive evidence, and entering the next research stage. Merge overlapping triggers into one review and omit routine implementation steps. A required checkpoint pauses progression until the mentor allows continuation or the minimum necessary correction is resolved; it does not transfer ownership of the task to the mentor.

## Reports

The archived mailbox message is the default report for iterative work. A
tracked report file is optional and should be created only when the user,
project rules, or a genuine deliverable milestone requires one. Do not create
a repository file solely to prove that a revision or approval occurred.

Reports should include:

- changed files
- checks run and exact results
- skipped checks with reasons
- blockers
- deviations from the plan

When a clean Git tip is part of the contract, finish every required tracked
write before checking cleanliness and requesting review. Send subsequent
receipts from `coworker/runtime/`; do not make the worktree dirty after claiming
it is clean.

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

The first review should surface the main blocking issues together whenever
practical. Later reviews should primarily verify the requested fixes and check
for regressions. Do not raise the acceptance standard unless a revision
introduced a new defect or a newly discovered issue would directly invalidate
the result. Separate blocking findings from recommendations; recommendations
do not prevent `APPROVE`.

An approval is valid as an archived mailbox verdict tied to an exact reviewed
tip. Do not create an administrative approval commit when doing so would merely
move an authorization parent or trigger another clean-tree/report cycle.

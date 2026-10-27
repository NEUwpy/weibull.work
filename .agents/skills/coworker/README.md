# Coworker

`coworker` is an Agent Skill for coordinating planner, executor, and reviewer
work across Codex, Hermes, OpenCode, Claude Code, and similar coding agents.

The skill supports compact handoffs, evidence-based review, incremental review,
and a duplex Markdown mailbox for long-running collaboration.

## Contents

- `SKILL.md` — skill entry point
- `VERSION.json` — canonical version metadata
- `references/` — protocols and operating guidance
- `scripts/` — PowerShell helpers
- `templates/` — review-state template
- `tests/` — mechanical regression tests

## Install

Clone the repository, then expose the repository directory from an Agent
Skills-compatible location. On Windows, a directory junction avoids duplicate
copies:

```powershell
git clone https://github.com/NEUwpy/coworker.git "$env:USERPROFILE\ai-skills\coworker"
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.agents\skills\coworker" `
  -Target "$env:USERPROFILE\ai-skills\coworker"
```

Back up or remove an existing destination only after comparing it with the
cloned version. Do not overwrite a divergent local copy blindly.

Codex and OpenCode discover `~/.agents/skills`. Claude Code can use a junction
under `~/.claude/skills`. Hermes can add the clone through
`skills.external_dirs`.

## Verify

```powershell
python -m pytest tests/test_coworker_v2.py -q
```

Functional changes must update both `SKILL.md` and `VERSION.json` with the same
semantic version and timestamp.

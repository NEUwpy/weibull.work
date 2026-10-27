# Coworker Version Resolution

Global and project-local copies may coexist so a repository remains portable
across computers. Never assume path precedence means version precedence.

## Selection

Before using coworker when duplicate copies exist:

1. Read `VERSION.json` from each copy.
2. Prefer the greater semantic `version`.
3. If versions match, prefer the later `updated_at`.
4. If both match but directory contents differ, stop with `VERSION_CONFLICT`;
   do not silently choose by path.
5. A copy without `VERSION.json` is legacy version `0.0.0`.

Record the selected path, version, and timestamp in the task's first status
entry.

Use the deterministic resolver:

```powershell
$resolver = 'C:\Users\36089\.agents\skills\coworker\scripts\resolve-coworker-skill.ps1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $resolver `
  -ProjectPath <repo>\.agents\skills\coworker
```

It is read-only and returns the selected copy or `VERSION_CONFLICT`.

## Synchronization

After selecting the newer copy:

1. Compare relative file lists and SHA256 values.
2. Preserve a recoverable backup or rely on a clean Git version for a tracked
   project copy.
3. Mirror the complete newer skill into the older location.
4. Recompute the comparison; file lists and hashes must match exactly.
5. Run the skill's mechanical tests.
6. For runtime-affecting changes, restart OpenCode before relying on the new
   version.

The resolver is deliberately read-only; synchronization is a separate reviewed
operation. The older controller-driven live-loop was removed from the active
2.1 series after its regression suite and the duplex transport suite passed.
It remains recoverable from repository history until a real duplex pilot is
approved.

Do not synchronize into a project worktree while another agent is modifying
that worktree. Wait for a clean, stable handoff first.

## Update Discipline

Every functional skill change must:

- increment semantic `version`;
- update `updated_at` in both `SKILL.md` and `VERSION.json`;
- keep the two values identical;
- update or add a mechanical test when behavior changes.

Documentation-only wording fixes increment the patch version. New compatible
behavior increments the minor version. Breaking mailbox or message-contract
changes increment the major version.

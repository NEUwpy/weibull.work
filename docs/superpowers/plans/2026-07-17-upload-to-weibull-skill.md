# Upload to Weibull Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and install one safe `upload-to-weibull` skill shared by Codex, Claude Code, OpenCode, and Hermes.

**Architecture:** Keep one canonical skill under `C:\Users\36089\.agents\skills\upload-to-weibull`. A testable PowerShell core performs ID parsing, source discovery, preflight comparison, and copy-only execution; a fixed-path wrapper prevents production callers from supplying arbitrary roots. The skill document directs agents through the semantic publication pass after the deterministic copy succeeds.

**Tech Stack:** Agent Skills `SKILL.md`, PowerShell 7/Windows PowerShell-compatible scripts, SHA-256 file comparison, Windows directory junctions, Git and the existing Weibull content checks.

---

## File map

- Create `C:\Users\36089\.agents\skills\upload-to-weibull\SKILL.md`: trigger conditions, safe workflow, semantic formatting, and completion gates.
- Create `C:\Users\36089\.agents\skills\upload-to-weibull\scripts\UploadToWeibull.Core.psm1`: pure/testable planning and copy functions.
- Create `C:\Users\36089\.agents\skills\upload-to-weibull\scripts\upload-to-weibull.ps1`: production entry point with fixed source and target roots.
- Create `C:\Users\36089\.agents\skills\upload-to-weibull\tests\upload-to-weibull.tests.ps1`: dependency-free temporary-directory test harness.
- Create junctions in Claude, OpenCode, and Hermes skill roots; Codex discovers the canonical `.agents\skills` directory directly.
- Modify `docs/superpowers/plans/2026-07-17-upload-to-weibull-skill.md`: check off completed steps and record exact verification evidence.

### Task 1: Establish the RED baseline

**Files:**
- Create: `C:\Users\36089\.agents\skills\upload-to-weibull\tests\upload-to-weibull.tests.ps1`
- Test target (initially absent): `C:\Users\36089\.agents\skills\upload-to-weibull\scripts\UploadToWeibull.Core.psm1`

- [ ] **Step 1: Record the agent-without-skill baseline**

Run one read-only pressure scenario asking an agent how it would upload `182-101` through `182-107`. Record whether it uses `-Force`, skips dry-run, assumes one source, edits before conflict checks, or lacks per-ID status.

- [ ] **Step 2: Write a dependency-free failing test harness**

The harness imports the absent core module and defines assertions for these behaviors:

```powershell
$module = Join-Path $PSScriptRoot '..\scripts\UploadToWeibull.Core.psm1'
Import-Module $module -Force

Assert-Equal @('182-101','182-102','182-103') `
  (Resolve-UploadIds -InputId @('182-101到182-103')) `
  'expands a same-prefix inclusive range'

Assert-Throws { Resolve-UploadIds -InputId @('182-103到182-101') } `
  'rejects a reverse range'
Assert-Throws { Resolve-UploadIds -InputId @('182-101到183-102') } `
  'rejects a cross-prefix range'
```

Temporary fixtures must additionally assert: dry-run writes nothing; apply copies original/translation/images; optional translation/images are reported missing but do not fail; identical targets skip; different targets conflict without overwrite; duplicate original matches fail; `_archive` matches are ignored; the source manifest is unchanged before and after apply.

- [ ] **Step 3: Run the test and verify RED**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\36089\.agents\skills\upload-to-weibull\tests\upload-to-weibull.tests.ps1
```

Expected: FAIL because `UploadToWeibull.Core.psm1` does not exist. The failure must be an import/module-not-found failure, not a fixture syntax error.

### Task 2: Implement deterministic planning and copy behavior

**Files:**
- Create: `C:\Users\36089\.agents\skills\upload-to-weibull\scripts\UploadToWeibull.Core.psm1`
- Test: `C:\Users\36089\.agents\skills\upload-to-weibull\tests\upload-to-weibull.tests.ps1`

- [ ] **Step 1: Implement strict ID expansion**

Export this interface:

```powershell
function Resolve-UploadIds {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string[]]$InputId)
    # Accept NNN-NNN, comma-separated values, and same-prefix inclusive ranges
    # written with 到, ~, or an ASCII hyphen surrounded by whitespace.
}
```

Normalize duplicates while preserving first-seen order. Reject malformed IDs, reverse ranges, and ranges whose three-digit prefix differs.

- [ ] **Step 2: Implement source discovery and artifact planning**

Export this interface:

```powershell
function New-UploadPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string[]]$Id,
        [Parameter(Mandatory)][string[]]$SourceRoot,
        [Parameter(Mandatory)][string]$TargetRoot
    )
}
```

For each ID, recursively locate exactly one `{ID}-pdf原文.md`, excluding every path segment named `_archive`. Set `failed` for zero or multiple matches. From that source directory, plan the required original and optional translation/image artifacts. Resolve every path with `[IO.Path]::GetFullPath()` and verify it remains beneath its declared source or target root.

- [ ] **Step 3: Implement SHA-256 comparison**

Use `Get-FileHash -Algorithm SHA256` for files. For directories, build a sorted manifest of relative path, length, and SHA-256 for every file. Return `missing`, `identical`, or `different` before any copy occurs.

- [ ] **Step 4: Implement per-ID preflight and copy**

Export this interface:

```powershell
function Invoke-UploadPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object[]]$Plan,
        [switch]$Apply
    )
}
```

For each ID, inspect all artifacts first. If any target is `different`, mark the ID `conflict` and copy none of its artifacts. Without `-Apply`, report `planned` and write nothing. With `-Apply`, copy only missing targets using `Copy-Item` without `-Force`; report all-identical IDs as `skipped` and successful writes as `copied`. Preserve explicit optional-artifact notes and return one result object per ID.

- [ ] **Step 5: Run the test and verify GREEN**

Run the Task 1 command. Expected: all named cases print `PASS` and the process exits `0`; temporary fixture directories are removed in `finally`.

### Task 3: Add the fixed production wrapper

**Files:**
- Create: `C:\Users\36089\.agents\skills\upload-to-weibull\scripts\upload-to-weibull.ps1`
- Modify: `C:\Users\36089\.agents\skills\upload-to-weibull\tests\upload-to-weibull.tests.ps1`

- [ ] **Step 1: Add a failing wrapper contract test**

Assert that the wrapper exists, exposes only `InputId` and `Apply`, contains the two approved source roots and `D:\weibull`, and has no caller-supplied `SourceRoot` or `TargetRoot` parameter.

- [ ] **Step 2: Run the test and verify RED**

Expected: FAIL with `production wrapper is missing`.

- [ ] **Step 3: Implement the wrapper**

Use this public interface and fixed roots:

```powershell
[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)][Alias('Id')][string[]]$InputId,
    [switch]$Apply
)

$sourceRoots = @(
    'D:\博士阶段\100科研文献管理',
    'D:\博士阶段\400知识管理'
)
$targetRoot = 'D:\weibull'
```

Import the core, resolve IDs, build the plan, invoke it, print a table containing `Id`, `Status`, and `Message`, and exit `2` after reporting all IDs if any result is `failed` or `conflict`.

- [ ] **Step 4: Run the test and verify GREEN**

Expected: all tests pass; invoking the wrapper without `-Apply` for `182-101` produces `planned` and does not change `D:\weibull`.

### Task 4: Write and pressure-test the skill instructions

**Files:**
- Create: `C:\Users\36089\.agents\skills\upload-to-weibull\SKILL.md`
- Test: `C:\Users\36089\.agents\skills\upload-to-weibull\tests\upload-to-weibull.tests.ps1`

- [ ] **Step 1: Write the minimal discoverable skill**

Use this frontmatter:

```yaml
---
name: upload-to-weibull
description: Use when uploading, copying, importing, or publishing numbered OCR literature from the doctoral 100 or 400 libraries into the Weibull electronic library, including requests such as 上传文献, 上传ID, or upload papers to Weibull.
---
```

The body must require: read repository `README.md` and `src/content/README.md`; run preview first; stop on conflict; run apply only after preview; never move/delete/overwrite sources; use the current content guide for YAML and images; use semantic review rather than bulk regex for references; report per-ID status; do not edit `05-状态.md`, algorithms, method eligibility, or generated caches; do not commit/push unless separately requested.

- [ ] **Step 2: Add exact usage examples**

```powershell
& 'C:\Users\36089\.agents\skills\upload-to-weibull\scripts\upload-to-weibull.ps1' -InputId '182-101到182-107'
& 'C:\Users\36089\.agents\skills\upload-to-weibull\scripts\upload-to-weibull.ps1' -InputId '182-101到182-107' -Apply
```

Document the post-copy semantic checklist: frontmatter, root-relative image links, actual image existence, figure captions, final `## 参考文献`/`## References`, numbered entries, `git diff --check`, and the smallest relevant site test.

- [ ] **Step 3: Re-run the baseline scenario with the skill available**

Success means the agent previews before applying, refuses `-Force`, treats metadata/reference editing as a reviewed second phase, and keeps method status out of scope. If it finds a loophole, tighten `SKILL.md` and repeat once.

### Task 5: Install one authority for four agents

**Files:**
- Authority: `C:\Users\36089\.agents\skills\upload-to-weibull`
- Create junction: `C:\Users\36089\.claude\skills\upload-to-weibull`
- Create junction: `C:\Users\36089\.config\opencode\skills\upload-to-weibull`
- Create junction: `C:\Users\36089\AppData\Local\hermes\skills\upload-to-weibull`

- [ ] **Step 1: Preflight every destination**

Resolve each absolute destination. If a destination already exists and is not a junction to the authority, stop and report it; do not remove or replace it.

- [ ] **Step 2: Create missing junctions**

Use native PowerShell junction creation:

```powershell
New-Item -ItemType Junction -Path $destination -Target $authority
```

- [ ] **Step 3: Verify discovery**

Check each junction target with `Get-Item`. Run `hermes skills list` and require an enabled `upload-to-weibull` row. Confirm Codex's enumerated shared skill root contains the authority and both Claude/OpenCode entry paths resolve to it.

### Task 6: Final verification and handoff

**Files:**
- Verify all files above; do not upload real papers in this task.

- [ ] **Step 1: Run the complete temporary-directory suite**

Expected: exit `0`, no residual test directory, and every case passes.

- [ ] **Step 2: Run a real read-only preview**

Preview `182-101到182-107` with no `-Apply`. Expected: seven per-ID results and no changes under `D:\weibull\src\content` or `D:\weibull\public`.

- [ ] **Step 3: Verify repository cleanliness boundaries**

Run `git status --short --branch` and `git diff --check`. Expected: only the implementation-plan tracking update is present in the repository; no paper, algorithm, status-source, cache, or credential file is changed.

- [ ] **Step 4: Report installation paths and first command**

Report the authority, three junction paths, test results, Hermes discovery status, real preview result, and the exact command the user can authorize later to apply `182-101到182-107`.

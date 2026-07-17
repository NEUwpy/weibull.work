# Stage A Codex Interim Review

VERDICT: REVISE

## Scope Check

- Approved scope: matches.
- Commits reviewed: `f8b6761`, `d7e3ac7`.
- Out-of-scope committed files: none.
- Existing `Study/01` drafts and `docs/history/260717.md`: remain outside the two executor commits.
- Stage B authorization: denied until the findings below are fixed and re-reviewed.

## Confirmed Results

- `npm run test:method-status`: 14/14 pass.
- `npm run check:method-status`: cache is up to date, 22 methods.
- `git diff --check 8350f29..d7e3ac7`: pass.
- Current `05-状态.md` names and families match all 22 catalog leaves.
- Fixed-sample backend smoke agrees with the report: MLE, MMLE, WMLE, MDM and LRE return estimates; MPS, LSE, MM, PWM, Grey and Bayesian return `NotImplementedError` failures.
- Current derived result agrees with the report: only MDM is calculator-enabled; MLE/MMLE/WMLE/LRE are first-layer in progress; the remaining 17 are not started.
- The three `PAPER_NEEDED` items are correctly blocked and do not overclaim completion.

## Findings

### [P2] Repository-relative evidence paths can escape the repository

File: `scripts/lib/method-status.mjs:212`

The validator rejects absolute paths but joins relative paths without checking that the resolved target remains under the repository root. A completed evidence item set to `evidence: ['..']` passes `checkEvidencePaths` because the parent directory exists. This violates the repository-relative evidence contract and weakens provenance fail-closed behavior.

Required correction:

- resolve the repository root and candidate path;
- reject a candidate when `path.relative(root, candidate)` is `..`, begins with `..${path.sep}`, or is absolute;
- include `classification_source` in repository-path validation;
- add a unit test proving `..` and `../outside` are rejected.

### [P2] Catalog duplication and status metadata drift are not rejected

Files: `scripts/lib/method-status.mjs:358`, `scripts/generate-method-status.mjs:19`

`flattenLeafIds()` does not reject duplicate leaf IDs, and validation only receives an ID array. A catalog containing `['mdm', 'mdm']` is accepted and generates two MDM entries. Separately, changing the status document's MDM name/family to unrelated values is accepted because neither is checked against `src/data/methods.json`.

Required correction:

- reject duplicate category and leaf IDs while flattening the catalog;
- compare each status entry's `name` and `family` with its catalog leaf and parent category, or derive those display fields from the catalog rather than duplicating them;
- add tests for duplicate catalog IDs, name mismatch and family mismatch.

## Reproduction Evidence

The following read-only probes were run against the submitted implementation:

```text
path_escape: ACCEPTED
name_family_drift: ACCEPTED
duplicate_catalog_ids: ACCEPTED generated=mdm,mdm
```

These probes do not invalidate the current YAML values, but they invalidate the claimed strict/fail-closed validator boundary.

## Required Reverification

After correction, rerun and report:

```powershell
npm run test:method-status
npm run check:method-status
git diff --check
```

The method-status suite must include the four new boundary cases: repository escape, duplicate catalog ID, name mismatch and family mismatch.

## Report Handling

Do not finalize or commit the current executor report as the approved Stage A record yet. After the revision:

1. add a revision section with the correction commit and fresh verification results;
2. keep the original execution evidence rather than rewriting history;
3. commit the updated report with the correction evidence;
4. return it to Codex for a fresh Stage A verdict.

## Conclusion

The implementation direction and current migrated data are acceptable, but the validation boundary still permits concrete provenance and catalog-consistency bypasses. Fix these focused issues before Stage B.

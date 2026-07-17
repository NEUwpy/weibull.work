# Stage B Codex Review

VERDICT: REVISE

## Scope Check

- Review baseline: `564ec8b`.
- Executor commits: `4b26cc2`, `af4e703`, `da8f39c`.
- Executor report: `b0817d5`.
- The committed file set matches Stage B Tasks 4–6 plus the report.
- `Study/01` working-tree edits and `docs/history/260717.md` remain outside the reviewed commits.
- Stage C files were not changed.

## Confirmed Results

- `npm run test:method-status`: 18/18 pass.
- `npm run check:method-status`: cache is up to date, 22 methods.
- `npx tsc --noEmit`: pass.
- `npm run build`: pass; 31 static pages generated.
- `git diff --check 564ec8b..b0817d5`: pass.
- The status dashboard renders 22 method rows from generated data and no longer contains `METHOD_STATUS`.
- Calculator readiness no longer reads `hasDetail`; remaining references are the legacy type/data fields only.
- `/?method=mps` cannot select MPS and falls back to the first enabled method, MDM.
- MDM exposes `/?method=mdm`; incomplete methods show a disabled `开发中` control.
- Detail tabs remain visible. A live MDM check showed `可信性验证` as `进行中`, while the platform-level comparison tab remains available.

## Findings

### [P1] Failed MDM initialization presents a local MLE result under the MDM identity

File: `src/app/page.tsx:111`

The initialization path first computes `initialResult` with `calculateWeibullParameters()`, then requests the selected enabled method. If `calculateWeibull()` fails, the empty `catch` deliberately keeps that local result. The card is subsequently assigned `methodId: selectedMethodId`, so an MDM card can display the local MLE estimate.

This is not theoretical. With port 8001 unreachable, a fresh browser load of `/?method=mdm` displayed an `MDM` card with populated beta/eta/gamma values. No MDM response existed. This violates the explicit Task 5 requirement not to reuse the local MLE result under another method ID.

Required correction:

- never retain a `calculateWeibullParameters()` result as the result of a selected status-enabled method;
- if the selected method request fails, leave its result unset or show an explicit failure state;
- keep seed/data initialization independent from method-result identity;
- add focused verification for the failed-backend path, not only the successful MDM path.

### [P2] The no-enabled-method branch still labels a card as MLE

File: `src/app/page.tsx:136`

`methodId: selectedMethodId ?? 'mle'` contradicts the handoff requirement to initialize without a selected method when `getEnabledMethodIds()` is empty. It reintroduces an unavailable MLE identity precisely in the branch that must have no default method.

Required correction:

- represent the no-enabled state without defaulting to `mle`;
- do not create a method-labelled result card until an enabled method exists;
- verify the zero-enabled branch with a focused unit/helper test or equivalent deterministic probe.

### [P2] First-layer readiness does not use the approved-exception completion rule

File: `src/app/help/changelog/page.tsx:45`

The dashboard increments readiness only for raw `status === 'done'`. The Stage A derivation treats `not_applicable` plus `exception_approved: true` as complete, so a method can derive `calculatorEnabled: true` while the dashboard reports `5/6` or lower.

Required correction:

- derive first-layer readiness from `missingLayer1` or apply the same completion rule used by Stage A;
- do not maintain a second, narrower definition of completion in the dashboard.

## Reverification

After correction, rerun:

```powershell
npm run test:method-status
npm run check:method-status
npx tsc --noEmit
npm run build
git diff --check
```

Also verify these behaviors:

```text
backend unavailable + ?method=mdm -> no populated MDM result from local MLE
?method=mps -> MPS remains blocked
zero enabled methods -> no MLE-labelled default card/result
approved not_applicable layer-one item -> readiness agrees with derived calculator availability
```

## Report Handling

After the fixes, append a revision section to the Stage B executor report with the correction commit, exact verification output and the four focused behavior checks above. Commit the focused code changes and updated report, then stop and return to Codex for re-review.

## Paper Requests

No new paper is required for this revision. Existing Stage A `PAPER_NEEDED` entries remain unchanged.

## Conclusion

The single-source frontend migration, calculator selector gate and detail-page status mapping are directionally correct, but the calculator initialization still permits a concrete method-identity misrepresentation. Stage B is not approved until the focused corrections above are implemented and re-reviewed. Stage C is not authorized.

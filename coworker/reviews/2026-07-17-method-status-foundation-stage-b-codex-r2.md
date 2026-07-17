# Stage B Codex Re-review

VERDICT: APPROVE

## Scope Check

- Review baseline: `b0817d5`.
- Correction commit: `0cb97f8`.
- Revised executor report: `409b925`.
- The correction changes only `src/app/page.tsx` and `src/app/help/changelog/page.tsx`; the report commit changes only the Stage B executor report.
- `Study/01` working-tree edits and `docs/history/260717.md` remain outside the reviewed commits.
- Stage C files were not changed.

## Resolution of Previous Findings

### Selected-method result identity

RESOLVED. A failed selected-method request now clears `initialResult`; it cannot retain the local `calculateWeibullParameters()` value under the selected method ID.

With port 8001 unavailable, a fresh `/?method=mdm` browser check showed the MDM card with `无参数` and no populated beta/eta/gamma result. The previous local-MLE-under-MDM reproduction no longer occurs.

### Zero-enabled-method behavior

RESOLVED. The card receives `methodId: selectedMethodId` without an MLE fallback, and the no-enabled branch explicitly clears `initialResult`.

### First-layer readiness semantics

RESOLVED. The dashboard now calculates readiness from `6 - missingLayer1.length`, reusing the Stage A completion derivation that treats an approved `not_applicable` item as complete.

## Independent Verification

Run from the repository root on 2026-07-17:

```text
npm run test:method-status
18 tests, 18 passed, 0 failed

npm run check:method-status
method-status: cache is up to date (22 methods).

npx tsc --noEmit
pass

npm run build
pass; 31 static pages generated

git diff --check b0817d5..409b925
pass
```

Focused browser checks with the backend unavailable:

```text
?method=mdm -> MDM selected, parameter area reports no parameters, no local MLE result shown
?method=mps -> MPS not selected, falls back to enabled MDM, no fabricated result shown
```

The local FastAPI process could not be started for an additional live success-path check because this machine's active Python environment lacks `torch`. Compensating evidence: the success branch still assigns the returned `calculateWeibull()` result directly, TypeScript passes, and the production Next.js build succeeds. This environment limitation does not invalidate the focused regression check.

No new actionable findings were identified.

## Paper Requests

No new paper is required. Existing Stage A `PAPER_NEEDED` entries remain unchanged.

## Conclusion

Stage B satisfies Tasks 4–6 and the approved handoff. The frontend consumers now use the generated single-source status, calculator selection is gated by first-layer completion without method-identity fallback, and detail pages expose truthful construction states.

Stage C may be authorized through a new, scoped handoff. Do not begin it without that handoff, and preserve the existing paper stop rules.

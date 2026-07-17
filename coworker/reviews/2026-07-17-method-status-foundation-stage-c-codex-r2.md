# Stage C Codex Re-review

VERDICT: APPROVE

## Scope Check

- Previous Stage C baseline/report: `88bd731`.
- Test-isolation correction: `d023de3`.
- Revised executor report: `ca1d2c4`.
- The correction changes only `python/tests/test_calculation_api.py`; the report commit changes only the Stage C executor report.
- `Study/01` working-tree edits and `docs/history/260717.md` remain outside the reviewed commits.
- No Phase 1 work was started.

## Resolution of Previous Finding

RESOLVED. The fake `torch` modules are installed by an autouse pytest fixture after collection, their prior `sys.modules` values are saved, and the values are restored during fixture teardown.

The exact full suite now collects and passes. A separate in-process probe also confirmed that `torch`, `torch.nn`, and `torch.nn.modules` match their pre-test states after pytest returns.

## Independent Verification

Run from the repository root on 2026-07-17:

```text
python -m pytest python/tests -q
131 passed

python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py -q
17 passed

torch restoration probe
4 passed; torch_modules_restored=True

npm run test:method-status
18 tests, 18 passed, 0 failed

npm run check:method-status
method-status: cache is up to date (22 methods).

npx tsc --noEmit
pass

npm run build
pass; 31 static pages generated

git diff --check 88bd731..ca1d2c4
pass

text audit for METHOD_STATUS, calculator hasDetail gate and WMLE fallback
no matches
```

No new actionable findings were identified.

## Status, Evidence, and Papers

- `05-状态.md` remains the sole editable method-capability source; generated status still covers all 22 leaf methods exactly once.
- Only MDM remains calculator-enabled. MLE, MMLE, WMLE, and LRE remain first-layer in progress; the remaining 17 methods remain not started.
- MLE, MMLE, and LRE `PAPER_NEEDED` records remain blocked and unchanged.
- No new paper is required by this review.

## Conclusion

Stage C satisfies Tasks 7–8 and the final audit contract. Silent WMLE substitution is removed, backend and frontend method identities are enforced, authority documents are synchronized, and the complete verification suite passes.

Stage A, Stage B, and Stage C are approved. Phase 0 — the single method-status source and identity-safety foundation — is complete.

Phase 1 may begin only through a new scoped handoff. Existing paper stop rules continue to apply.

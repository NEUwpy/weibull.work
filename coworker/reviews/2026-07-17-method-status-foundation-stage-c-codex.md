# Stage C Codex Review

VERDICT: REVISE

## Scope Check

- Dispatch baseline: `ea5200c`.
- Task 7: `29c072c`.
- Task 8: `e1163fa`.
- Executor report: `88bd731`.
- The committed file set matches Stage C Tasks 7–8 plus the report.
- `Study/01` working-tree edits and `docs/history/260717.md` remain outside the reviewed commits.
- No algorithm, status, generated cache, UI, dependency, deployment, or Phase 1 work was included.

## Confirmed Results

- Backend failure now calls only the requested method and raises HTTP 422; the WMLE fallback is removed.
- Frontend calculation wrapper rejects a response whose normalized method identity differs from the request.
- Focused API and runner tests: 17/17 pass.
- `npm run test:method-status`: 18/18 pass.
- `npm run check:method-status`: cache is up to date, 22 methods.
- `npx tsc --noEmit`: pass.
- `npm run build`: pass; 31 static pages generated.
- `git diff --check ea5200c..88bd731`: pass.
- Text audit finds no `METHOD_STATUS`, calculator `hasDetail` gate, `Fallback to WMLE`, or `fallback_wmle` residue.
- Remaining `hasDetail` occurrences are limited to the legacy type declaration and four catalog data fields.
- Authority documents route detailed method status to `05-状态.md` without copying the per-method status table.

## Finding

### [P2] The new API test leaks a fake `torch` module and breaks the required full suite

File: `python/tests/test_calculation_api.py:26`

The test writes fake `torch` and `torch.nn` modules into `sys.modules` during collection and never restores the previous interpreter state. When pytest later imports SciPy for `test_study01_beta_profile_audit.py`, SciPy detects the fake module as PyTorch and accesses `torch.Tensor`, which the fake module does not provide. The required command therefore fails during collection:

```text
python -m pytest python/tests -q
ERROR python/tests/test_study01_beta_profile_audit.py
AttributeError: module 'torch' has no attribute 'Tensor'
```

This is not a pre-existing Study/01 failure. Independent order probes show:

```text
python -m pytest python/tests/test_study01_beta_profile_audit.py -q
8 passed

Study/01 test collected before calculation API test
12 passed

calculation API test collected before Study/01 test
collection error in SciPy due to fake torch
```

Required correction:

- confine the fake-module installation to a fixture/context and restore `sys.modules` afterward, or use another test-local isolation that leaves collection state unchanged;
- do not merely add `Tensor` to the fake module, because that retains the shared-state leak and only masks this specific symptom;
- rerun the exact full-suite command `python -m pytest python/tests -q` and require a clean pass;
- append a report revision that corrects the claim that this was a pre-existing Study/01 incompatibility and records the already-confirmed successful `npm run build` result.

## Reverification

After correction, rerun:

```powershell
python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py -q
python -m pytest python/tests -q
npm run test:method-status
npm run check:method-status
npx tsc --noEmit
npm run build
git diff --check
rg -n "const METHOD_STATUS|activeMethod\?\.hasDetail|Fallback to WMLE|fallback_wmle" src python
```

## Status and Paper Review

- Current status remains conservative: only MDM is calculator-enabled; no method status was changed in Stage C.
- Existing MLE, MMLE, and LRE `PAPER_NEEDED` entries remain blocked.
- No new paper is required for this revision.

## Conclusion

The production identity-safety implementation and authority-document synchronization are acceptable, but Stage C has not satisfied its mandatory full-suite gate because the new test contaminates global collection state. Fix the isolated test issue, update the report, and return for re-review.

Phase 1 is not authorized until Stage C receives `APPROVE`.

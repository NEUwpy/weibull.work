# Method Status Foundation Implementation Plan

> **For agentic workers:** REQUIRED SKILL: use `coworker` and execute this plan through `coworker/handoffs/2026-07-17-method-status-foundation-hermes.md`. Track steps with the checkboxes below.

**Goal:** Make `05-状态.md` the single editable status source for traditional method construction, drive the existing dashboard and calculator gate from it, expose truthful incomplete states in method details, and remove silent method substitution.

**Architecture:** Store source status in YAML front matter inside `05-状态.md`. A small Node generator parses and validates the document against `src/data/methods.json`, derives contiguous maturity levels, and writes a committed read-only JSON cache for client components. TypeScript consumers import that cache; Python remains the executable backend truth and is checked independently.

**Tech Stack:** Node.js, `gray-matter`, Node built-in test runner, TypeScript/Next.js 14, Python/FastAPI/pytest.

---

## Known Facts

- `src/app/help/changelog/page.tsx` currently hardcodes `METHOD_STATUS`.
- `src/components/calculator/MethodSelector.tsx` currently uses `method.hasDetail` as the calculator gate.
- `src/app/methods/[methodId]/page.tsx` always exposes the apply link and does not consume construction status.
- `src/app/page.tsx` ignores `?method=` and defaults to MLE.
- `python/main.py::_run_calculation_method()` silently retries WMLE after the selected algorithm fails.
- The frontend response wrapper ignores the backend `method` identity.
- Current smoke evidence shows MLE, MMLE, WMLE, MDM and LRE return estimates; MPS, LSE, MM, PWM, Grey and Bayesian are registered but raise `NotImplementedError` through the runner.
- Local dedicated papers exist for MDM and WMLE. Full local dedicated papers have not yet been found for MLE, MMLE and LRE.
- The working tree contains unrelated `Study/01` edits and `docs/history/260717.md`; they are outside this task.

## File Map

Create:

- `scripts/lib/method-status.mjs` — parsing, schema validation and maturity derivation.
- `scripts/generate-method-status.mjs` — CLI for write/check modes.
- `scripts/tests/method-status.test.mjs` — Node unit tests for schema and derivation.
- `src/data/method-status.generated.json` — committed read-only generated cache.
- `src/lib/method-status.ts` — typed client/server accessors.
- `src/components/methods/MethodBuildStatus.tsx` — shared incomplete/blocked status panel.
- `python/tests/test_calculation_api.py` — API helper tests for no fallback and identity.

Modify:

- `05-状态.md`
- `package.json`
- `src/app/help/changelog/page.tsx`
- `src/lib/methods.ts`
- `src/components/calculator/MethodSelector.tsx`
- `src/app/page.tsx`
- `src/app/methods/[methodId]/page.tsx`
- `src/hooks/useWeibullCalculation.ts`
- `python/main.py`
- `README.md`
- `02-规则.md`
- `06-模块.md`
- `08-更新日志.md`

Do not edit any other file without stopping and reporting the need.

## Staged Execution Gates

This plan is executed in three separate Hermes runs:

1. **Stage A — Tasks 1–3:** parser tests, validator/generator, conservative `05-状态.md` migration and generated cache. Report to `coworker/reports/2026-07-17-method-status-foundation-stage-a-hermes.md`, then stop for Codex review.
2. **Stage B — Tasks 4–6:** typed accessors, dashboard, calculator gate, URL selection and detail-page status. Start only after Stage A receives `APPROVE`.
3. **Stage C — Tasks 7–8:** remove method substitution, validate response identity, synchronize authority docs and run the full suite. Start only after Stage B receives `APPROVE`.

Do not continue into the next stage in the same Hermes run. Codex writes a separate interim review after Stages A and B; the full audit contract applies after Stage C.

## Boundaries

### Allowed

- Preserve the existing visual design while replacing status data flow.
- Add a committed generated JSON cache, provided `05-状态.md` remains the only editable status source.
- Conservatively downgrade stale status claims when evidence is missing.
- Add focused TypeScript helpers, Node validation tests and Python API tests.

### Not Allowed

- Do not implement any missing estimation algorithm in this phase.
- Do not redesign the method overview or calculator selector.
- Do not add construction badges to the method overview.
- Do not mark a paper complete from 181-004 alone.
- Do not preserve current calculator availability through a legacy override.
- Do not modify `Study/01`, `Study/02`, `docs/history/`, `_archive/` or credentials.
- Do not push, merge or deploy.

## STOP Conditions

- A required path in the file map does not exist and no equivalent current path is discoverable.
- The method leaf IDs in `src/data/methods.json` are not exactly the expected 22 IDs.
- Making calculator selection fail closed requires a broad calculator redesign rather than the focused data-source change described here.
- A `done` status cannot be supported by an existing evidence path.
- A dedicated paper is required to upgrade a method: emit `PAPER_NEEDED`, keep the paper status `blocked`, and continue independent infrastructure work.
- Tests reveal that removing fallback breaks an undocumented external API contract requiring user choice.

## Stage A: Status source and generated cache

### Task 1: Add failing status parser and derivation tests

**Files:**

- Create: `scripts/tests/method-status.test.mjs`
- Test target: `scripts/lib/method-status.mjs`

- [ ] **Step 1: Write Node tests before the parser exists**

Use `node:test` and `node:assert/strict`. The tests must import these exact exports:

```js
import {
  deriveMethodCapability,
  validateStatusDocument,
} from '../lib/method-status.mjs'
```

Cover these exact behaviors:

```js
test('first layer requires paper and all five layer-one items', () => {
  const method = completeMethod('mdm')
  method.layer1.process.status = 'in_progress'
  const capability = deriveMethodCapability(method)
  assert.equal(capability.level, 'layer1_in_progress')
  assert.equal(capability.calculatorEnabled, false)
  assert.deepEqual(capability.missingLayer1, ['process'])
})

test('closed loop requires contiguous completion', () => {
  const method = completeMethod('mdm')
  assert.equal(deriveMethodCapability(method).level, 'closed_loop')
})

test('done requires evidence', () => {
  const method = completeMethod('mdm')
  method.layer1.backend.evidence = []
  assert.throws(
    () => validateStatusDocument(statusDoc([method]), ['mdm']),
    /done.*evidence/i,
  )
})

test('blocked requires a reason', () => {
  const method = completeMethod('mdm')
  method.paper = { status: 'blocked', evidence: [] }
  assert.throws(
    () => validateStatusDocument(statusDoc([method]), ['mdm']),
    /blocked.*reason/i,
  )
})

test('document must cover the exact leaf method set', () => {
  assert.throws(
    () => validateStatusDocument(statusDoc([completeMethod('mdm')]), ['mdm', 'mle']),
    /method id/i,
  )
})
```

The local helpers `completeMethod()` and `statusDoc()` must construct fully valid objects; do not weaken production validation merely to simplify fixtures.

- [ ] **Step 2: Run the test and confirm the expected import failure**

Run:

```powershell
node --test scripts/tests/method-status.test.mjs
```

Expected: FAIL because `scripts/lib/method-status.mjs` does not exist.

### Task 2: Implement the parser, validator and generator

**Files:**

- Create: `scripts/lib/method-status.mjs`
- Create: `scripts/generate-method-status.mjs`
- Modify: `package.json`

- [ ] **Step 1: Implement a strict schema without adding a new dependency**

Use `gray-matter` for front matter parsing and ordinary JavaScript validation. Export:

```js
export const STATUS_VALUES = ['todo', 'in_progress', 'done', 'blocked', 'not_applicable']
export const LAYER1_KEYS = ['backend', 'tests', 'calculator', 'theory', 'process']
export const LAYER2_KEYS = ['calculation', 'analysis']
export const LAYER3_KEYS = ['applicability', 'verification']

export function validateStatusDocument(document, expectedLeafIds) {}
export function deriveMethodCapability(method) {}
export function buildGeneratedStatus(document, expectedLeafIds) {}
export function parseStatusMarkdown(markdown, expectedLeafIds) {}
```

`deriveMethodCapability()` must return:

```js
{
  id: method.id,
  level: 'not_started' | 'layer1_in_progress' | 'layer1_complete' |
         'layer2_complete' | 'closed_loop',
  calculatorEnabled: boolean,
  missingLayer1: string[],
  paper: method.paper,
  items: {
    theory: method.layer1.theory,
    process: method.layer1.process,
    calculation: method.layer2.calculation,
    analysis: method.layer2.analysis,
    applicability: method.layer3.applicability,
    verification: method.layer3.verification,
  },
}
```

Validation must reject duplicate/missing/extra IDs, unknown status values, `done` without evidence, `blocked` without reason, missing citation metadata for a completed paper, and `not_applicable` on mandatory layer fields unless `exception_approved: true` plus a reason is present.

- [ ] **Step 2: Implement deterministic write and check modes**

`scripts/generate-method-status.mjs` must:

1. read `05-状态.md` and `src/data/methods.json` from the repository root;
2. flatten `children` to obtain the expected leaf IDs;
3. parse, validate and derive capabilities;
4. serialize stable pretty JSON ending in one newline;
5. write `src/data/method-status.generated.json` by default;
6. with `--check`, compare expected output with the committed file and exit non-zero with an actionable message if stale.

The JSON must include `schemaVersion`, `source: "05-状态.md"`, and the normalized methods. Do not include timestamps, absolute paths or other nondeterministic fields.

- [ ] **Step 3: Add package scripts**

Add exactly these scripts while preserving existing scripts:

```json
"generate:method-status": "node scripts/generate-method-status.mjs",
"check:method-status": "node scripts/generate-method-status.mjs --check",
"test:method-status": "node --test scripts/tests/method-status.test.mjs",
"predev": "npm run generate:method-status",
"prebuild": "npm run check:method-status"
```

- [ ] **Step 4: Run parser tests**

Run:

```powershell
npm run test:method-status
```

Expected: all parser and derivation tests pass.

- [ ] **Step 5: Commit the parser unit**

Commit only Task 1–2 files:

```powershell
git add -- package.json scripts/lib/method-status.mjs scripts/generate-method-status.mjs scripts/tests/method-status.test.mjs
git commit -m "feat: validate method construction status"
```

### Task 3: Migrate `05-状态.md` conservatively

**Files:**

- Modify: `05-状态.md`
- Create: `src/data/method-status.generated.json`

- [ ] **Step 1: Add YAML front matter for all 22 leaf IDs**

Use this top-level shape:

```yaml
---
schema_version: 1
methods:
  - id: mdm
    name: 最小差异法
    family: min_adequacy
    classification_source: src/content/181-004-pdf原文.md
    shared_core: null
    paper:
      status: done
      title: 基于统计最小差异原理的威布尔分布参数估计方法
      publication: 东北大学学报（自然科学版）
      year: 2025
      stable_id: 1005-3026(2025)07-0108-06
      evidence:
        - src/content/182-046-pdf原文.md
    layer1:
      backend: { status: done, evidence: [python/methods/mdm.py] }
      tests: { status: done, evidence: [python/tests/test_runner.py, python/tests/test_mdm_single_source.py] }
      calculator: { status: done, evidence: [src/hooks/useWeibullCalculation.ts] }
      theory: { status: done, evidence: [src/content/algorithms/mdm.md] }
      process: { status: done, evidence: [src/data/method_flows/mdm.json] }
    layer2:
      calculation: { status: done, evidence: [src/components/methods/mdm] }
      analysis: { status: done, evidence: [src/components/methods/mdm] }
    layer3:
      applicability: { status: done, evidence: [public/studies/mdm] }
      verification: { status: in_progress, evidence: [public/case-studies/mdm] }
---
```

Apply the same complete schema to every leaf ID. Evidence may contain files or directories, but every path must exist.

- [ ] **Step 2: Use conservative migration rules**

- Preserve an old `done` only after confirming its evidence exists and actually serves that method.
- Mark backend `done` only for MLE, MMLE, WMLE, MDM and LRE after rerunning the fixed-sample smoke test.
- Mark registered placeholders such as MPS, LSE, MM, PWM, Grey and Bayesian as `todo` or `in_progress`, never `done`.
- Mark current alias-only variants WLSE, EIV, BLRE, LM, TLM, Gibbs and MAP as not independently implemented.
- Mark MVE, LSF, PSO, SVR and ANN as not implemented.
- Mark MDM and WMLE paper evidence from their local dedicated paper files.
- Mark missing full dedicated papers `blocked` with `PAPER_NEEDED` in the reason; do not mark them complete from 181-004.
- Do not add a legacy calculator override. Calculator availability must derive from complete first-layer evidence.

- [ ] **Step 3: Rewrite the Markdown body as a control guide**

Remove the manually maintained method status table. Keep concise human-readable sections for:

- three construction layers;
- status legend;
- automatic derivation rules;
- evidence requirements;
- paper handoff;
- generated-cache command;
- links to the design and master roadmap.

The body must not duplicate per-method status values from YAML.

- [ ] **Step 4: Generate and verify the cache**

Run:

```powershell
npm run generate:method-status
npm run check:method-status
npm run test:method-status
```

Expected: all commands pass and the generated JSON contains exactly 22 methods.

- [ ] **Step 5: Commit the source and generated cache**

```powershell
git add -- 05-状态.md src/data/method-status.generated.json
git commit -m "docs: establish method status source"
```

## Stage B: Frontend consumers

### Task 4: Add typed accessors and render the dashboard from generated data

**Files:**

- Create: `src/lib/method-status.ts`
- Modify: `src/app/help/changelog/page.tsx`

- [ ] **Step 1: Add typed accessors**

Export these types and functions:

```ts
export type AtomicStatus = 'todo' | 'in_progress' | 'done' | 'blocked' | 'not_applicable'
export type MethodLevel = 'not_started' | 'layer1_in_progress' | 'layer1_complete' | 'layer2_complete' | 'closed_loop'

export function getMethodCapability(methodId: string | undefined): MethodCapability | undefined
export function isCalculatorEnabled(methodId: string | undefined): boolean
export function getEnabledMethodIds(): string[]
export function getMethodCapabilities(): MethodCapability[]
```

The module must only read `src/data/method-status.generated.json`; it must not re-declare status data.

- [ ] **Step 2: Replace dashboard constants with generated status**

Remove `METHOD_STATUS` and the local method-status interface from `src/app/help/changelog/page.tsx`. Render all 22 methods from `getMethodCapabilities()`. Keep the existing table visual language, add derived level and first-layer readiness, and keep “方法对比” outside individual maturity calculations.

- [ ] **Step 3: Verify TypeScript and status freshness**

```powershell
npm run check:method-status
npx tsc --noEmit
```

Expected: both pass; `rg -n "const METHOD_STATUS" src/app/help/changelog/page.tsx` returns no matches.

- [ ] **Step 4: Commit the dashboard migration**

```powershell
git add -- src/lib/method-status.ts src/app/help/changelog/page.tsx
git commit -m "feat: render method status from docs"
```

### Task 5: Gate the existing calculator UI and honor `?method=`

**Files:**

- Modify: `src/lib/methods.ts`
- Modify: `src/components/calculator/MethodSelector.tsx`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Remove `hasDetail` from calculator readiness**

Keep `hasDetail` temporarily only for legacy detail-content lookup if still required. In `MethodSelector`, replace every calculator-ready check with:

```ts
const isImplemented = isCalculatorEnabled(method.id)
```

Use the same result for row styling, “开发中”, confirmation and disabled state. Do not change layout, labels or animation.

- [ ] **Step 2: Select only enabled methods from URL/default initialization**

In `src/app/page.tsx`:

- read `searchParams.get('method')`;
- accept it only when `isCalculatorEnabled(requestedMethod)` is true;
- otherwise choose the first ID from `getEnabledMethodIds()`;
- if no method is enabled, initialize without a selected method and do not label local MLE output as an available method;
- when an enabled requested method exists, calculate through `calculateWeibull()` rather than reusing the local MLE result under another method ID.

The existing `caseId` behavior must continue to work.

- [ ] **Step 3: Verify behavior without redesign**

Manually verify:

- enabled method can be selected;
- incomplete method remains visible, grey and labelled “开发中”;
- `/?method=mdm` preselects and calculates MDM when MDM is enabled by the generated status;
- `/?method=mps` does not bypass the gate while MPS remains incomplete;
- no method-status badge is added to `/methods`.

- [ ] **Step 4: Run checks and commit**

```powershell
npm run check:method-status
npx tsc --noEmit
git diff --check
```

Then:

```powershell
git add -- src/lib/methods.ts src/components/calculator/MethodSelector.tsx src/app/page.tsx
git commit -m "feat: gate calculator by method maturity"
```

### Task 6: Show truthful incomplete states in method details

**Files:**

- Create: `src/components/methods/MethodBuildStatus.tsx`
- Modify: `src/app/methods/[methodId]/page.tsx`

- [ ] **Step 1: Implement one shared status panel**

The component accepts:

```ts
interface MethodBuildStatusProps {
  label: string
  status: AtomicStatus
  reason?: string
  evidence?: string[]
}
```

Render “未开始”“进行中”“受阻” or the approved exception state. Do not show raw filesystem paths to ordinary users unless the existing Help/document rendering convention already exposes them; evidence can remain available on the Help dashboard.

- [ ] **Step 2: Gate content, not tab visibility**

Keep all current tabs visible. Before rendering each tab body, read its atomic status:

- theory → `layer1.theory`
- flow → `layer1.process`
- lab → `layer2.calculation`
- analysis → `layer2.analysis`
- examples → `layer3.applicability`
- cases → `layer3.verification`

If the status is not `done`, render `MethodBuildStatus` instead of an empty viewer or misleading generic content. Keep “方法对比” unchanged as a platform-level tab.

- [ ] **Step 3: Gate the apply link without changing the page layout**

For first-layer complete methods, retain the link to `/?method=${method.id}`. Otherwise render the same visual position as a disabled control labelled “开发中”; do not allow navigation that bypasses the calculator gate.

- [ ] **Step 4: Verify and commit**

```powershell
npx tsc --noEmit
git diff --check
```

Then:

```powershell
git add -- src/components/methods/MethodBuildStatus.tsx "src/app/methods/[methodId]/page.tsx"
git commit -m "feat: expose method construction states"
```

## Stage C: Method identity safety and authority synchronization

### Task 7: Remove silent WMLE substitution and validate method identity

**Files:**

- Create: `python/tests/test_calculation_api.py`
- Modify: `python/main.py`
- Modify: `src/hooks/useWeibullCalculation.ts`

- [ ] **Step 1: Write failing Python tests**

Use `monkeypatch` to replace `main.run_method`. Test that a failed selected method:

- calls `run_method` exactly once with the requested ID;
- raises `HTTPException` with a clear detail;
- never calls WMLE;
- preserves the requested method identity on success.

Core assertion:

```python
assert calls == ["mle"]
assert exc.value.status_code == 422
assert "mle" in exc.value.detail
```

Run:

```powershell
python -m pytest python/tests/test_calculation_api.py -q
```

Expected: FAIL because the current helper calls WMLE.

- [ ] **Step 2: Fail explicitly in the backend**

Change `_run_calculation_method()` so a missing estimate raises HTTP 422 using the selected method ID and runner error. Delete the fallback call and fallback-labelled method response.

- [ ] **Step 3: Validate identity in the frontend wrapper**

Extend `CalculateResponse` to include `methodId`. After parsing the backend response:

```ts
if (res.method !== methodId.toLowerCase()) {
  throw new Error(`方法身份不一致：请求 ${methodId}，返回 ${res.method}`)
}
```

Return the validated method identity to callers. Do not silently accept a fallback suffix.

- [ ] **Step 4: Run focused and regression tests**

```powershell
python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py -q
python -m pytest python/tests -q
npx tsc --noEmit
```

Expected: all pass.

- [ ] **Step 5: Commit the safety fix**

```powershell
git add -- python/main.py python/tests/test_calculation_api.py src/hooks/useWeibullCalculation.ts
git commit -m "fix: fail selected methods without substitution"
```

### Task 8: Synchronize authority docs and run final verification

**Files:**

- Modify: `README.md`
- Modify: `02-规则.md`
- Modify: `06-模块.md`
- Modify: `08-更新日志.md`

- [ ] **Step 1: Clarify document authority without duplicating detailed status**

- README remains the project entry and project-wide snapshot, but routes detailed method construction status to `05-状态.md`.
- Remove or correct the stale “11 backend implementations” claim; do not replace it with a count that must be manually synchronized on every method change.
- `02-规则.md` must state that `05-状态.md` is the single editable method-capability source and generated JSON is derived.
- `06-模块.md` must describe first-layer calculator gating and shared-core/independent-variant rules.
- `08-更新日志.md` records this completed infrastructure change only after implementation checks pass.

- [ ] **Step 2: Run complete verification**

```powershell
npm run test:method-status
npm run check:method-status
npx tsc --noEmit
python -m pytest python/tests -q
npm run build
git diff --check
```

Also run:

```powershell
rg -n "const METHOD_STATUS|activeMethod\?\.hasDetail|Fallback to WMLE|fallback_wmle" src python
```

Expected: no status hardcode, calculator `hasDetail` gate or WMLE fallback remains. Remaining `hasDetail` references are allowed only for legacy content lookup and must be listed in the report.

- [ ] **Step 3: Confirm scope**

Run:

```powershell
git status --short
$reviewBase = git merge-base HEAD origin/main
git diff --name-only "$reviewBase...HEAD"
```

The implementation commits must not include `Study/01`, `Study/02`, `docs/history/260717.md`, credentials or unrelated files. The diff from the merge base may also list the approved design and plan bundle; identify those as planning inputs rather than executor changes in the report.

- [ ] **Step 4: Write the executor report**

Write `coworker/reports/2026-07-17-method-status-foundation-stage-c-hermes.md` with:

- start and end commits;
- changed files grouped by task;
- exact checks and results;
- generated-data relationship;
- initial status counts and which methods are calculator-enabled;
- every conservative downgrade from the old table;
- every `PAPER_NEEDED` item;
- skipped checks and reasons;
- deviations and blockers.

Reference the approved Stage A and Stage B reports rather than copying their detailed evidence.

Do not mark the task complete in project docs until Codex returns `APPROVE`.

## Codex Acceptance Gate

Codex reviews using `coworker/reviews/2026-07-17-method-status-foundation-codex-contract.md` and returns exactly one verdict: `APPROVE`, `REVISE`, or `BLOCK`.

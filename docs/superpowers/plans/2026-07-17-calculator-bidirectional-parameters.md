# Calculator Bidirectional Parameters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the calculator's parameter → sample and sample → parameter workflows without reintroducing mislabeled fallback estimates.

**Architecture:** Keep `result` as the parameter/chart value object and use `fitMode` as provenance: `manual` for defaults or direct edits, `fit` only for a verified backend estimate. Extract deterministic parameter-state helpers so the core mode, reset, sample-generation, and estimate-validation rules are unit tested independently of the large React components.

**Tech Stack:** Next.js 14, React 18, TypeScript 5, Node 22 built-in test runner, existing Weibull chart/calculation utilities.

---

## File Map

- Create `src/lib/calculator-state.ts`: pure defaults, mode switching, sample generation, and estimate validation.
- Create `scripts/tests/calculator-state.test.mjs`: Node unit tests for the pure calculator contract.
- Modify `package.json`: add the focused calculator-state test command.
- Modify `src/app/page.tsx`: initialize manual parameters, preserve them across sample changes and failures, enforce 3P-only estimation, and store each card's last 3P gamma.
- Modify `src/components/calculator/AnalysisCard.tsx`: reuse sample generation, implement mode-aware reset, and rename the reset button.
- Do not modify algorithms, `05-状态.md`, generated status, method gating, or protected research files.

### Task 1: Add tested calculator-state primitives

**Files:**
- Create: `scripts/tests/calculator-state.test.mjs`
- Create: `src/lib/calculator-state.ts`
- Modify: `package.json`

- [ ] **Step 1: Add the focused test script and failing tests**

Add this script to `package.json`:

```json
"test:calculator-state": "node --experimental-strip-types --test scripts/tests/calculator-state.test.mjs"
```

Create `scripts/tests/calculator-state.test.mjs`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  generateWeibullSample,
  getDefaultParameters,
  getEstimateFailure,
  toggleParameterMode,
} from '../../src/lib/calculator-state.ts'

test('3P and 2P defaults use the approved parameters', () => {
  assert.deepEqual(getDefaultParameters(true), { beta: 2, eta: 1000, gamma: 1000 })
  assert.deepEqual(getDefaultParameters(false), { beta: 2, eta: 1000, gamma: 0 })
})

test('parameter mode preserves and restores the last 3P gamma', () => {
  const twoP = toggleParameterMode({ is3P: true, currentGamma: 750, last3PGamma: 1000 })
  assert.deepEqual(twoP, { is3P: false, gamma: 0, last3PGamma: 750 })

  const threeP = toggleParameterMode(twoP)
  assert.deepEqual(threeP, { is3P: true, gamma: 750, last3PGamma: 750 })
})

test('sample generation uses the current parameters', () => {
  const sample = generateWeibullSample(2, { beta: 2, eta: 1000, gamma: 1000 }, () => 0.5)
  const expected = 1000 + 1000 * Math.sqrt(-Math.log(0.5))
  assert.equal(sample.length, 2)
  assert.equal(sample[0].value, expected)
  assert.deepEqual(sample.map(({ id, status }) => ({ id, status })), [
    { id: 0, status: 'F' },
    { id: 1, status: 'F' },
  ])
})

test('invalid and non-converged estimates return explicit failures', () => {
  assert.equal(
    getEstimateFailure({ beta: null, eta: 100, gamma: 0 }),
    '参数估计未返回完整参数',
  )
  assert.equal(
    getEstimateFailure({ beta: 2, eta: 100, gamma: 0, converged: false }),
    '参数估计未收敛',
  )
  assert.equal(
    getEstimateFailure({ beta: 2, eta: 100, gamma: 0, converged: 'unbounded' }),
    '参数估计无解',
  )
  assert.equal(getEstimateFailure({ beta: 2, eta: 100, gamma: 0, converged: true }), null)
})
```

- [ ] **Step 2: Run the focused test and verify the red state**

Run:

```powershell
npm run test:calculator-state
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/lib/calculator-state.ts`.

- [ ] **Step 3: Implement the pure state helpers**

Create `src/lib/calculator-state.ts`:

```ts
export type CalculatorParameters = {
  beta: number
  eta: number
  gamma: number
}

export type EstimateCandidate = {
  beta: number | null
  eta: number | null
  gamma: number
  converged?: boolean | string
}

export type ParameterModeState = {
  is3P: boolean
  gamma: number
  last3PGamma: number
}

export const DEFAULT_3P_PARAMETERS: CalculatorParameters = {
  beta: 2,
  eta: 1000,
  gamma: 1000,
}

export function getDefaultParameters(is3P: boolean): CalculatorParameters {
  return { ...DEFAULT_3P_PARAMETERS, gamma: is3P ? DEFAULT_3P_PARAMETERS.gamma : 0 }
}

export function toggleParameterMode(state: {
  is3P: boolean
  currentGamma?: number
  gamma?: number
  last3PGamma: number
}): ParameterModeState {
  if (state.is3P) {
    const savedGamma = state.currentGamma ?? state.gamma ?? DEFAULT_3P_PARAMETERS.gamma
    return { is3P: false, gamma: 0, last3PGamma: savedGamma }
  }
  const restoredGamma = Number.isFinite(state.last3PGamma)
    ? state.last3PGamma
    : DEFAULT_3P_PARAMETERS.gamma
  return { is3P: true, gamma: restoredGamma, last3PGamma: restoredGamma }
}

export function generateWeibullSample(
  n: number,
  parameters: CalculatorParameters,
  random: () => number = Math.random,
) {
  if (!Number.isInteger(n) || n <= 0) throw new Error('样本数必须为正整数')
  if (!(parameters.beta > 0) || !(parameters.eta > 0)) throw new Error('beta 和 eta 必须大于 0')

  return Array.from({ length: n }, (_, id) => {
    const u = Math.min(Math.max(random(), Number.EPSILON), 1 - Number.EPSILON)
    return {
      id,
      value: parameters.gamma + parameters.eta * Math.pow(-Math.log(u), 1 / parameters.beta),
      status: 'F' as const,
    }
  })
}

export function getEstimateFailure(result: EstimateCandidate): string | null {
  if (result.beta === null || result.eta === null) return '参数估计未返回完整参数'
  if (result.converged === 'unbounded') return '参数估计无解'
  if (result.converged === false) return '参数估计未收敛'
  return null
}
```

- [ ] **Step 4: Run the focused test and TypeScript check**

Run:

```powershell
npm run test:calculator-state
npx tsc --noEmit
```

Expected: 4 tests pass; TypeScript exits successfully.

- [ ] **Step 5: Commit the primitives**

```powershell
git add -- package.json scripts/tests/calculator-state.test.mjs src/lib/calculator-state.ts
git commit -m "test: define calculator parameter state contract"
```

### Task 2: Restore manual initialization and sample provenance

**Files:**
- Modify: `src/app/page.tsx:7-205`
- Test: `scripts/tests/calculator-state.test.mjs`

- [ ] **Step 1: Add a failing default-card contract test**

Extend `calculator-state.ts` with an exported `createDefaultParameterResult(data, calculatePoints)` contract and first add this test:

```js
import { createDefaultParameterResult } from '../../src/lib/calculator-state.ts'

test('default parameter result is 3P manual-ready and uses current data points', () => {
  const points = [{ x: 1, y: 2, rank: 0.5, t: 3 }]
  const result = createDefaultParameterResult([{ id: 0, value: 1200, status: 'F' }], () => points)
  assert.deepEqual(result, {
    beta: 2,
    eta: 1000,
    gamma: 1000,
    rSquared: null,
    points,
    converged: true,
  })
})
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run `npm run test:calculator-state`.

Expected: FAIL because `createDefaultParameterResult` is not exported.

- [ ] **Step 3: Implement the default-result helper**

Add to `src/lib/calculator-state.ts`:

```ts
export function createDefaultParameterResult<TData, TPoint>(
  data: TData[],
  calculatePoints: (data: TData[], gamma: number) => TPoint[],
) {
  const parameters = getDefaultParameters(true)
  return {
    ...parameters,
    rSquared: null,
    points: calculatePoints(data, parameters.gamma),
    converged: true,
  }
}
```

- [ ] **Step 4: Replace automatic initial estimation with manual defaults**

In `src/app/page.tsx`:

- remove the `calculateWeibullParameters` import;
- import `createDefaultParameterResult`, `generateWeibullSample`, `getDefaultParameters`, `getEstimateFailure`, and `toggleParameterMode`;
- add `last3PGamma?: number` to `CardData`;
- generate the no-case initial sample from `getDefaultParameters(true)`;
- after optional `caseId` loading, create `initialResult` with `createDefaultParameterResult(initialData, calculateMedianRanks)`;
- do not call `calculateWeibull()` during initialization;
- initialize `fitMode: 'manual'`, `is3P: true`, and `last3PGamma: 1000`.

The initialization must have this final shape:

```ts
const defaultParameters = getDefaultParameters(true)
if (initialData.length === 0) {
  initialData = generateWeibullSample(20, defaultParameters)
}
const initialResult = createDefaultParameterResult(initialData, calculateMedianRanks)

setCards([{
  id: '1',
  type: 'chart',
  data: initialData,
  result: initialResult,
  color: CHART_COLORS[0],
  fitMode: 'manual',
  is3P: true,
  last3PGamma: defaultParameters.gamma,
  methodId: selectedMethodId,
}])
```

- [ ] **Step 5: Preserve parameters when samples change**

Update `handleDataSave`, `handleDataSaveMulti`, and `handleDataChange` so they replace sample data and recalculate only plotting points. They must never call `calculateWeibullParameters()` and must retain the current beta/eta/gamma:

```ts
const preserveParametersForData = (card: CardData, nextData: DataPoint[]) => ({
  ...card,
  data: nextData,
  result: card.result
    ? { ...card.result, points: calculateMedianRanks(nextData, card.result.gamma) }
    : createDefaultParameterResult(nextData, calculateMedianRanks),
  fitMode: 'manual' as const,
})
```

For multi-source loading, keep every `DataSource.result` undefined until the user clicks “参数估计”; preserve the card's current parameter result and set `fitMode: 'manual'`.

When adding cards, any branch that previously produced `result: undefined` must receive a default manual result so every card retains a parameter/chart path. Inherited parameter/chart branches continue copying their source result and `last3PGamma`.

- [ ] **Step 6: Run focused and type checks**

Run:

```powershell
npm run test:calculator-state
npx tsc --noEmit
```

Expected: 5 tests pass; TypeScript exits successfully.

- [ ] **Step 7: Commit initialization and sample provenance**

```powershell
git add -- src/lib/calculator-state.ts scripts/tests/calculator-state.test.mjs src/app/page.tsx
git commit -m "fix: restore calculator manual parameter defaults"
```

### Task 3: Enforce mode, reset, and failure-safe estimation

**Files:**
- Modify: `src/app/page.tsx:300-425`
- Modify: `src/components/calculator/AnalysisCard.tsx:315-620`
- Test: `scripts/tests/calculator-state.test.mjs`

- [ ] **Step 1: Add a failing 2P estimation guard test**

Add this helper test before implementation:

```js
import { getEstimationModeFailure } from '../../src/lib/calculator-state.ts'

test('2P mode refuses a 3P-only method calculation', () => {
  assert.equal(getEstimationModeFailure(false), '当前方法仅支持 3P 估计，请切换到 3P')
  assert.equal(getEstimationModeFailure(true), null)
})
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run `npm run test:calculator-state`.

Expected: FAIL because `getEstimationModeFailure` is not exported.

- [ ] **Step 3: Implement the 2P guard helper**

Add to `src/lib/calculator-state.ts`:

```ts
export function getEstimationModeFailure(is3P: boolean): string | null {
  return is3P ? null : '当前方法仅支持 3P 估计，请切换到 3P'
}
```

- [ ] **Step 4: Make 2P/3P and gamma restoration card-local**

In `handleParamsUpdate`, update `last3PGamma` whenever a 3P card receives a finite gamma. In `handleToggle3P`, use `toggleParameterMode()` and recalculate plotting points with the returned gamma:

```ts
const mode = toggleParameterMode({
  is3P: !!card.is3P,
  currentGamma: card.result?.gamma,
  last3PGamma: card.last3PGamma ?? 1000,
})
const result = card.result ?? createDefaultParameterResult(card.data ?? [], calculateMedianRanks)
return {
  ...card,
  is3P: mode.is3P,
  last3PGamma: mode.last3PGamma,
  fitMode: 'manual',
  result: {
    ...result,
    gamma: mode.gamma,
    points: calculateMedianRanks(card.data ?? [], mode.gamma),
  },
}
```

- [ ] **Step 5: Reject 2P estimation and preserve state on all failures**

At the start of `handleCalculate`, call `getEstimationModeFailure(!!card.is3P)`. If it returns a message, `alert(message)` and return without calling the backend.

For a single source, validate the response before `setCards`:

```ts
const { result } = await calculateWeibull({ methodId: card.methodId!, data: card.data })
const failure = getEstimateFailure(result)
if (failure) throw new Error(failure)

setCards(prev => prev.map(current => current.id === cardId ? {
  ...current,
  result,
  fitMode: 'fit',
  last3PGamma: result.gamma,
} : current))
```

The catch path must only show the existing error popup; it must not call `setCards`.

For multiple sources, calculate and validate every source first with `Promise.all`. Only after all succeed, perform one `setCards` update containing all results and the first result as the card result. Any failure must reject the whole operation and preserve the pre-call card state.

- [ ] **Step 6: Reuse sample generation and implement mode-aware reset**

In `AnalysisCard.tsx`, replace the local inverse-transform loop with `generateWeibullSample(simN, { beta, eta, gamma })`.

Replace the reset handler with:

```ts
const handleResetParameters = () => {
  const defaults = getDefaultParameters(is3P)
  const points = data ? calculateMedianRanks(data, defaults.gamma) : []
  onParamsUpdate?.({ ...defaults, points, converged: true }, 'manual')
}
```

Change the button click handler to `handleResetParameters` and its text from `清除参数` to `重置参数`.

- [ ] **Step 7: Run focused tests and TypeScript**

Run:

```powershell
npm run test:calculator-state
npx tsc --noEmit
```

Expected: 6 tests pass; TypeScript exits successfully.

- [ ] **Step 8: Commit interaction behavior**

```powershell
git add -- src/lib/calculator-state.ts scripts/tests/calculator-state.test.mjs src/app/page.tsx src/components/calculator/AnalysisCard.tsx
git commit -m "fix: preserve calculator parameters across estimation failures"
```

### Task 4: Verify the complete regression contract

**Files:**
- Verify only; modify code only if a failing check traces to this scoped repair.

- [ ] **Step 1: Run automated focused and regression checks**

```powershell
npm run test:calculator-state
npm run test:method-status
npm run check:method-status
npx tsc --noEmit
python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py -q
npm run build
git diff --check
```

Expected:

- calculator-state tests all pass;
- 18 method-status tests pass;
- generated cache reports 22 methods and up to date;
- TypeScript passes;
- 17 API/runner tests pass;
- production build succeeds;
- diff check is clean.

- [ ] **Step 2: Verify the backend-unavailable browser path**

With port 8001 stopped and the frontend on port 3000, open `/` and confirm:

- MDM remains the selected enabled method;
- the card opens in 3P with `2/1000/1000`;
- PDF/CDF image renders from those parameters;
- “生成样本” changes the sample using the current parameters;
- “参数估计” shows an error but parameters, image, and sample remain unchanged;
- 3P → 2P sets gamma to 0; 2P → 3P restores the previous gamma;
- 2P “参数估计” shows the 3P-only message without a network request;
- “重置参数” restores the approved defaults for the active mode.

- [ ] **Step 3: Verify a successful 3P estimate**

Run the backend on port 8001, reload `/`, click “参数估计”, and confirm:

- the verified MDM response replaces the parameter values;
- the image follows the returned parameters;
- the response method remains MDM;
- no local MLE or WMLE fallback appears.

- [ ] **Step 4: Audit scope and protected files**

```powershell
git status --short
git diff --name-only 941c6be..HEAD
```

Expected: implementation commits contain only the plan/spec, focused calculator files, test file, and package script. `Study/01`, `docs/history/260717.md`, and untracked Stage C reviews remain untouched.

- [ ] **Step 5: Record final verification commit only if verification changed documentation**

If no file changed during verification, do not create an empty commit. If the implementation plan checklist is updated with exact results, stage only this plan and commit:

```powershell
git add -- docs/superpowers/plans/2026-07-17-calculator-bidirectional-parameters.md
git commit -m "docs: record calculator regression verification"
```

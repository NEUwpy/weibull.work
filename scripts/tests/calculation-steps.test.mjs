import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { calculationSteps } from '../../src/lib/calculation-steps.ts'

test('calculation stages reference existing scientific stages of each program flow', () => {
  assert.deepEqual(Object.keys(calculationSteps).sort(), ['lse','lre','mdm','mle','mm','mmle','wmle'].sort())
  for (const [method, steps] of Object.entries(calculationSteps)) {
    const flow = JSON.parse(fs.readFileSync(new URL(`../../src/data/method_flows/${method}.json`, import.meta.url), 'utf8'))
    assert.ok(steps.length >= 2 && steps.length <= 3, method)
    for (const step of steps) {
      assert.ok(step.programSteps.length > 0, `${method}: ${step.label}`)
      for (const id of step.programSteps) {
        const source = flow.steps.find(item => item.id === id)
        assert.ok(source?.sources?.length, `${method}: ${step.label} -> ${id}`)
      }
    }
  }
})

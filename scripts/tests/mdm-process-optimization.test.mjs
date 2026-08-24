import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildMdmOptimizationDetailsHref,
  isMdmAiSampleSizeSupported,
  MDM_AI_SUPPORTED_SAMPLE_SIZES,
  parseMdmOffsetMode,
} from '../../src/lib/mdm-process-optimization-contract.ts'


test('MDM AI process optimization supports only the sealed sample sizes', () => {
  assert.deepEqual([...MDM_AI_SUPPORTED_SAMPLE_SIZES], [7, 10, 15, 20])
  assert.equal(isMdmAiSampleSizeSupported(7), true)
  assert.equal(isMdmAiSampleSizeSupported(20), true)
  assert.equal(isMdmAiSampleSizeSupported(5), false)
  assert.equal(isMdmAiSampleSizeSupported(12), false)
})

test('MDM offset mode uses fixed as the safe default', () => {
  assert.equal(parseMdmOffsetMode('ai'), 'ai')
  assert.equal(parseMdmOffsetMode('fixed'), 'fixed')
  assert.equal(parseMdmOffsetMode('legacy'), 'fixed')
  assert.equal(parseMdmOffsetMode(null), 'fixed')
})

test('MDM optimization details URL carries the current sample', () => {
  const href = buildMdmOptimizationDetailsHref([1.25, 2.5, 3.75])
  assert.equal(href, '/ai/process-optimization/mdm?data=1.25%2C2.5%2C3.75')
})

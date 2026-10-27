import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildMdmOptimizationDetailsHref,
  compareMdmOptimization,
  formatSigned,
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

test('MDM comparison reports signed loss and opposite-direction predicted accuracy change', () => {
  assert.deepEqual(
    compareMdmOptimization({
      selected_predicted_loss: 0.45,
      default_predicted_loss: 0.5,
    }),
    {
      lossDifference: -0.04999999999999999,
      predictedAccuracyChangePercent: 9.999999999999998,
    },
  )

  const worse = compareMdmOptimization({
    selected_predicted_loss: 0.55,
    default_predicted_loss: 0.5,
  })
  assert.ok(worse.lossDifference > 0)
  assert.ok(worse.predictedAccuracyChangePercent < 0)
})

test('signed formatting always exposes the comparison direction', () => {
  assert.equal(formatSigned(1.234, 2), '+1.23')
  assert.equal(formatSigned(-1.234, 2), '-1.23')
  assert.equal(formatSigned(0, 2, '%'), '+0.00%')
  assert.equal(formatSigned(-0.0001, 2), '+0.00')
})

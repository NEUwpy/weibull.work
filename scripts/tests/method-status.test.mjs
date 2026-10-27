import test from 'node:test'
import assert from 'node:assert/strict'

import {
  deriveMethodCapability,
  flattenLeafIds,
  validateStatusDocument,
} from '../lib/method-status.mjs'

function completeItem(evidence) {
  return { status: 'done', evidence: [...evidence] }
}

function completeMethod(id) {
  return {
    id,
    name: '最小差异法',
    family: 'min_adequacy',
    classification_source: 'src/content/181-004-pdf原文.md',
    shared_core: null,
    paper: {
      status: 'done',
      title: '基于统计最小差异原理的威布尔分布参数估计方法',
      publication: '东北大学学报（自然科学版）',
      year: 2025,
      stable_id: '1005-3026(2025)07-0108-06',
      evidence: ['src/content/182-046-pdf原文.md'],
    },
    layer1: {
      backend: completeItem(['python/methods/mdm.py']),
      tests: completeItem(['python/tests/test_runner.py']),
      calculator: completeItem(['src/hooks/useWeibullCalculation.ts']),
      theory: completeItem(['src/content/algorithms/mdm.md']),
      process: completeItem(['src/data/method_flows/mdm.json']),
    },
    layer2: {
      calculation: completeItem(['src/components/methods/mdm']),
      analysis: completeItem(['src/components/methods/mdm']),
    },
    layer3: {
      applicability: completeItem(['public/studies/mdm']),
      verification: completeItem(['public/case-studies/mdm']),
    },
  }
}

function statusDoc(methods) {
  return {
    schema_version: 1,
    methods,
  }
}

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

test('incomplete first layer keeps calculator closed even when later layers are done', () => {
  const method = completeMethod('mdm')
  method.layer1.theory.status = 'todo'
  method.layer1.theory.evidence = []
  const capability = deriveMethodCapability(method)
  assert.equal(capability.level, 'layer1_in_progress')
  assert.equal(capability.calculatorEnabled, false)
  assert.deepEqual(capability.missingLayer1, ['theory'])
})

test('paper gap blocks first layer completion', () => {
  const method = completeMethod('mdm')
  method.paper = {
    status: 'blocked',
    reason: 'PAPER_NEEDED：缺少专项论文',
    evidence: [],
  }
  const capability = deriveMethodCapability(method)
  assert.equal(capability.level, 'layer1_in_progress')
  assert.equal(capability.calculatorEnabled, false)
  assert.deepEqual(capability.missingLayer1, ['paper'])
})

test('maturity cannot skip an unfinished earlier layer', () => {
  const method = completeMethod('mdm')
  method.layer2.calculation.status = 'in_progress'
  const capability = deriveMethodCapability(method)
  assert.equal(capability.level, 'layer1_complete')
  assert.equal(capability.calculatorEnabled, true)
})

test('layer two completion without layer three yields layer2_complete', () => {
  const method = completeMethod('mdm')
  method.layer3.verification.status = 'in_progress'
  const capability = deriveMethodCapability(method)
  assert.equal(capability.level, 'layer2_complete')
  assert.equal(capability.calculatorEnabled, true)
})

test('untouched method derives not_started', () => {
  const method = completeMethod('mdm')
  method.paper = { status: 'todo', evidence: [] }
  for (const key of Object.keys(method.layer1)) {
    method.layer1[key] = { status: 'todo', evidence: [] }
  }
  for (const key of Object.keys(method.layer2)) {
    method.layer2[key] = { status: 'todo', evidence: [] }
  }
  for (const key of Object.keys(method.layer3)) {
    method.layer3[key] = { status: 'todo', evidence: [] }
  }
  const capability = deriveMethodCapability(method)
  assert.equal(capability.level, 'not_started')
  assert.equal(capability.calculatorEnabled, false)
})

test('unknown status value is rejected', () => {
  const method = completeMethod('mdm')
  method.layer1.backend.status = 'finished'
  assert.throws(
    () => validateStatusDocument(statusDoc([method]), ['mdm']),
    /status/i,
  )
})

test('duplicate method ids are rejected', () => {
  assert.throws(
    () => validateStatusDocument(
      statusDoc([completeMethod('mdm'), completeMethod('mdm')]),
      ['mdm'],
    ),
    /method id/i,
  )
})

test('completed paper requires citation metadata', () => {
  const method = completeMethod('mdm')
  delete method.paper.stable_id
  assert.throws(
    () => validateStatusDocument(statusDoc([method]), ['mdm']),
    /paper/i,
  )
})

test('not_applicable on a mandatory item requires approved exception', () => {
  const method = completeMethod('mdm')
  method.layer1.process = { status: 'not_applicable', evidence: [] }
  assert.throws(
    () => validateStatusDocument(statusDoc([method]), ['mdm']),
    /not_applicable/i,
  )
  method.layer1.process = {
    status: 'not_applicable',
    evidence: [],
    exception_approved: true,
    reason: '经 Codex 审核的例外',
  }
  assert.doesNotThrow(
    () => validateStatusDocument(statusDoc([method]), ['mdm']),
  )
})

test('evidence path must not escape the repository root', () => {
  const method = completeMethod('mdm')
  method.layer1.backend.evidence = ['..']
  assert.throws(
    () =>
      validateStatusDocument(statusDoc([method]), ['mdm'], {
        checkEvidencePaths: true,
        rootDir: process.cwd(),
      }),
    /escapes/,
  )
  method.layer1.backend.evidence = ['../outside']
  assert.throws(
    () =>
      validateStatusDocument(statusDoc([method]), ['mdm'], {
        checkEvidencePaths: true,
        rootDir: process.cwd(),
      }),
    /escapes/,
  )
})

test('duplicate leaf ids in methods catalog are rejected', () => {
  assert.throws(
    () =>
      flattenLeafIds([
        {
          id: 'max_adequacy',
          name: '极大化适配法',
          children: [
            { id: 'mle', name: '极大似然估计' },
            { id: 'mle', name: '极大似然估计' },
          ],
        },
      ]),
    /duplicate leaf id/i,
  )
})

test('name in status document must match methods catalog', () => {
  const method = completeMethod('mdm')
  method.name = '最小二乘估计'
  assert.throws(
    () =>
      validateStatusDocument(statusDoc([method]), ['mdm'], {
        catalogLeaves: [{ id: 'mdm', name: '最小差异法', family: 'min_adequacy' }],
      }),
    /name.*does not match.*最小差异法/i,
  )
})

test('family in status document must match methods catalog', () => {
  const method = completeMethod('mdm')
  method.family = 'max_adequacy'
  assert.throws(
    () =>
      validateStatusDocument(statusDoc([method]), ['mdm'], {
        catalogLeaves: [{ id: 'mdm', name: '最小差异法', family: 'min_adequacy' }],
      }),
    /family.*does not match.*min_adequacy/i,
  )
})

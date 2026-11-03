import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import { loadMethodFlow } from '../../src/lib/server/method-flow.mjs'

test('each method has one live implementation and one corresponding process document', () => {
  for (const method of ['mdm', 'wmle', 'mm']) {
    const flow = loadMethodFlow(method)
    assert.equal(flow.methodId, method)
    assert.ok(flow.sources.some(source => source.path === `python/methods/${method}.py`))
    assert.ok(flow.sources.every(source => !source.path.endsWith('_paper.py')))
    assert.equal(fs.existsSync(`python/methods/${method}_paper.py`), false)
    assert.equal(fs.existsSync(`src/data/method_flows/${method}_paper.json`), false)
  }
})

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { createHash } from 'node:crypto'
import katex from 'katex'
import { loadMethodFlow, validateCompletedMethodFlows } from '../../src/lib/server/method-flow.mjs'

const methods = ['mle', 'wmle', 'mdm', 'lse', 'lre', 'mm', 'mmle']
const required = {
  mle: ['_shape', 'mle_profile', 'solve_mle_profile', 'solve_mle_profile.add', 'WeibullBase._calculate_r2'],
  wmle: ['get_weight_j1', 'get_weight_j2', 'get_weight_j3', '_load_j3_table', '_shape', 'wmle_profile', 'wmle_residuals', 'solve_wmle_profile.add', 'wmle_objective_profile'],
  mdm: ['MDM.run.find_best_beta_for_gamma', 'MDM.run.profile_gradient', 'MDM.run.find_right_anchor', 'MDM.run.fit_right_edge_root'],
  lse: ['_log_weibull_order_stat_mean', 'log_weibull_order_stat_means', 'LSE.run.profile_f', 'WeibullBase._calculate_r2'],
  lre: ['LRE.run.negative_correlation'],
  mm: ['sample_weibull_moment', 'solve_from_weibull_moments', 'WeibullBase._calculate_r2'],
  mmle: ['MMLE.run'],
}

test('all maintained flows resolve core helpers, original lines and current source hashes', () => {
  for (const id of methods) {
    const flow = loadMethodFlow(id)
    const symbols = new Set(flow.steps.flatMap(step => step.sources.map(ref => ref.symbol)))
    for (const symbol of required[id]) assert.ok(symbols.has(symbol), `${id}: hidden core helper ${symbol}`)
    for (const source of flow.sources) {
      const bytes = fs.readFileSync(source.path)
      assert.equal(source.sha256, createHash('sha256').update(bytes).digest('hex'))
      assert.deepEqual(source.lines, bytes.toString('utf8').split(/\r?\n/))
    }
    for (const step of flow.steps) for (const ref of step.sources) {
      const source = flow.sources.find(item => item.path === ref.file)
      assert.ok(ref.start >= 0 && ref.end <= source.lines.length && ref.end > ref.start)
    }
    assert.equal('code' in flow, false)
    for (const artifact of flow.artifacts) assert.equal(artifact.sha256, createHash('sha256').update(fs.readFileSync(artifact.path)).digest('hex'))
  }
})

test('every formula, symbol and variable mapping renders, without accidental escaped control characters', () => {
  for (const id of methods) for (const step of loadMethodFlow(id).steps) {
    const expressions = [step.formula.expression, ...step.formula.symbols.map(v => v.symbol), ...step.inputs.map(v => v.symbol), ...step.outputs.map(v => v.symbol)]
    for (const expression of expressions) {
      assert.doesNotMatch(expression, /[\x00-\x08\x0b\x0c\x0e-\x1f]/, `${id} ${step.id}`)
      assert.doesNotThrow(() => katex.renderToString(expression, { throwOnError: true, strict: false }), `${id} ${step.id}: ${expression}`)
    }
  }
})

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-flow-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  fs.mkdirSync(path.join(root, 'python/methods'), { recursive: true })
  fs.mkdirSync(path.join(root, 'src/data/method_flows'), { recursive: true })
  const file = path.join(root, 'python/methods/example.py')
  fs.writeFileSync(file, 'class Example:\n    def run(self,\n            trace=False):\n        """A function.\nThis unindented docstring is not a new scope.\n        """\n        # begin\n        value = 1\n        # stop\n        return value\n\ndef other():\n    return 99\n')
  const config = { schemaVersion: 2, methodId: 'example', methodName: 'Example', description: 'Example flow', steps: [{
    id: 1, name: 'Read', description: 'Read value', basis: 'Example implementation', notes: '',
    formula: { expression: 'x=1', explanation: 'A value', symbols: [{ symbol: 'x', meaning: 'value' }] },
    inputs: [{ code: 'self', symbol: 'S', meaning: 'sample' }], outputs: [{ code: 'value', symbol: 'x', meaning: 'value' }],
    sources: [{ file: 'python/methods/example.py', symbol: 'Example.run', label: 'Run' }],
  }] }
  const write = () => fs.writeFileSync(path.join(root, 'src/data/method_flows/example.json'), JSON.stringify(config))
  write()
  return { root, file, config, write }
}

test('multiline Python signatures and docstrings stay in scope; current edits update lines and hash', t => {
  const { root, file } = fixture(t)
  const before = loadMethodFlow('example', { root })
  assert.deepEqual(before.steps[0].sources.map(({ start, end }) => [start, end]), [[1, 10]])
  fs.writeFileSync(file, '\n\n' + fs.readFileSync(file, 'utf8').replace('value = 1', 'value = 2'))
  const after = loadMethodFlow('example', { root })
  assert.equal(after.steps[0].sources[0].start, 3)
  assert.notEqual(after.sources[0].sha256, before.sources[0].sha256)
  assert.ok(after.sources[0].lines.includes('        value = 2'))
})

test('bad source ranges fail closed instead of returning a copied or unrelated program', t => {
  const { root, file, config, write } = fixture(t)
  const step = config.steps[0], ref = step.sources[0]
  for (const symbol of ['Missing.run', 'Example.missing']) {
    ref.symbol = symbol; write()
    assert.throws(() => loadMethodFlow('example', { root }), /未唯一定位/)
  }
  ref.symbol = 'Example.run'
  ref.from = 'missing anchor'; write()
  assert.throws(() => loadMethodFlow('example', { root }), /锚点未唯一匹配/)
  ref.from = 'value'; write()
  assert.throws(() => loadMethodFlow('example', { root }), /锚点未唯一匹配/)
  ref.from = '# begin'; ref.until = 'value = 1'; write()
  assert.throws(() => loadMethodFlow('example', { root }), /只有说明/)
  delete ref.from; delete ref.until
  ref.file = '../secret.py'; write()
  assert.throws(() => loadMethodFlow('example', { root }), /不在允许范围/)
  ref.file = 'python/methods/example.py'; step.code = ['fake']; write()
  assert.throws(() => loadMethodFlow('example', { root }), /代码副本/)
  delete step.code; config.steps = []; write()
  assert.throws(() => loadMethodFlow('example', { root }), /步骤不完整/)
  config.steps = [step]; write()
  fs.writeFileSync(file, 'class Example:\n    def run(self,\n            trace=False):\n        """Only documentation."""\n        # no implementation\n        pass\n')
  assert.throws(() => loadMethodFlow('example', { root }), /只有说明/)
  assert.equal(loadMethodFlow('../example', { root }), null)
  assert.equal(loadMethodFlow('unknown', { root }), null)
})

test('done process status cannot point at a missing or invalid flow', t => {
  const { root } = fixture(t)
  const method = id => ({ id, layer1: { process: { status: 'done' } } })
  assert.doesNotThrow(() => validateCompletedMethodFlows([method('example')], root))
  assert.throws(() => validateCompletedMethodFlows([method('missing')], root), /缺少说明配置/)
})

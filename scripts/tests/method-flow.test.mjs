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
  for (const id of methods) {
    const flow = loadMethodFlow(id)
    const diagramMath = items => items.flatMap(item => item.kind === 'group' ? diagramMath(item.children)
      : item.kind === 'port' ? [item.label] : typeof item.symbol === 'string' ? [item.symbol] : Object.values(item.symbol ?? {}))
    for (const expression of diagramMath(flow.workflow.items)) {
      assert.doesNotMatch(expression, /[\x00-\x08\x0b\x0c\x0e-\x1f]/, id)
      assert.doesNotThrow(() => katex.renderToString(expression, { throwOnError: true, strict: false }), id + ': ' + expression)
    }
    for (const step of flow.steps) {
    const expressions = [...step.formula.equations,
      ...Object.values(step.formula.variantEquations ?? {}).flat(), ...step.formula.symbols.map(v => v.symbol),
      ...step.inputs.map(v => v.symbol), ...step.outputs.map(v => v.symbol)]
    for (const expression of expressions) {
      assert.doesNotMatch(expression, /[\x00-\x08\x0b\x0c\x0e-\x1f]/, `${id} ${step.id}`)
      assert.doesNotThrow(() => katex.renderToString(expression, { throwOnError: true, strict: false }), `${id} ${step.id}: ${expression}`)
    }
    }
  }
})

test('calculation stages retain the real source sequence and helper implementations', () => {
  for (const id of methods) {
    const flow = loadMethodFlow(id)
    assert.ok(flow.workflow)
    const modules = items => items.flatMap(item => item.kind === 'group'
      ? item.layout === 'module' ? [item] : modules(item.children) : [])
    assert.equal(modules(flow.workflow.items).length, flow.steps.length, `${id}: every stage uses the shared module structure`)
    assert.equal(new Set(Object.values(flow.workflow.targets)).size, flow.steps.length)
    flow.steps.forEach((step, index) => {
      assert.ok(step.sources.length >= 1)
      assert.equal(step.id, index + 1, `${id}: main navigation should stay a simple step list`)
    })
  }
  const mle = loadMethodFlow('mle').steps.flatMap(s => s.sources)
  const position = symbol => mle.findIndex(s => s.symbol === symbol)
  assert.ok(position('solve_mle_profile') < position('_distances'))
  assert.ok(position('_distances') < position('_shape'))
  assert.ok(position('_shape') < mle.map(s => s.symbol).lastIndexOf('mle_profile'))
  const mdmFlow = loadMethodFlow('mdm')
  assert.deepEqual(mdmFlow.steps.map(step => step.name), [
    '准备样本', '试算各位置的最小差异', '按梯度偏移求位置', '回代位置求形状', '反算尺度', '汇总结果',
  ])
  assert.deepEqual(mdmFlow.workflow.targets, { samples: 1, trial: 2, location: 3, shape: 4, scale: 5, result: 6 })
  const mdm = mdmFlow.steps.flatMap(s => s.sources)
  const gridIndex = mdm.findIndex(s => s.symbol === '_build_geometric_gamma_grid')
  const stdIndex = mdm.findIndex(s => s.symbol === 'MDM.run.calculate_eta_std')
  assert.ok(gridIndex < stdIndex, 'explain pseudo-scale evaluation when called, not when defined')
})

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-flow-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  fs.mkdirSync(path.join(root, 'python/methods'), { recursive: true })
  const file = path.join(root, 'python/methods/example.py')
  let source = 'class Example:\n    def run(self,\n            trace=False):\n        """A function.\nThis unindented docstring is not a new scope.\n        """\n        # begin\n        value = 1\n        # stop\n        return value\n\ndef other():\n    return 99\n'
  const config = { schemaVersion: 2, methodId: 'example', methodName: 'Example', description: 'Example flow', variables: {
    sample: { code: 'self', symbol: 'S', name: '样本', meaning: 'sample' },
    value: { code: 'value', symbol: 'x', name: '中间量', meaning: 'value' },
    result: { code: 'result', symbol: 'y', name: '结果', meaning: 'result' },
  }, steps: [{
    id: 1, name: 'Read', description: 'Read value', basis: 'Example implementation', notes: '',
    formula: { equations: ['x=1'], explanation: 'A value', symbols: [{ symbol: 'x', meaning: 'value' }] },
    inputs: ['sample'], outputs: ['value'],
    portGroups: { input: { name: '样本', refs: ['sample'] }, output: { name: '中间量', refs: ['value'] } },
    sources: [{ file: 'python/methods/example.py', symbol: 'Example.run', label: 'Run' }],
  }] }
  const write = (nextSource = source, workflow = {
    title: 'Flow', description: 'Example flow', targets: {}, connections: [],
    items: config.steps.map(step => ({ kind: 'step', step: step.id, anchor: 'step-' + step.id })),
  }) => {
    source = nextSource
    fs.writeFileSync(file, source + '\n# @method-flow\n# ' + JSON.stringify({ ...config, workflow }) + '\n# @end-method-flow\n')
  }
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
  write('class Example:\n    def run(self,\n            trace=False):\n        """Only documentation."""\n        # no implementation\n        pass\n')
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

test('one calculation stage can contain multiple real source blocks without splitting navigation', t => {
  const { root, config, write } = fixture(t)
  config.steps[0].sources.push({ file: 'python/methods/example.py', symbol: 'other', label: 'Helper' })
  write()
  const flow = loadMethodFlow('example', { root })
  assert.equal(flow.steps.length, 1)
  assert.equal(flow.steps[0].sources.length, 2)
  assert.equal(flow.sources.length, 1)
  assert.deepEqual(flow.steps[0].sources.map(s => s.symbol), ['Example.run', 'other'])
})

test('missing source ranges and conflicts between graph targets and steps are rejected', t => {
  const { root, config, write } = fixture(t)
  const step = config.steps[0]
  const source = step.sources.pop(); write()
  assert.throws(() => loadMethodFlow('example', { root }), /缺少真实源码引用/)
  step.sources.push(source)
  config.steps.push({ ...step, id: 2 })
  write(undefined, { title: 'Flow', description: 'Example flow', targets: { result: 2 }, connections: [],
    items: [{ kind: 'step', step: 1, anchor: 'step-1', target: 'result' }, { kind: 'step', step: 2, anchor: 'step-2' }],
  })
  assert.throws(() => loadMethodFlow('example', { root }), /节点步骤无效/)
})

test('after anchor locates a continuation within its real function scope', t => {
  const { root, config, write } = fixture(t)
  config.steps[0].sources[0].after = 'value = 1'
  config.steps[0].sources[0].from = 'return value'
  write()
  const ref = loadMethodFlow('example', { root }).steps[0].sources[0]
  assert.equal(ref.start, 9)
  assert.equal(ref.end, 10)
})

test('module attachments belong to their stage; transfers must connect an output to the next input', t => {
  const { root, config, write } = fixture(t)
  config.steps.push({ ...config.steps[0], id: 2, inputs: ['value'], outputs: ['result'],
    portGroups: { input: { name: '中间量', refs: ['value'] }, output: { name: '结果', refs: ['result'] } } })
  const connections = [{ from: 'value', to: 'next-input' }]
  const workflow = { title: 'Flow', description: 'Two connected stages', targets: { samples: 1, result: 2 }, connections,
    items: [
      { kind: 'group', layout: 'module', children: [
        { kind: 'port', anchor: 'sample', direction: 'input', target: 'samples', group: 'input', external: true },
        { kind: 'step', anchor: 'step-1', step: 1 },
        { kind: 'port', anchor: 'value', direction: 'output', target: 'samples', group: 'output' },
      ] },
      { kind: 'group', layout: 'module', children: [
        { kind: 'port', anchor: 'next-input', direction: 'input', target: 'result', group: 'input' },
        { kind: 'step', anchor: 'step-2', step: 2 },
        { kind: 'port', anchor: 'result', direction: 'output', target: 'result', group: 'output' },
      ] },
    ] }
  write(undefined, workflow)
  assert.doesNotThrow(() => loadMethodFlow('example', { root }))
  write(undefined, { ...workflow, connections: [] })
  assert.throws(() => loadMethodFlow('example', { root }), /输入端口缺少来源连线/)
  write(undefined, { ...workflow, connections: [{ from: 'step-1', to: 'value' }, ...connections] })
  assert.throws(() => loadMethodFlow('example', { root }), /模块间连线/)
  workflow.items[1].children.pop()
  write(undefined, workflow)
  assert.throws(() => loadMethodFlow('example', { root }), /须包含一个计算框和输入输出端口/)
})

test('all flow summaries reference the same quantities shown in their stage details', () => {
  for (const id of methods) {
    const flow = loadMethodFlow(id)
    function visit(items) {
      for (const item of items) {
        if (item.kind === 'group') { visit(item.children); continue }
        if (item.kind !== 'port') continue
        const step = flow.steps.find(step => step.id === flow.workflow.targets[item.target])
        const fields = item.direction === 'input' ? [...step.inputs, ...step.extraInputs] : [...step.outputs, ...step.extraOutputs]
        for (const ref of item.refs) {
          const field = fields.find(field => field.id === ref)
          assert.ok(field, `${id} step ${step.id}: summary lost ${ref}`)
          assert.equal(field, flow.variables[ref], `${id}: independent variable copy`)
          assert.ok(item.label.includes(field.symbol), `${id}: summary symbol differs`)
        }
      }
    }
    visit(flow.workflow.items)
  }
})

test('undefined quantities and chart bindings fail instead of creating another input/output list', t => {
  const { root, config, write } = fixture(t)
  config.steps[0].inputs = ['missing']; write()
  assert.throws(() => loadMethodFlow('example', { root }), /未知变量引用/)
  config.steps[0].inputs = ['sample']
  config.chartBindings = { curve: { x: 'sample', y: 'missing' } }; write()
  assert.throws(() => loadMethodFlow('example', { root }), /图像变量未定义/)
})

test('flow ports remain a key-quantity summary rather than duplicating every detail field', () => {
  const flow = loadMethodFlow('mdm')
  const step = flow.steps[0]
  assert.ok(step.outputs.some(field => field.id === 'ranks'))
  const module = flow.workflow.items[0]
  const output = module.children.find(item => item.kind === 'port' && item.direction === 'output')
  assert.deepEqual(output.refs, ['ordered', 'rank_transform'])
  assert.equal(output.refs.includes('ranks'), false)
})

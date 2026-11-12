import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import vm from 'node:vm'
import { createHash } from 'node:crypto'
import { createRequire } from 'node:module'
import ts from 'typescript'
import { legacyProcessHref, methodHref, methodTabFromPath } from '../../src/lib/method-navigation.ts'
import { workbookMatches, formatWorkbookCell } from '../../src/lib/monte-carlo.ts'
import { loadMethodFlow } from '../../src/lib/server/method-flow.mjs'
const require = createRequire(import.meta.url)
const sha = bytes => createHash('sha256').update(bytes).digest('hex')

test('independent method URLs retain the function, batch, sample and calculation deep links', () => {
  const query = new URLSearchParams({ batch: 'r00-test', n: '15', sample: '23', view: 'samples', data: '4,5,6', offset: '0.1' })
  for (const [section, tab] of [['calculation', 'lab'], ['analysis', 'analysis'], ['applicability', 'examples'], ['verification', 'cases'], ['compare', 'compare']]) {
    assert.equal(methodTabFromPath('/methods/mdm/' + section), tab)
    assert.equal(methodHref('mle', tab, query), '/methods/mle/' + section + '?' + query)
  }
  assert.equal(methodHref('mdm', null), '/methods/mdm')
  assert.equal(methodTabFromPath('/methods/mdm/process'), 'lab')
  query.set('step', '3')
  const redirected = new URL(legacyProcessHref('mdm', query), 'http://localhost')
  assert.equal(redirected.pathname, '/methods/mdm/calculation')
  assert.deepEqual([...redirected.searchParams], [...query].map(([key, value]) => [key === 'step' ? 'sourceStep' : key, value]))
  assert.equal(legacyProcessHref('mdm', new URLSearchParams()), '/methods/mdm/calculation?sourceStep=1')
})
test('linked choices require the other two parameters, sample size, method and available data to match', () => {
  const card = { truth: [2, 1000, 500], ns: [7, 15, 30], methods: ['mdm', 'mle'] }
  assert.equal(workbookMatches(card, [2, 1000, 500], 15, 'mle'), true)
  for (const [truth, n, method] of [[[3, 1000, 500], 15, 'mle'], [[2, 100, 500], 15, 'mle'], [[2, 1000, 1000], 15, 'mle'], [[2, 1000, 500], 10, 'mle'], [[2, 1000, 500], 15, 'lre']]) assert.equal(workbookMatches(card, truth, n, method), false)
  assert.equal(workbookMatches({ ...card, available: false }, card.truth, 7, 'mle'), false)
  assert.equal(formatWorkbookCell('—'), '—')
  assert.equal(formatWorkbookCell(null), '')
  assert.equal(formatWorkbookCell(1.23456789, '0.000000'), '1.234568')
})

function fixture(run) {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-workbook-test-'))
  const data = path.join(workspace, 'data'), root = path.join(data, 'monte-carlo', 'fixture')
  fs.mkdirSync(root, { recursive: true })
  const raw = Buffer.from('original workbook bytes'), code = Buffer.from('frozen code'), book = Buffer.from(JSON.stringify({ schemaVersion: 1, id: 'fixture', sha256: sha(raw), groups: {}, sheets: [], source: {} }))
  const manifest = { schemaVersion: 1, id: 'fixture', protocol: 'frozen', configuration: { seed_namespace_original: 42 }, files: {} }
  function write(relative, bytes, role) { fs.mkdirSync(path.dirname(path.join(root, relative)), { recursive: true }); fs.writeFileSync(path.join(root, relative), bytes); if (role) manifest.files[relative] = { sha256: sha(bytes), bytes: bytes.length, role } }
  write('workbook.xlsx', raw, 'workbook'); write('workbook.json', book, 'view'); write('source/method.py', code, 'code'); write('private-input.json', Buffer.from('{}'), 'input')
  const entry = { id: 'fixture', truth: [2, 1000, 500], ns: [7], methods: ['mdm'], offsets: [.1], directory: 'monte-carlo/fixture', workbookSha256: sha(raw), filename: 'fixture.xlsx' }
  function seal() { const bytes = Buffer.from(JSON.stringify(manifest)); write('manifest.json', bytes); entry.manifestSha256 = sha(bytes) }
  seal()
  const index = { entries: [entry] }, modules = new Map()
  function load(file) {
    file = path.resolve(file)
    if (modules.has(file)) return modules.get(file).exports
    const module = { exports: {} }; modules.set(file, module)
    const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText
    const localRequire = name => {
      if (name === '@/content/monte-carlo/research00.json') return index
      if (name === './method-flow.mjs') return { loadMethodFlow }
      return name.startsWith('.') ? load(path.resolve(path.dirname(file), name + '.ts')) : require(name)
    }
    const context = vm.createContext({ process: { env: { WEIBULL_DATA_ROOT: data }, cwd: () => process.cwd() }, console, Buffer })
    vm.runInContext('(function(require,module,exports){' + compiled + '\n})', context, { filename: file })(localRequire, module, module.exports)
    return module.exports
  }
  try { return run({ root, workspace, raw, code, entry, manifest, write, seal, api: load('src/lib/server/monte-carlo.ts') }) }
  finally { assert.ok(path.basename(workspace).startsWith('weibull-workbook-test-')); fs.rmSync(workspace, { recursive: true, force: true }) }
}
test('registered data uses an external manifest, retains source identity, and exports original bytes', () => fixture(({ api, raw, code }) => {
  assert.equal(api.workbookCatalog()[0].available, true)
  assert.equal(api.registeredWorkbook('fixture').source.configuration.seed_namespace_original, 42)
  assert.deepEqual(api.registeredWorkbookFile('fixture').bytes, raw)
  assert.deepEqual(api.registeredWorkbookFile('fixture', 'source/method.py').bytes, code)
  for (const name of ['private-input.json', '../outside.py', 'source/../../outside.py', 'workbook.json']) assert.equal(api.registeredWorkbookFile('fixture', name), null)
  assert.equal(api.registeredWorkbook('../fixture'), null)
}))
test('changed workbook, view or provenance identities fail explicitly without a fallback', () => fixture(({ api, write }) => {
  write('workbook.xlsx', Buffer.from('changed'))
  assert.throws(() => api.registeredWorkbookFile('fixture'), /身份已变化/)
  write('workbook.json', Buffer.from('{}'))
  assert.throws(() => api.registeredWorkbook('fixture'), /身份已变化/)
  write('manifest.json', Buffer.from('{}'))
  assert.equal(api.workbookCatalog()[0].available, false)
  assert.throws(() => api.registeredWorkbook('fixture'), /哈希已变化/)
}))
test('registered code cannot escape the monte-carlo namespace through a link', () => fixture(({ api, root, workspace, manifest, seal }) => {
  const privateDir = path.join(workspace, 'private'); fs.mkdirSync(privateDir); fs.writeFileSync(path.join(privateDir, 'secret.py'), 'private')
  fs.symlinkSync(privateDir, path.join(root, 'link'), process.platform === 'win32' ? 'junction' : 'dir')
  manifest.files['link/secret.py'] = { sha256: sha(Buffer.from('private')), bytes: 7, role: 'code' }; seal()
  assert.throws(() => api.registeredWorkbookFile('fixture', 'link/secret.py'), /文件缺失/)
}))

function archivedProcessFixture(run) {
  return fixture(context => {
    const { entry, write, seal, raw } = context
    entry.mdmProcess = { n: 3, delta: .1, records: 'source/estimates.jsonl', source: 'source/mdm.py', base: 'source/base.py',
      replay: { path: 'fixture/replay.json' } }
    const book = {
      schemaVersion: 1, id: 'fixture', sha256: sha(raw), title: 'W(2,1000,500)', truth: [2, 1000, 500], sheets: [], source: {},
      groups: { 3: {
        samples: [[1, 510, 530, 600], [2, 515, 540, 610]],
        resultRows: [[1, 2, 1000, 500], [2, 2.1, 1010, 501]],
        blocks: [{ method: 'mdm', delta: .1, column: 1 }],
      } },
    }
    const records = book.groups[3].resultRows.map(([id, beta_hat, eta_hat, gamma_hat]) => ({
      id, n: 3, delta: .1, method_id: 'mdm', beta_hat, eta_hat, gamma_hat, r_squared: .95, converged: true,
      criterion_curve: [{ gamma: 0, gradient: -.01 }, { gamma: 509, gradient: .2 }],
      extra: { solution_info: { root_solver: 'brent', target_offset: .1, optimal_gamma: gamma_hat,
        root_bracket: { left: { gamma: 0 }, right: { gamma: 509 } } } },
    }))
    const source = Buffer.from(String.raw`class MDM:
    def run(self):
        # @step: 1 | 排序
        t = self.data
        # @step: 2 | 秩
        ranks = self._median_ranks()
        # @step: 3 | 计算标准差
        def calculate_eta_std(beta, gamma, t):
            return 5
        # @step: 4 | 搜索
        def find_best_beta_for_gamma(gamma):
            return beta, 5
        def profile_sigma(gamma):
            return find_best_beta_for_gamma(gamma)[1]
        def profile_gradient(gamma):
            return profile_sigma(gamma + h) - profile_sigma(gamma - h)
        def find_right_anchor():
            return 509
        # @step: 5 | 网格
        gammas = (0, 509)
        # @step: 6 | 位置试算
        sigmas = [profile_sigma(g) for g in gammas]
        # @step: 7 | 计算梯度
        grads = [profile_gradient(g) for g in gammas]
        # @step: 9 | 求位置 | 按梯度偏移定位
        # @formula: g(0)\ge\delta\Rightarrow\hat\gamma=0;\quad g(\hat\gamma)=\delta
        # @symbols: \gamma|\gamma|位置
        # @inputs: offset|\delta|偏移量
        # @outputs: found_gamma|\hat\gamma|位置
        root = root_scalar(objective, method="brentq")
        found_gamma = float(root.root)
        found_beta, _ = find_best_beta_for_gamma(found_gamma)
        solution_strategy = "brent_root"
        # @step: 11 | 算尺度 | 均值
        found_eta = np.mean(etas)
        # @step: 12 | 计算 R²
        r2 = self._calculate_r2(found_beta, found_eta, found_gamma)
        return float(found_beta), found_eta, found_gamma, r2, True
`)
    const base = Buffer.from('def __init__(self):\n    self.data = sorted(data)\n' +
      'def log_step(self):\n    pass\n' +
      'def _median_ranks(self):\n    return (i - 0.3) / (n + 0.4)\n' +
      'def _cdf_3p(self):\n    pass\n' +
      'def _calculate_r2(self):\n    return 1 - (ss_res / ss_tot)\n')
    const traces = book.groups[3].resultRows.map(([id, beta, eta]) => ({
      id, profile: [[0, 100, beta], [509, 50, beta]], shape: [[beta, 45], [beta + 1, 140]],
      trialShapes: [[[beta, 100], [beta + 1, 160]], [[beta, 50], [beta + 1, 145]]],
      pseudoScales: [[.9, eta - 1], [1, eta], [1.1, eta + 1]], scaleSum: eta * 3,
    }))
    const save = () => {
      write('workbook.json', Buffer.from(JSON.stringify(book)), 'view')
      write(entry.mdmProcess.records, Buffer.from(records.map(row => JSON.stringify(row)).join('\n')), 'input')
      write(entry.mdmProcess.source, source, 'code')
      write(entry.mdmProcess.base, base, 'code')
      seal()
      const replay = Buffer.from(JSON.stringify({ manifestSha256: entry.manifestSha256, n: 3, delta: .1, runs: traces }))
      entry.mdmProcess.replay.sha256 = sha(replay)
      write('replay.json', replay)
    }
    save()
    return run({ ...context, book, records, source, traces, save })
  })
}

test('archived process binds all curves to workbook rows and exposes the frozen solver source', () => archivedProcessFixture(({ api, source }) => {
  const result = api.registeredWorkbookProcess('fixture', 3, .1)
  assert.equal(result.runs.length, 2)
  assert.equal(result.runs[1].gamma, 501)
  assert.equal(result.runs[1].sample.join(','), '515,540,610')
  assert.equal(result.runs[0].curve.length, 2)
  assert.equal(result.flow.sources[0].sha256, sha(source))
  assert.equal(result.flow.artifacts[0].path, 'source/estimates.jsonl')
  assert.equal(result.flow.artifacts[1].path, 'workbook.json')
  assert.equal(result.flow.artifacts[2].path, 'fixture/replay.json')
  assert.deepEqual(Array.from(result.flow.steps, step => step.name), loadMethodFlow('mdm').steps.map(step => step.name))
  assert.equal(result.flow.workflow.targets.scale, 5)
  assert.equal(result.runs[1].trace.pseudoScales[0][1], 1009)
  assert.equal(result.runs[1].rSquared, .95)
  assert.equal(api.registeredWorkbookTrialShapes('fixture', 3, .1, 2)[1][0][1], 50)
  assert.equal(api.registeredWorkbookTrialShapes('fixture', 3, .1, 3), null)
  assert.equal(result.flow.steps[2].formula.equations.length, 2)
  const reference = result.flow.steps[2].sources[0]
  const code = result.flow.sources[0].lines.slice(reference.start, reference.end).join('\n')
  assert.match(code, /method="brentq"/)
  assert.doesNotMatch(code, /found_eta = np.mean/)
  assert.equal(api.registeredWorkbookProcess('fixture', 7, .1), null)
  assert.equal(api.registeredWorkbookProcess('fixture', 3, .2), null)
  assert.equal(api.registeredWorkbookProcess('../fixture', 3, .1), null)
}))

test('archived process rejects partial, duplicated or mismatched estimation records', () => {
  for (const mutate of [
    ({ records }) => { records.pop() },
    ({ records }) => { records.push(structuredClone(records[0])) },
    ({ book }) => { book.groups[3].samples.push([...book.groups[3].samples[0]]) },
    ({ records }) => { records[0].gamma_hat = 499 },
    ({ records }) => { records[0].extra.solution_info.target_offset = .2 },
    ({ records }) => { records[0].extra.solution_info.optimal_gamma = 499 },
    ({ records }) => { records[0].extra.solution_info.root_solver = 'linear_interpolation' },
    ({ records }) => { records[0].criterion_curve = [] },
    ({ traces }) => { traces[0].profile[0][0] = 1 },
    ({ traces }) => { traces[0].shape = [[1, 50]] },
    ({ traces }) => { traces[0].scaleSum++ },
  ]) archivedProcessFixture(context => {
    mutate(context)
    context.save()
    assert.throws(() => context.api.registeredWorkbookProcess('fixture', 3, .1), /不一致|全部重复|不唯一/)
  })
})

test('archived process rejects changed curve and source files before displaying a batch', () => archivedProcessFixture(({ api, entry, write, source, save }) => {
  write(entry.mdmProcess.records, Buffer.from('changed'))
  assert.throws(() => api.registeredWorkbookProcess('fixture', 3, .1), /身份已变化/)
  save()
  write(entry.mdmProcess.source, Buffer.concat([source, Buffer.from('\n# changed')]))
  assert.throws(() => api.registeredWorkbookProcess('fixture', 3, .1), /身份已变化/)
  save()
  write('replay.json', Buffer.from('changed'))
  assert.throws(() => api.registeredWorkbookProcess('fixture', 3, .1), /补录计算记录的身份已变化/)
}))

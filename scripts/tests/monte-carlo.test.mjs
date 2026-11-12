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
    const context = vm.createContext({ process: { env: { WEIBULL_DATA_ROOT: data }, cwd: () => process.cwd() }, console, Buffer, structuredClone })
    vm.runInContext('(function(require,module,exports){' + compiled + '\n})', context, { filename: file })(localRequire, module, module.exports)
    return module.exports
  }
  try { return run({ root, data, load, workspace, raw, code, entry, manifest, write, seal, api: load('src/lib/server/monte-carlo.ts') }) }
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

function calculationFixture(run) {
  return fixture(context => {
    const { entry, write, seal, data } = context
    const flow = structuredClone(loadMethodFlow('mdm'))
    const set = {
      schemaVersion: 1, method: 'mdm', model: '3p', title: 'MDM records', settings: { offset: .1 }, truth: [2,1000,500],
      implementation: { sources: flow.sources.map(source => ({ path: source.path.replace(/^python\//, ''), sha256: source.sha256 })) }, flow,
      records: [1,2].map(id => ({ id, input: { observations: id === 1 ? [510,530,600] : [515,540,610] },
        result: { beta: 2, eta: 1000, gamma: 500, rSquared: .95, converged: true },
        process: { solver: 'linear_interpolation', offset: .1, bracket: [0,509], curve: [{gamma:0,gradient:0},{gamma:509,gradient:.2}],
          trace: { profile: [[0,50,2],[509,45,2]], shape: [[2,45],[3,140]],
            trialShapes: [[[2,50],[3,160]],[[2,45],[3,140]]], pseudoScales: [[.9,999],[1,1000],[1.1,1001]], scaleSum: 3000 } } })),
    }
    const book = { schemaVersion: 1, id: 'fixture', sha256: entry.workbookSha256, title: set.title, truth: set.truth, sheets: [], source: {},
      groups: { 3: { samples: [[1,510,530,600],[2,515,540,610]], resultRows: [[1,2,1000,500],[2,2,1000,500]],
        blocks: [{ method:'mdm',delta:.1,column:1 }] } } }
    let file
    const save = () => {
      write('workbook.json', Buffer.from(JSON.stringify(book)), 'view'); seal()
      const bytes = Buffer.from(JSON.stringify(set)), digest = sha(bytes)
      file = path.join(data, 'calculation-records', 'mdm', digest+'.json')
      fs.mkdirSync(path.dirname(file), {recursive:true}); fs.writeFileSync(file, bytes)
      entry.mdmProcess = { n:3, delta:.1, recordId:'mdm-'+digest }
    }
    save()
    const store = context.load('src/lib/server/calculation-records.ts')
    return run({ ...context, set, book, save, store, get file() { return file } })
  })
}

test('calculation records are standalone and workbook adapters only verify the sample/result link', () => calculationFixture(({ api, entry, store, root }) => {
  const process = api.registeredWorkbookProcess('fixture',3,.1)
  assert.equal(process.runs.length,2)
  assert.equal(process.flow.steps.length,6)
  assert.equal(process.selection.id,entry.mdmProcess.recordId)
  assert.equal(process.runs[0].trace.trialShapes,undefined)
  assert.equal(api.registeredWorkbookTrialShapes('fixture',3,.1,2)[0][0][1],50)
  assert.equal(api.registeredWorkbookProcess('fixture',7,.1),null)
  fs.unlinkSync(path.join(root,'workbook.json'))
  const set = store.readCalculationRecordSet(entry.mdmProcess.recordId)
  assert.equal(set.records.length,2)
  assert.equal(store.mdmRecordSetProcess(entry.mdmProcess.recordId,set,true).runs[1].trace.trialShapes.length,2)
  assert.doesNotMatch(JSON.stringify(set),/Research00|research00|replay|补录/)
}))

test('record sets reject incomplete stages, duplicate identities and mismatched sample/result links', () => {
  for (const mutate of [
    ({set}) => set.records.pop(),
    ({set}) => { set.records.push(structuredClone(set.records[0])) },
    ({book}) => { book.groups[3].samples.push([...book.groups[3].samples[0]]) },
    ({set}) => { set.records[0].result.gamma=499 },
    ({set}) => { set.records[0].input.observations[0]=511 },
    ({set}) => { set.records[0].process.trace.scaleSum++ },
    ({set}) => { set.records[0].process.trace.trialShapes[0]=[[9,99]] },
    ({set}) => { set.implementation.sources[0].sha256='0'.repeat(64) },
  ]) calculationFixture(context => {
    mutate(context);context.save()
    assert.throws(()=>context.api.registeredWorkbookProcess('fixture',3,.1),/不一致|全部样本|不完整/)
  })
})

test('record content is verified against its own identifier before rendering', () => calculationFixture(context => {
  fs.appendFileSync(context.file,' ')
  assert.throws(()=>context.store.readCalculationRecordSet(context.entry.mdmProcess.recordId),/内容哈希不一致/)
  assert.equal(context.store.readCalculationRecordSet('../fixture'),null)
}))

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
    const localRequire = name => name === '@/content/monte-carlo/research00.json' ? index : name.startsWith('.') ? load(path.resolve(path.dirname(file), name + '.ts')) : require(name)
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

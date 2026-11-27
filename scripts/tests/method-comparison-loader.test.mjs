import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const params = { beta: 2, eta: 1000, gamma: 1000, n: 7, offset: 0.1, rep: 2, seed: 42, step: 60 }
const selection = patch => ({ params: { ...params, ...patch }, complete: true, multiple: false })
const shard = offset => `b2_e1000_g1000_n7_d${offset}_rep2_seed42_step60.csv`
const mleShard = 'b2_e1000_g1000_n7_rep2_seed42_step60.csv'
const catalog = chunks => Response.json({ chunks, parsedParams: {}, total: chunks.length })
const archive = beta => new Response(`beta_true,eta_true,sample_size,sim_id,est_beta,est_eta\n2,1000,7,1,${beta},900`)
const simulation = offset => Response.json({
  rows: [1, 2].map(id => ({ method_id: 'mdm', beta_true: 2, eta_true: 1000, gamma: 1000, sample_size: 7,
    sim_id: id, offset_value: offset, est_beta: 1.5, est_eta: 900, est_gamma: 1000, status: id === 1 ? 'success' : 'failure' })),
  metrics: {
    n_total: 2, n_valid: 1, n_failure: 1,
    param_standard: Object.fromEntries(['beta', 'eta', 'gamma'].map(key => [key,
      { absolute: { n: 1, bias: 0, sd: 0, rmse: 0, mae: 0 } }])),
  },
})
const tick = () => new Promise(resolve => setImmediate(resolve))

function deferred() {
  let resolve
  const response = new Promise(done => { resolve = done })
  return { response, resolve }
}

function fixture(t, respond) {
  let nextTimer = 0
  const timers = new Map()
  const { createMethodComparisonLoader, initialMethodComparisonParams } = loadServerModule(
    'src/lib/method-comparison-loader.ts', {}, {
      setTimeout(callback) { timers.set(++nextTimer, callback); return nextTimer },
      clearTimeout(timer) { timers.delete(timer) }
    }
  )
  const states = new Map()
  const requests = []
  const loader = createMethodComparisonLoader((id, state) => states.set(id, state), async (url, options) => {
    const call = { url, ...options }
    requests.push(call)
    return respond(call)
  })
  t.after(() => loader.dispose())
  return {
    loader, initialMethodComparisonParams, requests,
    result: id => states.get(id)?.result,
    runScheduledSimulation() {
      for (const start of [...timers.values()]) start()
    }
  }
}

test('bootstrap and stable selections share one catalog and one archive request', async t => {
  const f = fixture(t, ({ url }) => {
    if (url.startsWith('/api/studies/')) return catalog([shard(0.1)])
    assert.equal(url, `/studies/mdm/chunks/${shard(0.1)}`)
    return archive(2)
  })
  const initial = await f.loader.catalog('mdm')
  assert.equal(f.initialMethodComparisonParams(initial).offset, 0.1)
  f.loader.select(['mdm'], selection())
  f.loader.select(['mdm'], selection())
  await tick()
  assert.equal(f.requests.length, 2)
  assert.equal(f.result('mdm').source, 'archive')
  assert.equal(f.result('mdm').filename, shard(0.1))
  assert.equal(f.result('mdm').rows[0].est_beta, 2)
  assert.equal(f.result('mdm').rows[0].gamma, 1000)
})

test('a late archive body cannot overwrite a later selection even if fetch ignores abort', async t => {
  const oldBody = deferred()
  const f = fixture(t, ({ url }) => {
    if (url.startsWith('/api/studies/')) return catalog([shard(0.1), shard(0.24)])
    if (url.endsWith(shard(0.1))) return { ok: true, text: () => oldBody.response }
    assert.ok(url.endsWith(shard(0.24)))
    return archive(3)
  })
  f.loader.select(['mdm'], selection())
  await tick()
  f.loader.select(['mdm'], selection({ offset: 0.24 }))
  await tick()
  assert.equal(f.requests[1].signal.aborted, true)
  assert.equal(f.result('mdm').filename, shard(0.24))
  oldBody.resolve(await archive(2).text())
  await tick()
  assert.equal(f.result('mdm').rows[0].est_beta, 3)
})

test('an index failure is local to one method and can be retried', async t => {
  let requestCount = 0
  const f = fixture(t, ({ url }) => {
    if (url === '/api/studies/mdm/chunks') return ++requestCount === 1 ? new Response('', { status: 503 }) : catalog([shard(0.1)])
    if (url === '/api/studies/mle/chunks') return catalog([mleShard])
    return archive(2)
  })
  f.loader.select(['mdm', 'mle'], selection())
  await tick()
  assert.equal(f.result('mdm').status, 'error')
  assert.equal(f.result('mdm').stage, 'catalog')
  assert.equal(f.result('mle').source, 'archive')
  f.loader.retry('mdm')
  await tick()
  assert.equal(f.result('mdm').source, 'archive')
  assert.equal(f.requests.filter(({ url }) => url.includes('mle')).length, 2)
})

test('missing fixed combinations simulate once, failed simulations retry, and variable selections stay archival', async t => {
  let simulationCount = 0
  const f = fixture(t, ({ url, body }) => {
    if (url === '/api/studies/mdm/chunks') return catalog([])
    assert.equal(url, '/api/studies/simulate')
    assert.equal(JSON.parse(body).params.offset, 0.24)
    return ++simulationCount === 1 ? new Response('', { status: 503 }) : simulation(0.24)
  })
  const current = selection({ offset: 0.24 })
  f.loader.select(['mdm'], current)
  await tick()
  assert.equal(f.result('mdm').status, 'waiting-for-simulation')
  f.runScheduledSimulation()
  await tick()
  assert.equal(f.result('mdm').stage, 'simulation')
  f.runScheduledSimulation()
  assert.equal(simulationCount, 1)
  f.loader.retry('mdm')
  await tick()
  assert.equal(f.result('mdm').source, 'simulation')
  assert.equal(f.result('mdm').metrics.n_valid, 1)
  assert.equal(f.result('mdm').rows[1].status, 'failure')
  f.loader.select(['mdm'], { ...current, multiple: true })
  await tick()
  assert.equal(f.result('mdm').status, 'missing')
  f.runScheduledSimulation()
  assert.equal(simulationCount, 2)
})

test('a late simulation and a removed method cannot replace the current result', async t => {
  const oldSimulation = deferred()
  const f = fixture(t, ({ url }) => {
    if (url === '/api/studies/mdm/chunks') return catalog([shard(0.24)])
    if (url === '/api/studies/simulate') return oldSimulation.response
    return archive(3)
  })
  f.loader.select(['mdm'], selection())
  await tick()
  f.runScheduledSimulation()
  const active = f.requests[1]
  assert.equal(f.result('mdm').status, 'simulating')
  f.loader.select([], selection())
  assert.equal(active.signal.aborted, true)
  f.loader.select(['mdm'], selection({ offset: 0.24 }))
  await tick()
  oldSimulation.resolve(simulation(0.1))
  await tick()
  assert.equal(f.result('mdm').filename, shard(0.24))
})

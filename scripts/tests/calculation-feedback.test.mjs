import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

function feedback(fetch) {
  return loadServerModule('src/lib/calculation-feedback.ts', {}, { fetch })
}
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
async function rejected(promise) {
  try { await promise } catch (error) { return error }
  assert.fail('Expected the request to fail')
}

test('a rejected fetch is a connection notice without asserting CORS or a solver failure', async () => {
  const client = feedback(async () => { throw new TypeError('Failed to fetch') })
  const error = await rejected(client.requestCalculationJson('http://api.test/calculate', {}, true))
  assert.equal(error.kind, 'connection')
  const notice = client.getCalculationNotice(error, 'mle')
  assert.equal(notice.title, '连接未完成')
  assert.equal(notice.description, '暂时无法连接计算服务，请稍后重试。')
  assert.equal('suggestion' in notice, false)
  assert.doesNotMatch(notice.description, /极大值|样本错误|已执行/)
})

test('the actual MLE no-finite-maximum status explains the solver outcome', async () => {
  const client = feedback(async () => json({ detail: "Method 'mle' failed: {'raw_status': 'no_finite_local_maximum'}" }, 422))
  const error = await rejected(client.requestCalculationJson('/calculate', {}, true))
  assert.equal(error.status, 422)
  assert.equal(error.kind, 'solver')
  assert.equal(client.getCalculationNotice(error, 'mle').description, 'MLE 未找到有限极大值，可尝试其他方法。')
  assert.doesNotMatch(client.getCalculationNotice(error, 'mdm').description, /MLE|极大值/)
})

test('FastAPI and runner invalid-sample 422 responses remain input notices', async () => {
  for (const detail of [
    [{ loc: ['body', 'data'], msg: 'Field required', type: 'missing' }],
    "Method 'mle' failed: {'error': 'invalid sample: observations must not all be equal'}",
  ]) {
    const client = feedback(async () => json({ detail }, 422))
    const error = await rejected(client.requestCalculationJson('/calculate', {}, true))
    assert.equal(error.kind, 'input')
    assert.equal(client.getCalculationNotice(error, 'mle').title, '请检查计算条件')
  }
})

test('structured trace failures retain their calculation and trace for method pages', async () => {
  const calculation = { selection: { status: 'no_finite_local_maximum' } }
  const trace = [{ phase: 'failed' }]
  const client = feedback(async () => json({ detail: { message: '无有限候选', calculation, trace_data: trace } }, 422))
  const error = await rejected(client.requestCalculationJson('/calculate', {}, true))
  assert.equal(error.kind, 'solver')
  assert.equal(JSON.stringify(error.calculation), JSON.stringify(calculation))
  assert.equal(JSON.stringify(error.traceData), JSON.stringify(trace))
  assert.match(client.getCalculationNotice(error, 'mle').description, /有限极大值/)
})

test('non-JSON HTTP failures and AI validation are not mistaken for MLE solver failures', async () => {
  for (const [response, expectedKind] of [
    [new Response('<html>Unavailable</html>', { status: 503 }), 'service'],
    [json({ detail: 'Unsupported AI sample size' }, 422), 'service'],
  ]) {
    const client = feedback(async () => response)
    const error = await rejected(client.requestCalculationJson('/ai/process-optimization/mdm', {}))
    assert.equal(error.kind, expectedKind)
    assert.doesNotMatch(client.getCalculationNotice(error, 'mle').description, /MLE|极大值/)
  }
  const busy = feedback(async () => json({ detail: 'busy' }, 429))
  const error = await rejected(busy.requestCalculationJson('/calculate', {}, true))
  assert.equal(busy.getCalculationNotice(error).title, '计算服务正忙')
})

test('an unreadable successful response is not called a connection failure', async () => {
  const client = feedback(async () => new Response('not JSON'))
  const error = await rejected(client.requestCalculationJson('/calculate', {}, true))
  assert.equal(error.kind, 'response')
})

test('the real calculator client preserves a successful response and exported error identity', async () => {
  const requests = []
  const backend = { method: 'mle', beta: 2.5, eta: 1000, gamma: 500, rSquared: .99, converged: true,
    plot_points: [{ t: 1000, x: 1, y: 2 }], calculation: { selection: { status: 'ok' } }, trace_data: [{ phase: 'final' }] }
  const shared = feedback(async (url, options) => { requests.push({ url, options }); return json(backend) })
  const client = loadServerModule('src/hooks/useWeibullCalculation.ts', {
    '@/lib/calculation-feedback': shared,
    '@/lib/config': { getApiBaseUrl: () => 'http://api.test' },
    '@/lib/weibull': { calculateMedianRanks() { assert.fail('Backend points must be used') } },
  })
  const data = [{ id: 1, value: 1000, status: 'F' }, { id: 2, value: 1100, status: 'S' }]
  const result = await client.calculateWeibull({ methodId: 'mle', data, trace: true })
  assert.equal(client.CalculationError, shared.CalculationError)
  assert.equal(result.result.beta, 2.5)
  assert.equal(JSON.stringify(result.traceData), JSON.stringify(backend.trace_data))
  assert.equal(JSON.stringify(result.calculation), JSON.stringify(backend.calculation))
  assert.equal(requests[0].url, 'http://api.test/calculate')
  assert.equal(requests[0].options.body, JSON.stringify({ method: 'mle', data: [1000], trace: true }))
  assert.equal(data.length, 2)
})

test('a generic solver failure does not assert that a finite maximum cannot exist', () => {
  const client = feedback(async () => json({}))
  const error = new client.CalculationError('参数估计未收敛', undefined, undefined, { kind: 'solver' })
  const notice = client.getCalculationNotice(error, 'mle', '样本组2')
  assert.equal(notice.sourceName, '样本组2')
  assert.doesNotMatch(notice.description, /有限极大值/)
})

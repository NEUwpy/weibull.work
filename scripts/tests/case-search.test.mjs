import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule as load } from './helpers/load-server-module.mjs'

const entry = { id: 'epoxy', name: '环氧树脂击穿电压试验', is_group: true, nature: { kind: 'observed', observation: 'grouped' },
  scale: '5 组样本', sources: [{ paper_id: '182-105' }], description: '五批20点实测样本', can_calculate: false }
const sample = { id: 'batch-1', name: '第1批击穿电压', nature: { kind: 'observed', observation: 'complete' },
  scale: '20 点', can_calculate: true, role: 'sample', sources: [] }

function fixture({ configured = true, records = [entry], completion = () => ({ matches: [{ id: 'epoxy', reason: '五批完整的实测样本，可直接估计参数。' }] }) } = {}) {
  const calls = []
  const route = load('src/app/api/cases/search/route.ts', {
    '@/lib/server/case-catalog': { loadCaseCatalog: () => ({ records, groups: new Map([['epoxy', { ...entry, members: [sample] }]]) }) },
    '@/lib/server/deepseek-client': {
      hasDeepSeekKey: () => configured,
      getDeepSeekSettings: () => ({ model: 'test-model' }),
      getDeepSeekClient: () => ({ chat: { completions: { create: async (request, options) => {
        calls.push({ request, options })
        const value = completion()
        return { choices: [{ message: { content: typeof value === 'string' ? value : JSON.stringify(value) } }] }
      } } } }),
    },
  })
  return { calls, post: body => route.POST(new Request('http://localhost/api/cases/search', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })) }
}

test('invalid or unconfigured searches do not call the provider', async () => {
  const { post, calls } = fixture()
  for (const question of ['', '  ', 123, 'a'.repeat(2001)]) assert.equal((await post({ question })).status, 400)
  assert.equal(calls.length, 0)
  assert.equal((await fixture({ configured: false }).post({ question: '查找实测数据' })).status, 503)
})

test('AI ranks only server-owned groups and keeps calculator eligibility and source links', async () => {
  const { post, calls } = fixture({ completion: () => ({ matches: [
    { id: 'not-published', reason: '库外资料' }, { id: 'epoxy', reason: '五批完整样本' },
    { id: 'epoxy', reason: '重复' }, { id: 'batch-1', reason: '不能拆散为外层案例' },
  ] }) })
  const result = await (await post({ question: '有可直接用于估计的实测寿命数据吗？', catalog: [{ id: 'client-forged-case' }] })).json()
  assert.deepEqual(result.results.map(match => match.entry.id), ['epoxy'])
  assert.equal(result.results[0].entry.sources[0].paper_id, '182-105')
  const context = JSON.parse(calls[0].request.messages[1].content)
  assert.deepEqual(context.catalog.map(item => item.id), ['epoxy'])
  assert.equal(context.catalog[0].members[0].can_calculate, true)
  assert.equal(context.catalog[0].members[0].observation, '完整样本')
  assert.equal(JSON.stringify(context).includes('client-forged-case'), false)
  assert.ok(calls[0].options.signal)
})

test('empty relevance matches and an empty catalog return no invented cases', async () => {
  assert.deepEqual((await (await fixture({ completion: () => ({ matches: [] }) }).post({ question: '深度学习训练数据' })).json()).results, [])
  const { post, calls } = fixture({ records: [] })
  assert.deepEqual((await (await post({ question: '实测数据' })).json()).results, [])
  assert.equal(calls.length, 0)
})

test('malformed or failed provider responses produce a recoverable message', async () => {
  for (const completion of [() => 'not json', () => ({}), () => { throw { status: 429, message: 'private-provider-message' } }]) {
    const response = await fixture({ completion }).post({ question: '查找实测数据' })
    assert.equal(response.status, 502)
    const body = await response.json()
    assert.equal(typeof body.error, 'string')
    assert.equal(JSON.stringify(body).includes('private-provider-message'), false)
  }
})

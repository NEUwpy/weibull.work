import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { buildSearchQueries, selectLibraryEvidence, evidenceContext, orderEvidenceCandidates, poolLibraryCandidates } = loadServerModule('src/lib/library-rag.ts')

function hit(n, slug = '182-001', text = `这是正文证据 ${n}，说明条件与结论。`) {
  return { id: `${slug}-${n}`, slug, title: '测试文献', version: '原文', section: '方法', startLine: n,
    endLine: n + 1, text, excerpt: text, href: `/library/${slug}?version=原文#passage-${n}`, score: 10 }
}

test('query expansion retains the question and bounds/deduplicates generated variants', () => {
  const queries = buildSearchQueries(' Weibull MLE ', ['WEIBULL MLE', 1, '', '极大似然', 'a'.repeat(999), 'too many'], 4)
  assert.equal(queries[0], 'Weibull MLE')
  assert.equal(queries.length, 4)
  assert.equal(queries[1], 'MLE')
  assert.equal(queries[3].length, 160)
  assert.equal(buildSearchQueries('直接检索', { queries: ['wrong shape'] }).length, 1)
})

test('comparison retrieval preserves named methods even when paraphrases omit one', () => {
  const queries = buildSearchQueries('7个样本下 MLE 与 MDM 谁更好？', ['小样本 MLE', 'Weibull moment method comparison'])
  assert.ok(queries.includes('MDM'))
  assert.ok(queries.includes('MLE'))
  const repeated = Array.from({ length: 24 }, (_, i) => hit(i + 1, `mle-${i}`))
  const target = hit(100, 'mdm-paper', 'MDM 最小差异法的正文说明。')
  const candidates = poolLibraryCandidates([repeated, repeated, repeated, [target]], { maxPassages: 12, maxPerPaper: 3, maxContextChars: 18000 })
  assert.ok(candidates.some(candidate => candidate.id === target.id))
})

test('evidence fusion deduplicates identical text, caps each paper and total context', () => {
  const rankings = [Array.from({ length: 30 }, (_, i) => hit(i + 1, `182-${String(Math.floor(i / 5)).padStart(3, '0')}`))]
  rankings.push([rankings[0][0], hit(90, '182-099', rankings[0][0].text)])
  const evidence = selectLibraryEvidence(rankings, { maxPassages: 12, maxPerPaper: 3, maxContextChars: 2300 })
  assert.ok(evidence.length > 0 && evidence.length <= 12)
  assert.ok(JSON.stringify(evidenceContext(evidence)).length <= 2300)
  const counts = new Map()
  for (const [i, passage] of evidence.entries()) {
    assert.equal(passage.citation, i + 1)
    counts.set(passage.slug, (counts.get(passage.slug) || 0) + 1)
  }
  assert.ok([...counts.values()].every(n => n <= 3))
  assert.equal(evidence.filter(p => p.text === rankings[0][0].text).length, 1)
})

test('semantic screening can select no evidence and cannot introduce a new source', () => {
  const candidates = selectLibraryEvidence([[hit(10), hit(20)]], { maxPassages: 12, maxPerPaper: 3, maxContextChars: 18000 })
  const selected = orderEvidenceCandidates(candidates, [candidates[1].id, 'invented-source', candidates[1].id])
  assert.equal(selected.length, 1)
  assert.equal(selected[0].id, candidates[1].id)
  assert.equal(orderEvidenceCandidates(candidates, []).length, 0)
  assert.throws(() => orderEvidenceCandidates(candidates, null), /Invalid evidence/)
})

function chatRoute({ results = [hit(10)], brokenExpansion = false, failAnswer = false } = {}) {
  const calls = []
  const searches = []
  const client = { chat: { completions: { create: async (params, options) => {
    calls.push({ params, signal: options.signal })
    if (!params.stream) {
      if (params.messages[0].content.startsWith('你筛选')) return { choices: [{ message: { content: JSON.stringify({ ranked_ids: results.map(item => item.id) }) } }] }
      if (brokenExpansion) throw new Error('expansion fixture failure')
      return { choices: [{ message: { content: JSON.stringify({ queries: ['Weibull maximum likelihood', '三参数 极大似然'] }) } }] }
    }
    if (failAnswer) throw Object.assign(new Error('DO NOT ECHO SECRET FIXTURE'), { status: 401 })
    return (async function* () { yield { choices: [{ delta: { content: '结论参见[1](/library/182-001?version=原文#passage-10)。' } }] } })()
  } } } }
  const route = loadServerModule('src/app/api/chat/route.ts', {
    '@/lib/server/deepseek-client': { hasDeepSeekKey: () => true, getDeepSeekClient: () => client,
      getDeepSeekSettings: () => ({ model: 'deepseek-flash', label: 'DeepSeek V4.1 Flash' }) },
    '@/lib/server/library-search': { searchLibrary: (query) => { searches.push(query); return { results } }, enrichLibrarySearchHits: hits => hits },
  })
  return { route, calls, searches }
}

test('chat retrieves server-side evidence and streams the supplied sources on the same response', async () => {
  const { route, calls, searches } = chatRoute()
  const response = await route.POST({ json: async () => ({ question: '什么是极大似然？', papers: [{ slug: 'private-injected' }] }) })
  const text = await response.text()
  assert.equal(response.status, 200)
  assert.ok(text.includes('"evidence":['))
  assert.ok(text.includes('"citation":1'))
  assert.ok(text.includes('"done":true'))
  assert.equal(calls.length, 3)
  assert.equal(searches.length, 3)
  assert.equal(calls[0].params.model, 'deepseek-flash')
  assert.equal(calls[0].params.response_format.type, 'json_object')
  assert.ok(calls[2].params.messages[1].content.includes('这是正文证据'))
  assert.ok(!calls[2].params.messages[1].content.includes('private-injected'))
  assert.equal(calls[2].params.thinking.type, 'disabled')
})

test('chat rejects invalid input and explicitly distinguishes general knowledge when evidence is empty', async () => {
  const { route, calls } = chatRoute({ results: [] })
  for (const question of [null, {}, '', 'x'.repeat(2001)]) {
    assert.equal((await route.POST({ json: async () => ({ question }) })).status, 400)
  }
  assert.equal((await route.POST({ json: async () => { throw new SyntaxError() } })).status, 400)
  const text = await (await route.POST({ json: async () => ({ question: '非库内问题' }) })).text()
  assert.ok(text.includes('"evidence":[]'))
  assert.equal(calls.length, 2)
  assert.ok(calls[1].params.messages[0].content.includes('资料为空时'))
  assert.ok(calls[1].params.messages[1].content.endsWith('参考资料：\n[]'))
})

test('failed expansion still searches the exact question; provider errors remain redacted', async () => {
  const { route, searches } = chatRoute({ brokenExpansion: true, failAnswer: true })
  const text = await (await route.POST({ json: async () => ({ question: '极大似然' }) })).text()
  assert.deepEqual(searches, ['极大似然'])
  assert.ok(text.includes('认证失败'))
  assert.ok(!text.includes('DO NOT ECHO SECRET'))
})

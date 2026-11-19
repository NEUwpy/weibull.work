import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { buildRecommendationSearchPlan, buildSearchQueries, selectLibraryEvidence, evidenceContext, orderEvidenceCandidates, poolLibraryCandidates } = loadServerModule('src/lib/library-rag.ts')

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

test('compound recommendations keep both the broad topic and the canonical method name when model variants are narrow', () => {
  const question = '我想研究小样本情况下的参数估计，再看 MDM 的自适应改进。请推荐论文。'
  const variants = ['MDM 小样本 参数估计', 'small sample parameter estimation MDM', 'MDM 自适应 改进']
  const queries = buildSearchQueries(question, variants, 6, true)
  assert.deepEqual(Array.from(queries), [question, 'MDM', '小样本 参数估计', '最小差异法', ...variants.slice(0, 2)])
  assert.deepEqual(Array.from(buildSearchQueries(question, variants)), [question, 'MDM', ...variants])
  const comparison = buildSearchQueries('请推荐 MLE 和 WMLE 对右截尾小样本参数估计的比较论文。', ['右截尾 三参数威布尔'], 6, true)
  assert.ok(comparison.includes('右截尾 三参数威布尔'))
})

test('recommendation plans preserve independent mechanism and comparison expressions within eight searches', () => {
  const question = '我想研究小样本情况下的参数估计，再看 MDM 的自适应改进。请推荐论文。'
  const plan = buildRecommendationSearchPlan(question, {
    queries: ['small sample estimation', 'adaptive Weibull', 'distribution fitting'],
    mechanism_queries: [null, '  tuning   parameter ', 'TUNING PARAMETER', 'tuning constant', 'extra mechanism'],
    comparison_query: 'Weibull weighted MLE',
  }, 8)
  assert.deepEqual(Array.from(plan.queries), [question, 'MDM', '小样本 参数估计', '最小差异法',
    'tuning parameter', 'tuning constant', 'Weibull weighted MLE', 'small sample estimation'])
  assert.deepEqual(Array.from(plan.mechanismQueries), ['tuning parameter', 'tuning constant'])
  assert.equal(plan.comparisonQuery, 'Weibull weighted MLE')
  const malformed = buildRecommendationSearchPlan(question, { mechanism_queries: {}, comparison_query: 123 }, 8)
  assert.deepEqual(Array.from(malformed.queries), [question, 'MDM', '小样本 参数估计', '最小差异法'])
  assert.equal(malformed.mechanismQueries.length, 0)
  assert.equal(malformed.comparisonQuery, undefined)
})

test('recommendation plans independently search the written method name for a proposed improvement', () => {
  const question = '我想要给最小差异法加一个机制，就是自适应选择偏移量。有哪些跟我这个相关的论文？'
  const plan = buildRecommendationSearchPlan(question, {
    queries: ['最小差异法 偏移量', 'minimum difference method offset', '自适应 偏移量 选择'],
    mechanism_queries: ['adaptive tuning parameter selection', 'data-driven regularization parameter'],
  }, 8)
  assert.deepEqual(Array.from(plan.methodQueries), ['最小差异法'])
  assert.equal(plan.queries[1], '最小差异法')
  assert.ok(plan.queries.includes('最小差异法 偏移量'))
  assert.deepEqual(Array.from(plan.mechanismQueries), ['tuning parameter', 'tuning constant'])
})

test('a written method name keeps its full qualifier and deduplicates its abbreviation', () => {
  const question = '请推荐修正极大似然估计（MMLE）的改进论文。'
  const plan = buildRecommendationSearchPlan(question, {}, 8)
  assert.deepEqual(Array.from(plan.methodQueries), ['修正极大似然估计'])
  assert.deepEqual(Array.from(plan.queries), [question, 'MMLE', '修正极大似然估计'])
})

test('tuning searches keep two short alternative expressions when generated phrases overconstrain matching', () => {
  const plan = buildRecommendationSearchPlan('研究按照数据选择稳健估计的调节量', {
    mechanism_queries: ['adaptive tuning parameter selection', 'data-driven regularization parameter'],
  }, 8)
  assert.deepEqual(Array.from(plan.mechanismQueries), ['tuning parameter', 'tuning constant'])
  assert.ok(plan.queries.includes('data-driven regularization parameter'))
  const threshold = buildRecommendationSearchPlan('请推荐动态检测阈值论文', { mechanism_queries: ['dynamic threshold'] }, 8)
  assert.deepEqual(Array.from(threshold.mechanismQueries), ['dynamic threshold'])
})

test('focused searches retain distinct candidates under a shared context budget', () => {
  const general = Array.from({ length: 8 }, (_, i) => hit(i + 1, `general-${i}`))
  const shared = hit(10, 'shared')
  const sharedTranslation = { ...hit(11, 'shared'), version: '翻译' }
  const mechanism = hit(12, 'mechanism')
  const comparison = hit(13, 'comparison')
  const focused = [[shared, mechanism], [sharedTranslation, comparison]]
  const limits = { maxPassages: 8, maxPerPaper: 1, maxContextChars: 520 }
  const pool = poolLibraryCandidates([general, ...focused], limits, focused)
  assert.deepEqual(Array.from(pool, candidate => candidate.slug), ['shared', 'mechanism', 'comparison'])
  assert.ok(JSON.stringify(evidenceContext(pool)).length <= limits.maxContextChars)
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

function chatRoute({ results = [hit(10)], brokenExpansion = false, failAnswer = false, screeningContent, answerError } = {}) {
  const calls = []
  const searches = []
  const diagnostics = []
  const records = []
  const client = { chat: { completions: { create: async (params, options) => {
    calls.push({ params, signal: options.signal })
    if (!params.stream) {
      if (params.messages[0].content.startsWith('你筛选')) return { choices: [{ message: { content: screeningContent ?? JSON.stringify({ ranked_ids: results.map(item => item.id) }) } }] }
      if (brokenExpansion) throw new Error('expansion fixture failure')
      return { choices: [{ message: { content: JSON.stringify({ queries: ['Weibull maximum likelihood', '三参数 极大似然'] }) } }] }
    }
    if (answerError) throw answerError
    if (failAnswer) throw Object.assign(new Error('DO NOT ECHO SECRET FIXTURE'), { status: 401 })
    return (async function* () { yield { choices: [{ delta: { content: '结论参见[1](/library/182-001?version=原文#passage-10)。' } }] } })()
  } } } }
  const route = loadServerModule('src/app/api/chat/route.ts', {
    '@/lib/server/library-chat-log': { createLibraryChatLog: () => ({ record: (event, details) => records.push({event, ...details}), flush: async () => {} }) },
    '@/lib/server/deepseek-client': { hasDeepSeekKey: () => true, getDeepSeekClient: () => client,
      getDeepSeekSettings: () => ({ model: 'deepseek-flash', label: 'DeepSeek V4.1 Flash' }) },
    '@/lib/server/library-search': { searchLibrary: (query) => { searches.push(query); return { results } }, enrichLibrarySearchHits: hits => hits,
      startLibrarySearchPrewarm: async () => {} },
  }, { console: { warn: (...args) => diagnostics.push(args), error: (...args) => diagnostics.push(args) } })
  return { route, calls, searches, diagnostics, records }
}

test('chat retrieves server-side evidence and streams the supplied sources on the same response', async () => {
  const { route, calls, searches, records } = chatRoute()
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
  assert.equal(records[0].question, '什么是极大似然？')
  assert.ok(records.find(record => record.event === 'retrieval').sources.length)
  assert.equal(records.at(-1).outcome, 'completed')
  assert.doesNotMatch(JSON.stringify(records), /这是正文证据|结论参见/)
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

test('screening format failures report their stage without logging raw model data', async () => {
  const { route, diagnostics, records } = chatRoute({ screeningContent: 'DO NOT ECHO RAW MODEL DATA' })
  const text = await (await route.POST({ json: async () => ({ question: '矩估计是什么？' }) })).text()
  assert.match(text, /参考资料筛选未完成/)
  assert.equal(diagnostics[0][1].stage, 'screening')
  assert.equal(diagnostics[0][1].name, 'SyntaxError')
  assert.doesNotMatch(JSON.stringify(diagnostics) + text, /DO NOT ECHO/)
  assert.equal(records.at(-1).outcome, 'failed')
  assert.equal(records.find(record => record.event === 'error').stage, 'screening')
  assert.doesNotMatch(JSON.stringify(records), /DO NOT ECHO/)
})

test('connection and timeout failures have actionable messages and redacted diagnostics', async () => {
  for (const [name, expected] of [['APIConnectionTimeoutError', /响应超时/], ['APIConnectionError', /无法连接/]]) {
    const answerError = Object.assign(new Error('DO NOT ECHO REQUEST OR KEY'), { name })
    const { route, diagnostics } = chatRoute({ answerError })
    const text = await (await route.POST({ json: async () => ({ question: '矩估计是什么？' }) })).text()
    assert.match(text, expected)
    assert.equal(diagnostics[0][1].stage, 'answering')
    assert.equal(diagnostics[0][1].name, name)
    assert.doesNotMatch(JSON.stringify(diagnostics) + text, /DO NOT ECHO/)
  }
})

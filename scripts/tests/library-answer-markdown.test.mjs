import test from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import Markdown from 'react-markdown'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkMath from 'remark-math'
import { remarkLibraryAnswerCitations } from '../../src/lib/library-answer-markdown.ts'

const evidence = [
  { citation: 1, href: '/library/182-046?version=%E7%BF%BB%E8%AF%91#passage-59' },
  { citation: 2, href: '/library/181-004?version=%E5%8E%9F%E6%96%87#passage-12' },
]

function parse(source, sources = evidence) {
  const processor = unified().use(remarkParse).use(remarkMath).use(remarkLibraryAnswerCitations, { evidence: sources })
  return processor.runSync(processor.parse(source))
}

function collect(tree, types) {
  const found = []
  function walk(node) {
    if (types.includes(node.type)) found.push(node)
    node.children?.forEach(walk)
  }
  walk(tree)
  return found
}

test('normal, bare, spaced and malformed citation links use the exact evidence URL', () => {
  const source = '正常 [1](/wrong)，裸引用 [1]，空格 [2]( /wrong )，错误地址 [2](bad url)。'
  const links = collect(parse(source), ['link'])
  assert.deepEqual(links.map(link => link.url), [evidence[0].href, evidence[0].href, evidence[1].href, evidence[1].href])
  assert.deepEqual(links.map(link => link.children[0].value), ['[1]', '[1]', '[2]', '[2]'])
  const html = renderToStaticMarkup(React.createElement(Markdown, {
    remarkPlugins: [[remarkLibraryAnswerCitations, { evidence }]], children: source,
  }))
  assert.equal((html.match(/<a /g) || []).length, 4)
  assert.equal(html.includes('/wrong'), false)
  assert.equal(html.includes('bad url'), false)
})

test('numeric evidence links cannot redirect to a model-written URL; unknown labels stay text', () => {
  const tree = parse('[1](https://unrelated.invalid/path) 和 [99] 以及 [99](/wrong)。')
  assert.deepEqual(collect(tree, ['link']).map(link => link.url), [evidence[0].href])
  const text = collect(tree, ['text']).map(node => node.value).join('')
  assert.equal((text.match(/\[99\]/g) || []).length, 2)
  assert.equal(collect(parse('[1](/wrong)', []), ['link']).length, 0)
})

test('code and inline/block math retain literal bracketed numbers', () => {
  const source = '`[1]` $a_{[1]}$\n\n```js\n[2](/wrong)\n```\n\n$$\nf_{[2]}(x)=1\n$$\n\n普通引用 [1]。'
  const before = unified().use(remarkParse).use(remarkMath).parse(source)
  const types = ['inlineCode', 'code', 'inlineMath', 'math']
  const after = parse(source)
  assert.deepEqual(collect(after, types).map(node => [node.type, node.value]), collect(before, types).map(node => [node.type, node.value]))
  assert.equal(collect(after, ['link']).length, 1)
})

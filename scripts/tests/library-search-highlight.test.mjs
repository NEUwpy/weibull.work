import test from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import Markdown from 'react-markdown'
import { processLibraryContent, getLibraryMarkdownOptions } from '../../src/lib/library-markdown.ts'
import { librarySearchHitHref, readLibrarySearchHighlight, rehypeLibrarySearchHighlights } from '../../src/lib/library-search-highlight.ts'

const text = value => ({ type: 'text', value })
const element = (tagName, children = [], properties = {}) => ({ type: 'element', tagName, children, properties })
function findAll(tree, predicate) { return [...(predicate(tree) ? [tree] : []), ...(tree.children || []).flatMap(child => findAll(child, predicate))] }
const marks = tree => findAll(tree, node => node.tagName === 'mark')

test('search links retain version and source anchor while carrying actual search terms', () => {
  const href = librarySearchHitHref('/library/182-046?version=%E7%BF%BB%E8%AF%91#passage-59', ['位置参数', 'Weibull', '位置参数'])
  const url = new URL(href, 'https://library.invalid')
  assert.equal(url.searchParams.get('version'), '翻译')
  assert.equal(url.hash, '#passage-59')
  assert.deepEqual(readLibrarySearchHighlight(url.search, url.hash), { passageId: 'passage-59', terms: ['位置参数', 'Weibull'] })
  assert.deepEqual(readLibrarySearchHighlight('?version=翻译', '#passage-59').terms, [])
  assert.deepEqual(readLibrarySearchHighlight(url.search, '#references-section'), { passageId: '', terms: [] })
})

test('only matching words in the target passage are marked across emphasis and links', () => {
  const link = element('a', [text('参数')], { href: '/methods/mdm' })
  const strong = element('strong', [text('位置')])
  const paragraph = element('p', [strong, link, text('估计 Weibull WEIBULL 和其他文字。')], { id: 'passage-4' })
  const other = element('p', [text('位置参数 Weibull')], { id: 'passage-8' })
  const tree = { type: 'root', children: [paragraph, other] }
  rehypeLibrarySearchHighlights({ passageId: 'passage-4', terms: ['位置参数', 'weibull'] })(tree)
  assert.deepEqual(marks(tree).map(mark => mark.children[0].value), ['位置', '参数', 'Weibull', 'WEIBULL'])
  assert.deepEqual(link.properties, { href: '/methods/mdm' })
  assert.equal(paragraph.children[0], strong)
  assert.equal(marks(other).length, 0)
  assert.ok(findAll(paragraph, node => node.type === 'text').some(node => node.value.includes('其他文字')))
})

test('math, code and citation subtrees stay unchanged, without duplicate KaTeX highlights', () => {
  const protectedNodes = [element('span', [text('Weibull')], { className: ['katex'] }), element('math', [text('Weibull')]),
    element('code', [text('Weibull')]), element('pre', [text('Weibull')]), element('sup', [element('a', [text('1')], { href: '#ref-1' })])]
  const snapshots = structuredClone(protectedNodes)
  const tree = { type: 'root', children: [element('p', [text('Weibull '), ...protectedNodes], { id: 'passage-1' })] }
  rehypeLibrarySearchHighlights({ passageId: 'passage-1', terms: ['weibull', '1'] })(tree)
  assert.deepEqual(protectedNodes, snapshots)
  assert.equal(marks(tree).length, 1)
})

test('changing target or clearing terms removes previous marks without losing rich text', () => {
  const link = element('a', [text('参数估计')], { href: '/method' })
  const tree = { type: 'root', children: [element('p', [link], { id: 'passage-1' }), element('p', [text('参数估计')], { id: 'passage-2' })] }
  rehypeLibrarySearchHighlights({ passageId: 'passage-1', terms: ['参数'] })(tree)
  assert.equal(marks(tree.children[0]).length, 1)
  rehypeLibrarySearchHighlights({ passageId: 'passage-2', terms: ['估计'] })(tree)
  assert.equal(marks(tree.children[0]).length, 0)
  assert.equal(marks(tree.children[1]).length, 1)
  rehypeLibrarySearchHighlights({ passageId: '', terms: [] })(tree)
  assert.equal(marks(tree).length, 0)
  assert.equal(link.children.map(node => node.value).join(''), '参数估计')
  assert.equal(link.properties.href, '/method')
})

test('the actual reader pipeline retains formulas, citations and links with word-only highlights', () => {
  const processed = processLibraryContent('# Title\n\n位置**参数** [估计](/methods/mdm) Weibull $Weibull$ `Weibull` [1]。\n\n## References\n[1] Source.\n')
  const options = getLibraryMarkdownOptions(processed)
  const html = renderToStaticMarkup(React.createElement(Markdown, { ...options,
    rehypePlugins: [...options.rehypePlugins, [rehypeLibrarySearchHighlights, { passageId: 'passage-3', terms: ['位置参数', 'weibull'] }]], children: processed.body }))
  assert.match(html, /<strong><mark[^>]*>参数<\/mark><\/strong>/)
  assert.match(html, /href="\/methods\/mdm">估计<\/a>/)
  assert.match(html, /<code>Weibull<\/code>/)
  assert.match(html, /href="#ref-1"/)
  assert.equal((html.match(/<mark /g) || []).length, 3)
  assert.match(html, /class="katex"/)
  assert.equal(html.includes('data-library-target'), false)
})

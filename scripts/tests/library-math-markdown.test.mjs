import test from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import Markdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { loadServerModule } from './helpers/load-server-module.mjs'
import { normalizeLibraryMath, libraryMathExcerpt, rehypeLibraryTextHighlights } from '../../src/lib/library-math-markdown.ts'
import { remarkLibraryAnswerCitations } from '../../src/lib/library-answer-markdown.ts'

const equations = [
  String.raw`\eta = \frac{t-\gamma}{\left(-\ln(1-F)\right)^{1/\beta}} \tag{9}`,
  String.raw`\left(\hat{\beta}_{MDM},\hat{\gamma}_{MDM}\right)=\arg\min_{(\beta,\gamma)}\ \mathrm{std}\!\left(\frac{t_i-\gamma}{\left(-\ln(1-F_i)\right)^{1/\beta}}\right) \tag{10}`,
  String.raw`\hat{\eta}_{MDM}=\frac{1}{n}\sum_{i=1}^{n}\frac{t_i-\gamma_{MDM}}{\left(-\ln(1-F_i)\right)^{1/\hat{\beta}_{MDM}}} \tag{11}`,
]

function render(source, terms = [], evidence = []) {
  return renderToStaticMarkup(React.createElement(Markdown, {
    skipHtml: true,
    remarkPlugins: [remarkMath, [remarkLibraryAnswerCitations, { evidence }]],
    rehypePlugins: [rehypeKatex, [rehypeLibraryTextHighlights, { terms }]],
    children: normalizeLibraryMath(source),
  }))
}

test('all three reported tagged MDM equations render in each supported delimiter format', () => {
  for (const wrap of [body => `$${body}$`, body => `$$${body}$$`, body => `\\[\n${body}\n\\]`, body => `$$\n${body}\n$$`]) {
    const source = equations.map(wrap).join('\n\n')
    const html = render(source)
    assert.equal((html.match(/class="katex"/g) || []).length, 3)
    assert.equal((html.match(/class="katex-display"/g) || []).length, 3)
    assert.equal(html.includes('katex-error'), false)
    const processor = unified().use(remarkParse).use(remarkMath)
    const values = processor.parse(normalizeLibraryMath(source)).children.filter(node => node.type === 'math').map(node => node.value)
    assert.deepEqual(values, equations, 'formula source is preserved, including the original gamma notation')
  }
})

test('inline slash math renders, while code, links and an unfinished streaming formula remain intact', () => {
  const literal = String.raw`\(\beta\) is code: ` + '`\\(x\\) $$y$$`' + '\n\n```latex\n\\[x\\] $z$\n```\n\n' + String.raw`[source](https://example.test/\(x\))`
  const normalized = normalizeLibraryMath(literal)
  assert.ok(normalized.startsWith('$\\beta$'))
  assert.ok(normalized.includes('`\\(x\\) $$y$$`'))
  assert.ok(normalized.includes('```latex\n\\[x\\] $z$\n```'))
  assert.ok(normalized.includes(String.raw`[source](https://example.test/\(x\))`))
  const html = render(literal)
  assert.equal((html.match(/class="katex"/g) || []).length, 1)
  assert.equal(normalizeLibraryMath('未完成 \\[x +'), '未完成 \\[x +')
  assert.equal(normalizeLibraryMath('未完成 $\\beta +'), '未完成 $\\beta +')
})

test('excerpt windows preserve complete formulas, operators, links and code at both edges', () => {
  const formula = String.raw`$\operatorname*{arg\,min}_{\beta < 3} \left(\frac{a}{b}\right)^{1/\beta}$`
  const source = '矩估计 ' + '前文'.repeat(155) + formula + '后文'.repeat(200)
  const endWindow = libraryMathExcerpt(source, ['矩估计'])
  assert.ok(endWindow.includes(formula))
  assert.equal(render(endWindow).includes('katex-error'), false)
  const startWindow = libraryMathExcerpt('前文'.repeat(50) + formula + '目标词 ' + '后文'.repeat(150), ['目标词'])
  assert.ok(startWindow.includes(formula))
  const link = '[完整的目标词](https://example.test/' + 'path'.repeat(80) + ')'
  const linked = libraryMathExcerpt('目标词 ' + '前'.repeat(280) + link + '后'.repeat(200), ['目标词'])
  assert.ok(linked.includes(link))
  const code = '`完整的目标词 ' + '$x$'.repeat(50) + '`'
  assert.ok(libraryMathExcerpt('目标词 ' + '前'.repeat(280) + code, ['目标词']).includes(code))
  assert.ok(libraryMathExcerpt('纯文字'.repeat(400), []).length <= 362)
})

test('word highlighting skips formulas and code, while numbered citations retain evidence links', () => {
  const evidence = [{ citation: 1, href: '/library/182-001?version=%E5%8E%9F%E6%96%87#passage-9' }]
  const html = render('矩估计 $\\text{矩估计} + \\beta$，`矩估计`。依据 [1]。', ['矩估计', 'beta'], evidence)
  assert.equal((html.match(/<mark /g) || []).length, 1)
  assert.ok(html.includes(`href="${evidence[0].href}"`))
  assert.equal(html.includes('katex-error'), false)
  assert.equal((html.match(/class="katex"/g) || []).length, 1)
})

test('the real search pipeline returns source math rather than a flattened or cut formula', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'weibull-math-search-'))
  const previous = process.env.WEIBULL_LIBRARY_ROOT
  try {
    fs.mkdirSync(path.join(root, 'content'))
    fs.mkdirSync(path.join(root, 'assets'))
    fs.writeFileSync(path.join(root, 'library.json'), JSON.stringify({ schema_version: 1 }))
    fs.writeFileSync(path.join(root, 'references.json'), '{}')
    const formula = String.raw`$\operatorname*{arg\,min}_{\beta < 3} \frac{a}{b}$`
    fs.writeFileSync(path.join(root, 'content', '182-001-pdf原文.md'), '---\ntitle: Source math\nauthor: Test Author\nyear: 2024\n---\n\n# Estimation\n\n矩估计 ' + '前文'.repeat(160) + formula + '后文'.repeat(150))
    process.env.WEIBULL_LIBRARY_ROOT = root
    const { searchLibrary } = loadServerModule('src/lib/server/library-search.ts')
    const hit = searchLibrary('矩估计').results[0]
    assert.ok(hit.excerpt.includes(formula))
    const html = render(hit.excerpt, ['矩估计'])
    assert.equal((html.match(/class="katex"/g) || []).length, 1)
    assert.equal(html.includes('katex-error'), false)
    assert.equal((html.match(/<mark /g) || []).length, 1)
  } finally {
    if (previous === undefined) delete process.env.WEIBULL_LIBRARY_ROOT
    else process.env.WEIBULL_LIBRARY_ROOT = previous
    fs.rmSync(root, { recursive: true, force: true })
  }
})

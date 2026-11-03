import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import ts from 'typescript'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import * as math from '../../src/lib/library-math-markdown.ts'
import * as citations from '../../src/lib/library-answer-markdown.ts'
import { libraryAuthorPreview } from '../../src/lib/library-card-presentation.ts'
import { loadServerModule } from './helpers/load-server-module.mjs'

// Render the actual shared TSX component, including its inline HTML boundary.
const file = 'src/components/shared/LibraryMathMarkdown.tsx'
const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
  jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
} }).outputText
const require = createRequire(import.meta.url)
const module = { exports: {} }
const esm = value => ({ __esModule: true, default: value })
const imports = { 'react-markdown': esm(Markdown), 'remark-gfm': esm(remarkGfm), 'remark-math': esm(remarkMath),
  'rehype-katex': esm(rehypeKatex), '@/lib/library-math-markdown': math, '@/lib/library-answer-markdown': citations }
vm.runInNewContext(compiled, { module, exports: module.exports, require: name =>
  name.endsWith('.css') ? {} : imports[name] ?? require(name) }, { filename: file })
const { LibraryMathMarkdown } = module.exports
const metadataModule = { exports: {} }
const metadataFile = 'src/components/library/LibraryCardMetadata.tsx'
vm.runInNewContext(ts.transpileModule(fs.readFileSync(metadataFile, 'utf8'), { compilerOptions: {
  jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
} }).outputText, { module: metadataModule, exports: metadataModule.exports, require: name =>
  name === '@/lib/library-types' ? loadServerModule('src/lib/library-types.ts') : require(name) }, { filename: metadataFile })
const { LibraryCardMetadata } = metadataModule.exports
const render = (source, props = {}) => renderToStaticMarkup(React.createElement('h3', null,
  React.createElement(LibraryMathMarkdown, { inline: true, ...props }, source)))

test('author preview keeps short lists and limits long lists without duplicating et al', () => {
  assert.equal(libraryAuthorPreview('Man Chen, Zheng Zhang, Cen Cui'), 'Man Chen, Zheng Zhang, Cen Cui')
  assert.equal(libraryAuthorPreview('Noah Hollmann, Samuel Müller, Lennart Purucker, Arjun Krishnakumar, Max Körfer'), 'Noah Hollmann, Samuel Müller, Lennart Purucker, et al.')
  assert.equal(libraryAuthorPreview('Xiaoyu Yang, Liyang Xie, Yaoyao Liu, et al'), 'Xiaoyu Yang, Liyang Xie, Yaoyao Liu, et al.')
  assert.equal(libraryAuthorPreview('杨小玉，谢里阳，杨奕凤，赵丙峰'), '杨小玉、谢里阳、杨奕凤 等')
  assert.equal(libraryAuthorPreview('A; B; C; D'), 'A, B, C, et al.')
  assert.equal(libraryAuthorPreview('A and B'), 'A and B')
})

test('real card titles render math as inline content inside headings', () => {
  for (const source of [
    'Estimation of $R = P ( Y < X )$ for three-parameter Weibull distribution',
    '威布尔分布下小样本 $P - S - N$ 曲线拟合方法',
    'Estimating the parameters of $3 - p$ Weibull distribution',
    String.raw`An estimator for \(\beta\)`,
    'A title with $$x^2$$',
  ]) {
    const html = render(source)
    assert.equal((html.match(/class="katex"/g) || []).length, 1, source)
    assert.doesNotMatch(html, /<(?:div|p)(?:\s|>)|katex-error/, source)
    assert.ok(html.startsWith('<h3><span'))
  }
})

test('inline title highlighting preserves math and avoids nested links or unsafe HTML', () => {
  const html = render('Weibull $\\text{Weibull}$ [source](https://example.test) <img src=x onerror=alert(1)>', { highlightTerms: ['Weibull'] })
  assert.equal((html.match(/<mark /g) || []).length, 1)
  assert.equal((html.match(/class="katex"/g) || []).length, 1)
  assert.doesNotMatch(html, /<a\b|<img\b|onerror=|<p\b|<div\b/)
  const block = renderToStaticMarkup(React.createElement(LibraryMathMarkdown, null, 'One paragraph.\n\nAnother.'))
  assert.ok(block.startsWith('<div'))
  assert.equal((block.match(/<p>/g) || []).length, 2)
})

test('metadata keeps fixed icon slots, preserves identity/year and names missing fields honestly', () => {
  const html = renderToStaticMarkup(React.createElement('div', null,
    React.createElement(LibraryCardMetadata, { id: '182-119', type: '期刊', publication: 'Statistics & Probability Letters', year: 2009, available: true }),
    React.createElement(LibraryCardMetadata, { id: '421-001', type: '书籍', year: 0, available: false })))
  assert.equal((html.match(/<button /g) || []).length, 4)
  assert.equal((html.match(/role="tooltip"/g) || []).length, 4)
  assert.equal(new Set(Array.from(html.matchAll(/aria-describedby="([^"]+)"/g), match => match[1])).size, 4)
  assert.match(html, /182-119/)
  assert.match(html, /发表年份：2009/)
  assert.match(html, /期刊 · Statistics &amp; Probability Letters/)
  assert.match(html, /未登记DOI/)
  assert.match(html, /未登记出版信息/)
  assert.match(html, /发表年份：未登记/)
  assert.doesNotMatch(html, /<a\b|disabled=/)
})

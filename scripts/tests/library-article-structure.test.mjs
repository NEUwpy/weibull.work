import test from 'node:test'
import assert from 'node:assert/strict'
import { compileLibraryMarkdown } from '../../src/lib/library-markdown-compiler.mjs'

const article = '# Paper title\n\nAuthor, University\n\n## Abstract\n\nActual abstract with $x^2$ and citation [1].\n\nKeywords: Weibull\n\n## 1. Introduction\n\nScientific body.\n\n## References\n\n[1] A source.\n'
const errors = result => result.diagnostics.filter(item => item.severity === 'error')

test('the shared reader starts at the abstract and renders one semantic frame with source anchors intact', async () => {
  const result = await compileLibraryMarkdown(article, { requireAbstract: true })
  assert.deepEqual(errors(result), [])
  assert.match(result.html, /<section class="library-abstract" aria-label="Abstract">/)
  assert.match(result.html, /id="abstract"/)
  assert.match(result.html, /id="passage-7"/)
  assert.match(result.html, /katex/)
  assert.match(result.html, /href="#ref-1"/)
  assert.doesNotMatch(result.html, /Paper title|Author, University/)
  assert.match(result.html, /<\/section>\s*<p[^>]*>Keywords:/)
  assert.ok(result.html.indexOf('library-abstract') < result.html.indexOf('1. Introduction'))
})

test('strict article compilation rejects missing, empty, misplaced or abstract-only documents', async () => {
  for (const [body, code] of [
    ['# Paper\n\n## 1. Introduction\n\nBody.', 'article.abstract-missing'],
    ['# Paper\n\nAbstract: Inline abstract.\n\n## 1. Introduction\n\nBody.', 'article.abstract-format'],
    ['## 摘要\n\n## 关键词\n\n威布尔\n\n## 1 引言\n\n正文', 'article.abstract-empty'],
    ['# Paper\n\n## 1. Introduction\n\nBody.\n\n## Abstract\n\nAbstract.\n\n## 2. Methods\n\nBody.', 'article.before-abstract'],
    ['# Paper\n\n## Abstract\n\nAbstract only.', 'article.body-missing'],
  ]) {
    const result = await compileLibraryMarkdown(body, { requireAbstract: true })
    assert.ok(errors(result).some(item => item.code === code), JSON.stringify(result.diagnostics))
  }
})

test('publisher controls and pre-abstract icons fail with original file lines and actionable reasons', async () => {
  const raw = '---\ntitle: Paper\n---\n# Paper\n\n![publisher icon](icon.jpg)\n\nView supplementary material\n\n' + article.slice(article.indexOf('## Abstract'))
  const result = await compileLibraryMarkdown(raw, { requireAbstract: true })
  const chrome = errors(result).find(item => item.code === 'article.publisher-chrome')
  assert.equal(chrome.line, 8)
  assert.equal(chrome.excerpt, 'View supplementary material')
  assert.match(chrome.message, /删除/)
  assert.ok(errors(result).some(item => item.code === 'article.before-abstract' && item.line === 6))
})

test('control labels in prose, code, quotations and bibliography are not mistaken for publisher UI', async () => {
  const raw = article.replace('Scientific body.', 'Scientific body. Supplementary material is available with data and code.\n\nThe study reports article views: 54 as a measurement.\n\n> Check for updates\n\n```text\nSubmit your article to this journal\n```')
    .replace('[1] A source.', '[1] Paper. Published online: 2026.')
  assert.deepEqual(errors(await compileLibraryMarkdown(raw, { requireAbstract: true })), [])
})

test('books and partial Markdown compile without a fabricated abstract while Chinese abstracts get the shared frame', async () => {
  assert.deepEqual(errors(await compileLibraryMarkdown('# Chapter\n\nContent.')), [])
  const book = await compileLibraryMarkdown('---\ntype: 书籍\n---\n# Book\n\n## Chapter One\n\nEarlier chapter.\n\n## Abstract\n\nA later chapter abstract.\n\n## Chapter Two\n\nContent.')
  assert.match(book.html, /Earlier chapter/)
  const result = await compileLibraryMarkdown('# 标题\n\n作者\n\n## 摘要\n\n原论文摘要。\n\n### 研究目的\n\n结构化摘要内容。\n\n## 1 引言\n\n正文。', { requireAbstract: true })
  assert.deepEqual(errors(result), [])
  assert.match(result.html, /class="library-abstract" aria-label="摘要"/)
  assert.match(result.html, /研究目的/)
})

test('legacy Chinese inline abstracts use the shared frame and keep original passage anchors', async () => {
  const raw = '# 中文题名\n\n作者\n\n**摘 要：** 实际摘要 $x^2$。\n\n关键词：威布尔\n\n# English title\n\nAbstract: English abstract.\n\nKey words: Weibull\n\n# 1 正文\n\n正文内容。'
  const result = await compileLibraryMarkdown(raw, { requireAbstract: true })
  assert.deepEqual(errors(result).map(({ code, line }) => [code, line]), [['article.abstract-format', 5], ['article.abstract-format', 11]])
  assert.match(result.html, /<section class="library-abstract" aria-label="摘要"><h2>摘要<\/h2>\s*<p id="passage-5">[\s\S]*?katex[\s\S]*?<\/section>\s*<p[^>]*>关键词：威布尔/)
  assert.match(result.html, /<section class="library-abstract" aria-label="Abstract"><h2>Abstract<\/h2>\s*<p id="passage-11">English abstract\.<\/p>/)
  assert.match(result.html, /<\/section>[\s\S]*<p id="passage-17">正文内容。/)
  assert.doesNotMatch(result.html, /中文题名|摘 要：/)
})

test('numbered Chinese affiliation lines are front matter while real pre-abstract content stays visible for review', async () => {
  const raw = '# 中文题名\n\n（1. 某大学机械学院；\n\n2. 某大学重点实验室）\n\n## 摘要\n\n实际摘要。\n\n## 1 引言\n\n正文。'
  const valid = await compileLibraryMarkdown(raw, { requireAbstract: true })
  assert.deepEqual(errors(valid), [])
  assert.match(valid.html, /^<section class="library-abstract"/)
  const invalid = await compileLibraryMarkdown(raw.replace('2. 某大学重点实验室）', '## 已提前出现的正文\n\n这段内容应保留供核对。'), { requireAbstract: true })
  assert.ok(errors(invalid).some(item => item.code === 'article.before-abstract' && item.line === 5))
  assert.match(invalid.html, /这段内容应保留供核对。/)
})

test('legacy OCR labels preserve abstract text with bracketed, spaced or standalone formatting', async () => {
  for (const label of ['【摘要】实际摘要。', '摘 要 实际摘要。', '**摘要**\n\n实际摘要。', 'Abstract — 实际摘要。']) {
    const result = await compileLibraryMarkdown(`# 标题\n\n${label}\n\n关键词 威布尔\n\n## 1 引言\n\n正文。`, { requireAbstract: true })
    assert.deepEqual(errors(result).map(item => item.code), ['article.abstract-format'])
    assert.match(result.html, /<section class="library-abstract"[\s\S]*实际摘要。\s*<\/p>\s*<\/section>\s*<p[^>]*>关键词 威布尔/)
  }
})

test('abstract rules check the title level, separate keywords and require substantive body after both abstracts', async () => {
  const legacy = await compileLibraryMarkdown('# 摘要\n\n实际摘要。\n\n## 1 引言\n\n正文。', { requireAbstract: true })
  assert.deepEqual(errors(legacy).map(item => item.code), ['article.abstract-format'])
  assert.match(legacy.html, /<\/section>\s*<h2[^>]*>1 引言/)

  for (const body of [
    '## Abstract\n\nActual abstract.\n\n## Methods\n\n## References\n\n[1] Source.',
    '## 摘要\n\n中文摘要内容。\n\n# English Title\n\nAuthor\n\n## Abstract\n\nEnglish abstract.\n\nKeywords: Weibull\n\n## 致谢\n\n致谢。',
  ]) {
    assert.ok(errors(await compileLibraryMarkdown(body, { requireAbstract: true })).some(item => item.code === 'article.body-missing'))
  }
  const keywords = await compileLibraryMarkdown('## ABSTRACT\n\nActual abstract.\n\nKEYWORDS Weibull; reliability\n\n## 1. Introduction\n\nBody.', { requireAbstract: true })
  assert.deepEqual(errors(keywords), [])
  assert.match(keywords.html, /<\/section>\s*<p[^>]*>KEYWORDS Weibull/)
})

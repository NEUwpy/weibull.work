import test from 'node:test'
import assert from 'node:assert/strict'
import { compileLibraryMarkdown } from '../../src/lib/library-markdown-compiler.mjs'
import { processLibraryContent, getLibraryMarkdownOptions, LIBRARY_RENDERER_VERSION } from '../../src/lib/library-markdown.ts'

test('round numeric citations require an explicit style and exclude equations and math', async () => {
  const body = '# Paper\n\nSource (1), source（2）, Eq. (1), Table (2), year (2023), `$x(1)$`, $x(1)$. Neural differential equations (1, 2).\n\n## References\n\n1. First source.\n2. Second source.\n'
  const normal = await compileLibraryMarkdown(body)
  assert.equal(normal.citations.length, 0)
  const enabled = await compileLibraryMarkdown('---\ncitation_style: numeric-parentheses\n---\n' + body)
  assert.deepEqual(enabled.citations.map(c => c.id), ['1', '2', '1', '2'])
  assert.ok(enabled.html.includes('href="#ref-1"'))
  assert.ok(enabled.html.includes('Eq. (1)'))
  assert.ok(enabled.html.includes('year (2023)'))
})

test('citations never rewrite valid formulas, code, image text or existing links', async () => {
  const raw = String.raw`# Article

Prose [1-2,4]. Again [2]. $x \in [1,2]$ and $[4]$.

\`[1]\` [1](https://example.org/[2]) ![[2]](image.png)

\`\`\`text
[1]
## References
\`\`\`

<code>[2]</code> <a href="/elsewhere">[4]</a>

## References
[1] First.
[2] Second.
[4] Fourth.
`.replaceAll('\\`', '`')
  const compiled = await compileLibraryMarkdown(raw)
  assert.equal(compiled.diagnostics.filter(item => item.severity === 'error').length, 0)
  assert.deepEqual(compiled.citations.map(item => item.id), ['1', '2', '4', '2'])
  assert.equal((compiled.html.match(/id="cite-2"/g) || []).length, 1)
  assert.match(compiled.html, /<code>\[1\]<\/code>/)
  assert.match(compiled.html, /href="https:\/\/example.org\/%5B2%5D"/)
  assert.match(compiled.html, /alt="\[2\]"/)
  assert.equal(compiled.counts.math, 2)
  assert.equal(compiled.referenceEntries.length, 3)
})

test('reference detection uses real standalone headings and retains later appendices', async () => {
  const raw = '# Article\n\nText mentions ## References in prose.\n\n## References\n[1] A.\ncontinued.\n[2] B.\n\n## Appendix\n\nKept $x^2$.\n'
  const processed = processLibraryContent(raw)
  assert.match(processed.body, /mentions ## References in prose/)
  assert.match(processed.body, /## Appendix/)
  assert.doesNotMatch(processed.body, /continued/)
  assert.equal(processed.referenceEntries[0].content, 'A.\ncontinued.')
  const compiled = await compileLibraryMarkdown(raw)
  assert.match(compiled.html, /id="appendix"/)
  assert.equal(compiled.counts.math, 1)
})

test('compiler returns actual KaTeX parse failures at original source lines', async () => {
  const raw = '---\ntitle: T\n---\n# Title\n\n$$\nx_\n$$\n\n## References\n[1] Ref.\n\n## Appendix\n\n$\\badcommand$\n'
  const compiled = await compileLibraryMarkdown(raw)
  const errors = compiled.diagnostics.filter(item => item.code === 'math.katex')
  assert.equal(errors.length, 2)
  assert.equal(errors[0].line, 6)
  assert.equal(errors[1].line, 15)
  assert.match(errors[0].message, /group after/)
  assert.match(compiled.html, /katex-error/)
})

test('same-line double-dollar display equations retain supported display tags', async () => {
  const compiled = await compileLibraryMarkdown('# T\n\n$$x = [1] \\tag{1}$$\n\n## References\n[1] A.\n')
  assert.equal(compiled.diagnostics.length, 0)
  assert.match(compiled.html, /katex-display/)
  assert.equal(compiled.citations.length, 0)
})

test('reference ranges create a backlink for every first-seen reference', async () => {
  const compiled = await compileLibraryMarkdown('# T\n\n[1-3]. [2]. [3].\n\n## References\n[1] A\n[2] B\n[3] C\n')
  for (const id of ['1', '2', '3']) assert.equal((compiled.html.match(new RegExp(`id="cite-${id}"`, 'g')) || []).length, 1)
  assert.match(compiled.html, /\[1\]<\/a>, <a[^>]+>\[2\]/)
  assert.equal(compiled.citations.length, 5)
})

test('unknown or descending bracket ranges remain text, rather than making broken anchors', async () => {
  const compiled = await compileLibraryMarkdown('# T\n\n[7] [2-1] [1].\n\n## References\n[1] A\n')
  assert.deepEqual(compiled.citations.map(item => item.id), ['1'])
  assert.equal(compiled.diagnostics[0].code, 'citation.missing-reference')
  assert.doesNotMatch(compiled.html, /href="#ref-7"/)
})

test('duplicate references fail and fullwidth/parenthesized markers resolve consistently', async () => {
  const compiled = await compileLibraryMarkdown('# T\n\n[1] [2] [3]\n\n## 参考文献\n［1］ First\n(2) Second\n3. Third\n[1] Duplicate\n')
  assert.equal(compiled.diagnostics.filter(item => item.code === 'reference.duplicate').length, 1)
  assert.deepEqual(compiled.citations.map(item => item.id), ['1', '2', '3'])
})

test('compiler and website options preserve GFM tables, images and intended captions', async () => {
  const compiled = await compileLibraryMarkdown('# T\n\nTable 1. Results\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\n![Figure](image.png)\n\nFig. 1 Caption\n\nOrdinary prose.\n')
  assert.equal(compiled.counts.tables, 1)
  assert.deepEqual(compiled.images, [{ url: 'image.png', line: 9 }])
  assert.match(compiled.html, /class="table-caption"/)
  assert.match(compiled.html, /class="figure-caption">Fig. 1 Caption/)
  assert.doesNotMatch(compiled.html, /class="figure-caption">Ordinary prose/)
})

test('TOC slugs follow the same Github duplicate and punctuation rules as rehype-slug', async () => {
  const raw = '# Same: heading\n\n# Same: heading\n\n```md\n# Fake heading\n```\n'
  const processed = processLibraryContent(raw)
  const compiled = await compileLibraryMarkdown(raw)
  assert.deepEqual(processed.headings.map(heading => heading.slug), ['same-heading', 'same-heading-1'])
  for (const heading of processed.headings) assert.match(compiled.html, new RegExp(`id="${heading.slug}"`))
})

test('bibliography formulas are actually rendered and errors identify their source line', async () => {
  const compiled = await compileLibraryMarkdown('# T\n\n[1].\n\n## References\n[1] Paper on $x^2$; [DOI](https://example.org).\n[2] Bad $x_$.\n')
  assert.equal(compiled.counts.math, 1)
  const error = compiled.diagnostics.find(item => item.code === 'math.katex')
  assert.equal(error.line, 7)
  assert.equal(error.excerpt, '[2] Bad $x_$.')
  assert.match(compiled.html, /id="ref-1"/)
  assert.match(compiled.html, /href="https:\/\/example.org"/)
})

test('an unterminated display fence fails rather than silently consuming the end of the paper', async () => {
  const compiled = await compileLibraryMarkdown('# T\n\n$$\nx^2\n')
  assert.ok(compiled.diagnostics.some(item => item.code === 'math.unclosed-display' && item.line === 3 && item.severity === 'error'))
})

test('Bibliography headings and TOC math keep their intended structure', async () => {
  const raw = '# A $x^2$ heading\n\n[1]\n\n## Bibliography\n[1] A.\n'
  const processed = processLibraryContent(raw)
  const compiled = await compileLibraryMarkdown(raw)
  assert.equal(processed.referenceEntries.length, 1)
  assert.equal(processed.headings[0].text, 'A $x^2$ heading')
  assert.match(compiled.html, new RegExp(`id="${processed.headings[0].slug}"`))
})

test('strict KaTeX failures remain errors even when fallback produces no katex-error class', async () => {
  const compiled = await compileLibraryMarkdown('# T\n\n$$\nx \\tag{1·3}\n$$\n')
  assert.equal(compiled.diagnostics.filter(item => item.code === 'math.katex').length, 1)
  assert.doesNotMatch(compiled.html, /class="katex-error"/)
  assert.match(compiled.diagnostics[0].message, /cdotp/)
})

test('unclosed single-dollar math fails while escaped currency and code examples pass', async () => {
  const broken = await compileLibraryMarkdown('# T\n\nAn equation $x + 1 has no closing delimiter.\n')
  assert.ok(broken.diagnostics.some(item => item.code === 'math.unmatched-delimiter' && item.severity === 'error' && item.line === 3))
  const valid = await compileLibraryMarkdown('# T\n\nPrice \\$5 and `$unclosed` is a code example.\n\n```text\n$unclosed\n```\n')
  assert.equal(valid.diagnostics.length, 0)
})

test('actual hard-break references from 421-003 render with observations and keep source anchors', async () => {
  // Original book lines 579-583. rehype-raw merges each generated hard-break newline
  // with the following reference text, leaving position.end but no position.start.
  const excerpt = 'References\n\n' +
    '[1] Birnbaum, Z.W. 1969. On the importance of different components in a multi-component system. In P.R. Krishnaiah, ed., Multivariate Analysis, pp. 581-592. Academic Press, San Diego, CA.  \n' +
    '[2] Modarres, M., M. Kaminskiy, and V. Krivtsov. 2010. Reliability Engineering and Risk Analysis. CRC Press, Boca Raton, FL.  \n' +
    '[3] Rausand, M. and A. Høyland. 2004. System Reliability Theory: Models, Statistical Methods, and Applications. 2nd ed. Wiley-Interscience, Hoboken, NJ.'
  const raw = '---\ntitle: Book excerpt\n---\n# Book\n\n' + excerpt + '\n\nFollowing paragraph [2].\n\n![Diagram](diagram.jpg)\n\n## References\n[1] First\n[2] Second\n[3] Third\n'
  const compiled = await compileLibraryMarkdown(raw)
  assert.equal(compiled.version, '1.1.1')
  assert.equal(compiled.version, LIBRARY_RENDERER_VERSION)
  assert.equal(compiled.diagnostics.filter(item => item.severity === 'error').length, 0)
  assert.deepEqual(compiled.citations.map(item => item.id), ['1', '2', '3', '2'])
  assert.match(compiled.html, /id="passage-6">References/)
  assert.match(compiled.html, /id="passage-8">/)
  assert.match(compiled.html, /id="passage-12">Following paragraph/)
  assert.equal((compiled.html.match(/<br\/>/g) || []).length, 2)
  assert.deepEqual(compiled.images, [{ url: 'diagram.jpg', line: 14 }])
  assert.doesNotMatch(compiled.html, /passage-(?:undefined|NaN|0)\b/)
})

test('generated paragraph nodes without a valid source start are skipped rather than claiming a passage', () => {
  const processed = processLibraryContent('---\ntitle: T\n---\nFirst paragraph.\n\nSecond paragraph.\n')
  const options = getLibraryMarkdownOptions(processed)
  const entry = options.rehypePlugins.find(plugin => Array.isArray(plugin) && plugin[0].name === 'rehypeLibraryPassages')
  const transform = entry[0](entry[1])
  const paragraph = position => ({ type: 'element', tagName: 'p', properties: {}, children: [], ...(position === undefined ? {} : { position }) })
  const generated = [paragraph(), paragraph({}), paragraph({ end: { line: 1 } }), paragraph({ start: {} }), paragraph({ start: { line: 0 } }), paragraph({ start: { line: NaN } })]
  const first = paragraph({ start: { line: 1 } })
  const second = paragraph({ start: { line: 3 } })
  transform({ type: 'root', children: [...generated, first, second] })
  assert.ok(generated.every(node => node.properties.id === undefined))
  assert.equal(first.properties.id, 'passage-4')
  assert.equal(second.properties.id, 'passage-6')
})

test('observations tolerate generated image nodes and KaTeX ancestors with partial positions', () => {
  const processed = processLibraryContent('---\ntitle: T\n---\nText.\n')
  const observation = { counts: { math: 0, tables: 0, headings: 0 }, images: [], diagnostics: [], citations: [] }
  const options = getLibraryMarkdownOptions(processed, observation)
  const entry = options.rehypePlugins.find(plugin => Array.isArray(plugin) && plugin[0].name === 'rehypeLibraryObserve')
  entry[0](entry[1])({ type: 'root', children: [
    { type: 'element', tagName: 'img', properties: { src: 'generated.jpg' }, position: { end: { line: 5 } } },
  ] }, { messages: [{ source: 'rehype-katex', reason: 'Example math error', ancestors: [
    { position: { start: { line: 8 } } }, { position: { end: { line: 9 } } },
  ] }] })
  assert.deepEqual(observation.images, [{ url: 'generated.jpg', line: 4 }])
  assert.equal(observation.diagnostics[0].line, 11)
})

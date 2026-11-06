import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import React from 'react'
import ts from 'typescript'
import * as jsxRuntime from 'react/jsx-runtime'

const LibraryDocumentProvider = () => null
const LibraryDocumentLink = () => null
const PageLink = () => null
const imports = {
  react: { ...React, useState: initial => [initial, () => {}] },
  'react/jsx-runtime': jsxRuntime,
  'next/link': PageLink, 'react-markdown': () => null,
  'lucide-react': Object.fromEntries(['Copy', 'Check', 'Download', 'ArrowLeft', 'ArrowUpRight', 'ChevronLeft', 'ChevronRight', 'BookOpen', 'Loader2', 'X'].map(name => [name, () => null])),
  '@/components/library/LibraryDocumentDialog': { LibraryDocumentProvider, LibraryDocumentLink },
  '@/components/shared/CatalogSearchForm': {}, '@/components/shared/LibraryMathMarkdown': { LibraryMathMarkdown: () => null },
  '@/components/shared/usePreviewDialog': {}, '@/lib/library-preview-history': {},
  '@/lib/library-markdown': {},
  '@/lib/case-datasets': { natureLabels: { observed: '实测数据' }, observationLabels: { complete: '完整样本' } },
}
function load(file, extra = '') {
  const module = { exports: {} }
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8') + extra, { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText, { module, exports: module.exports, require: name => {
    if (name.endsWith('.css')) return {}
    if (!(name in imports)) throw new Error('Unexpected import: ' + name)
    return imports[name]
  } }, { filename: file })
  return module.exports
}
function descendants(element) {
  if (!element || typeof element !== 'object') return []
  return [element, ...React.Children.toArray(element.props?.children).flatMap(descendants)]
}

test('the cases route supplies the shared paper preview context without replacing its children', () => {
  const { default: CasesLayout } = load('src/app/cases/layout.tsx')
  const children = React.createElement('main', null, '案例目录与当前样本')
  const layout = CasesLayout({ children })
  assert.equal(layout.type, LibraryDocumentProvider)
  assert.equal(layout.props.children, children)
  assert.equal(layout.props.returnLabel, '返回案例')
})

test('case source papers and original references use the shared preview link, preserving the original version', () => {
  const { DatasetDetails } = load('src/app/cases/page.tsx', '\nexport { DatasetDetails };')
  const view = DatasetDetails({ record: {
    id: 'sample', name: '第二批试件', data: [10, 20, 30],
    nature: { kind: 'observed', observation: 'complete' },
    sources: [{ paper_id: '182-029', title: '来源论文', location: '表1', relation: 'secondary', original_paper_id: '181-001' }],
    legacy_href: '/cases/c1',
  } })
  const links = descendants(view).filter(node => typeof node.props?.href === 'string')
  const sources = links.filter(node => node.props.href.startsWith('/library/'))
  assert.equal(sources.length, 2)
  assert.ok(sources.every(node => node.type === LibraryDocumentLink))
  assert.equal(sources[0].props.href, '/library/182-029?version=' + encodeURIComponent('原文'))
  assert.equal(sources[1].props.href, '/library/181-001')
  assert.ok(links.some(node => node.props.href === '/cases/c1' && node.type === PageLink))
})

test('an external data source keeps its explicit new-tab behaviour', () => {
  const { DatasetDetails } = load('src/app/cases/page.tsx', '\nexport { DatasetDetails };')
  const view = DatasetDetails({ record: { id: 'external', name: '外部数据',
    data: { kind: 'external', description: '原始数据', url: 'https://example.test/data' },
    nature: { kind: 'observed', observation: 'complete' }, sources: [],
  } })
  const link = descendants(view).find(node => node.props?.href === 'https://example.test/data')
  assert.equal(link.type, 'a')
  assert.equal(link.props.target, '_blank')
})

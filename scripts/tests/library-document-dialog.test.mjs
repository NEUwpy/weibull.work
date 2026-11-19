import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import React from 'react'
import ts from 'typescript'
import { isLibraryPreviewHref, libraryEntityDirectories, libraryEntityPreviewKind } from '../../src/lib/library-preview-history.ts'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { createLibraryDirectoryIndex } = loadServerModule('src/lib/library-directory-index.ts')

function loadComponent(file, imports, globals = {}) {
  const module = { exports: {} }
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText, { module, exports: module.exports, require: name => {
    if (!(name in imports)) throw new Error('Unexpected import: ' + name)
    return imports[name]
  }, URL, URLSearchParams, ...globals }, { filename: file })
  return module.exports
}

function harness() {
  const states = [], refs = [], listeners = new Map(), opened = []
  let index = 0, refIndex = 0, active = true, mounted = false
  const hooks = { ...React, useContext: () => href => opened.push(href),
    useState: initial => { const key = index++; if (!(key in states)) states[key] = initial
      return [states[key], value => { states[key] = typeof value === 'function' ? value(states[key]) : value }] },
    useRef: initial => refs[refIndex++] ||= { current: initial },
    useEffect: callback => { if (!mounted) callback() },
    useMemo: factory => factory(),
    useCallback: callback => callback,
  }
  const imports = {
    react: hooks, 'next/link': () => null, 'next/dynamic': () => () => null,
    'next/navigation': { usePathname: () => '/library' }, 'lucide-react': { Expand: () => null },
    '@/lib/library-chat-session': { setLibraryChatActive: value => { active = value } },
    './LibraryPreviewDialog': { LibraryPreviewDialog: () => null },
    './LibraryEntityDialog': { LibraryEntityDialog: () => null },
    '@/lib/library-directory-index': { createLibraryDirectoryIndex },
    '@/lib/library-authors': { libraryAuthorPreviewHref: name => `/library?author=${encodeURIComponent(name)}` },
    './LibraryAuthors': { LibraryAuthorContext: React.createContext(null) },
    '@/lib/library-institutions': { libraryInstitutionPreviewHref: name => `/library?institution=${encodeURIComponent(name)}` },
    './LibraryInstitutions': { LibraryInstitutionContext: React.createContext(null) },
    '@/lib/library-preview-history': { isLibraryPreviewHref, libraryEntityDirectories, libraryEntityPreviewKind, createLibraryPreviewHistory: (_window, onChange) => {
      let trail = []
      const change = next => { trail = next; onChange(trail.at(-1) || null, trail) }
      return { currentHref: () => trail.at(-1) ?? null,
        open: href => change([...trail.slice(0, -1), href]), push: href => change([...trail, href]),
        close: () => change(trail.slice(0, -1)), leave: () => change([]), restore: () => change(trail), dispose() {} }
    } },
  }
  const exports = loadComponent('src/components/library/LibraryDocumentDialog.tsx', imports, {
    window: { location: new URL('http://library.local/library'), addEventListener: (name, handler) => listeners.set(name, handler), removeEventListener() {} },
  })
  return { link: props => exports.LibraryDocumentLink(props), opened,
    render: (props = {}) => { index = 0; refIndex = 0; const view = exports.LibraryDocumentProvider({ children: 'original window', ...props }); mounted = true; return view },
    home: detail => listeners.get('weibull:module-home')({ detail }), active: () => active }
}
function click(patch = {}) {
  return { button: 0, defaultPrevented: false, preventDefault() { this.defaultPrevented = true }, ...patch }
}

function content(view) {
  return view.props.children.props.children.props.children.props.children
}

test('ordinary document clicks open a preview without changing the real link or navigating', () => {
  const app = harness()
  const href = '/library/182-046?version=%E5%8E%9F%E6%96%87#passage-59'
  const link = app.link({ href, children: 'source' })
  const event = click()
  link.props.onClick(event)
  assert.equal(link.props.href, href)
  assert.equal(event.defaultPrevented, true)
  assert.deepEqual(app.opened, [href])
})

test('modified, cancelled and non-document links retain normal browser behaviour', () => {
  const app = harness()
  for (const patch of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }, { defaultPrevented: true }]) {
    app.link({ href: '/library/182-046' }).props.onClick(click(patch))
  }
  app.link({ href: '/library/182-046', target: '_blank' }).props.onClick(click())
  app.link({ href: '/library' }).props.onClick(click())
  app.link({ href: 'https://example.test/library/182-046' }).props.onClick(click())
  app.link({ href: '/library/182-046', onClick: event => event.preventDefault() }).props.onClick(click())
  assert.deepEqual(app.opened, [])
})

test('journal links use the preview stack and return through the journal to the source paper', () => {
  const app = harness()
  const journal = '/library?view=journals&journal=nature'
  const article = '/library/182-046'
  const previewLink = app.link({ href: journal })
  previewLink.props.onClick(click({ ctrlKey: true }))
  assert.deepEqual(app.opened, [])
  previewLink.props.onClick(click())
  assert.deepEqual(app.opened, [journal])

  const layers = () => content(app.render())[1]
  app.render().props.value(article)
  app.render().props.value(journal)
  assert.equal(layers()[1].props.backLabel, '返回文献')
  app.render().props.value('/library/182-025')
  assert.equal(layers()[2].props.backLabel, '返回期刊')
  layers()[2].props.onClose()
  assert.equal(layers().at(-1).props.href, journal)
  layers()[1].props.onClose()
  assert.equal(layers().at(-1).props.href, article)
})

test('closing a preview retains the original window; Logo explicitly resets to the module home', () => {
  const app = harness()
  let view = app.render()
  const originalKey = content(view)[0].key
  view.props.value('/library/182-046')
  view = app.render()
  assert.equal(content(view)[1][0].props.href, '/library/182-046')
  content(view)[1][0].props.onClose()
  view = app.render()
  assert.equal(content(view)[0].key, originalKey)
  assert.equal(content(view)[1].length, 0)
  assert.equal(app.active(), true)
  app.home('/ai')
  assert.equal(content(app.render())[0].key, originalKey)
  app.home('/library')
  assert.notEqual(content(app.render())[0].key, originalKey)
  assert.equal(app.active(), false)
})

test('nested previews label their return destination and retain the previous layer on close', () => {
  const app = harness()
  let view = app.render()
  view.props.value('/library/181-004')
  view = app.render()
  view.props.children.props.value('Xiaoyu Yang', '181-004')
  view = app.render()
  let layers = content(view)[1]
  assert.equal(layers[1].props.backLabel, '返回文献')
  view.props.value('/library/182-025')
  layers = content(app.render())[1]
  assert.equal(layers[2].props.backLabel, '返回作者')
  layers[2].props.onClose()
  layers = content(app.render())[1]
  assert.equal(layers.length, 2)
  assert.equal(layers[1].props.backLabel, '返回文献')
  view = app.render()
  view.props.children.props.children.props.value('东北大学')
  view = app.render()
  layers = content(view)[1]
  assert.equal(layers[2].props.backLabel, '返回作者')
  view.props.value('/library/182-046')
  layers = content(app.render())[1]
  assert.equal(layers[3].props.backLabel, '返回单位')
})

test('the first paper preview can identify the case underneath as its return destination', () => {
  const app = harness()
  app.render({ returnLabel: '返回案例' }).props.value('/library/182-010?version=原文')
  const layers = content(app.render({ returnLabel: '返回案例' }))[1]
  assert.equal(layers[0].props.backLabel, '返回案例')
})

test('author, institution and journal previews render indexed papers immediately without a fetch', () => {
  const catalog = [{ slug: 'example', year: 2025, author: 'Example Author', affiliation: 'Example University', type: '期刊', publication: 'Nature' }]
  const options = { catalog }

  const LibraryCollectionDetails = () => null
  const LibraryJournalDetails = () => null
  const { LibraryEntityDialog } = loadComponent('src/components/library/LibraryEntityDialog.tsx', {
    react: { ...React, useState: initial => [initial, () => {}], useEffect: run => run() },
    'lucide-react': { ArrowUpRight: () => null },
    '@/lib/library-preview-history': { libraryEntityPreviewKind },
    './LibraryDocumentDialog': { LibraryDocumentLink: () => null },
    './LibraryInstitutions': { LibraryInstitutions: () => null },
    './LibraryPreviewDialog': { LibraryPreviewDialog: () => null },
    './LibraryJournalDetails': { LibraryJournalDetails },
    './LibraryCollectionDetails': { LibraryCollectionDetails },
    './LibraryAuthorshipLinks': { LibraryAuthorInstitutionLinks: () => null, LibraryInstitutionAuthorLinks: () => null },
  }, { AbortController, fetch: () => assert.fail('indexed collection details should not request the API') })

  for (const [kind, key, title] of [
    ['author', 'Example Author', 'Example Author'],
    ['institution', 'Example University', 'Example University'],
    ['journal', 'nature', 'Nature'],
  ]) {
    const app = harness()
    app.render(options).props.value(`/library?${new URLSearchParams({ [kind]: key })}`)
    const [layer] = content(app.render(options))[1]
    const view = LibraryEntityDialog(layer.props)
    if (kind === 'journal') {
      assert.equal(view.props.children.type, LibraryJournalDetails)
      assert.equal(view.props.children.props.journal.name, title)
      assert.equal(view.props.children.props.papers[0], catalog[0])
    } else {
      const details = view.props.children.props.children.find(child => child?.type === LibraryCollectionDetails)
      assert.equal(details.props.title, title)
      assert.equal(details.props.papers[0], catalog[0])
      if (kind === 'author') assert.equal(details.props.children[0].props.author.affiliations[0].name, 'Example University')
    }
  }
})

test('the directory index shares memberships with journal and problem counts and deduplicates parent groups', () => {
  const common = { author: 'Example Author', type: '期刊' }
  const catalog = [
    { ...common, slug: 'old', year: 2021, affiliation: '东北大学机械工程与自动化学院',
      publication: 'Reliability Engineering and System Safety', tags: ['problem:theory-02'] },
    { ...common, slug: 'new', year: 2025, affiliation: '东北大学；东北大学机械工程与自动化学院',
      publication: 'Reliability Engineering & System Safety 183: 116-127', tags: ['problem:theory', 'problem:theory-02', 'problem:theory-01'] },
    { ...common, slug: 'book', year: 2026, type: '书籍', publication: 'Reliability Engineering and System Safety', tags: [] },
  ]
  const index = createLibraryDirectoryIndex(catalog)
  const ids = papers => Array.from(papers, paper => paper.slug)
  assert.equal(index.journals[0].count, 2)
  assert.deepEqual(ids(index.findEntity('journal', index.journals[0].key).papers), ['new', 'old'])
  assert.deepEqual(ids(index.findEntity('institution', 'Northeastern University').papers), ['new', 'old'])
  assert.deepEqual(ids(index.problemPapers.get('theory')), ['new', 'old'])
  assert.deepEqual(ids(index.problemPapers.get('theory-02')), ['new', 'old'])
  assert.deepEqual(ids(index.problemPapers.get('theory-01')), ['new'])
  assert.equal(index.problemGroups.find(group => group.key === 'theory').count, 2)
})

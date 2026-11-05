import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import React from 'react'
import ts from 'typescript'

function harness() {
  const states = [], refs = [], listeners = new Map(), opened = []
  let index = 0, refIndex = 0, active = true, mounted = false
  const hooks = { ...React, useContext: () => href => opened.push(href),
    useState: initial => { const key = index++; if (!(key in states)) states[key] = initial
      return [states[key], value => { states[key] = typeof value === 'function' ? value(states[key]) : value }] },
    useRef: initial => refs[refIndex++] ||= { current: initial },
    useEffect: callback => { if (!mounted) callback() },
  }
  const module = { exports: {} }
  const imports = {
    react: hooks, 'next/link': () => null, 'next/dynamic': () => () => null,
    'next/navigation': { usePathname: () => '/library' }, 'lucide-react': { Expand: () => null, X: () => null },
    '@/lib/library-chat-session': { setLibraryChatActive: value => { active = value } }, './dialog.css': {},
    '@/components/shared/usePreviewDialog': {},
    '@/lib/library-authors': { libraryAuthorPreviewHref: name => `/library?author=${encodeURIComponent(name)}` },
    './LibraryAuthors': { LibraryAuthorContext: React.createContext(null) },
    '@/lib/library-institutions': { libraryInstitutionPreviewHref: name => `/library?institution=${encodeURIComponent(name)}` },
    './LibraryInstitutions': { LibraryInstitutionContext: React.createContext(null) },
    '@/lib/library-preview-history': { createLibraryPreviewHistory: (_window, onChange) => {
      let trail = []
      const change = next => { trail = next; onChange(trail.at(-1) || null, trail) }
      return { open: href => change([...trail.slice(0, -1), href]), push: href => change([...trail, href]),
        close: () => change(trail.slice(0, -1)), leave: () => change([]), restore: () => change(trail), dispose() {} }
    } },
  }
  const file = 'src/components/library/LibraryDocumentDialog.tsx'
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText, { module, exports: module.exports, require: name => {
    if (!(name in imports)) throw new Error('Unexpected import: ' + name)
    return imports[name]
  }, URL, window: { addEventListener: (name, handler) => listeners.set(name, handler), removeEventListener() {} } }, { filename: file })
  return { link: props => module.exports.LibraryDocumentLink(props), opened,
    render: () => { index = 0; refIndex = 0; const view = module.exports.LibraryDocumentProvider({ children: 'original window' }); mounted = true; return view },
    home: detail => listeners.get('weibull:module-home')({ detail }), active: () => active }
}
function click(patch = {}) {
  return { button: 0, defaultPrevented: false, preventDefault() { this.defaultPrevented = true }, ...patch }
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

test('closing a preview retains the original window; Logo explicitly resets to the module home', () => {
  const app = harness()
  let view = app.render()
  const content = view => view.props.children.props.children.props.children
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
  let layers = view.props.children.props.children.props.children[1]
  assert.equal(layers[1].props.backLabel, '返回文献')
  view.props.value('/library/182-025')
  layers = app.render().props.children.props.children.props.children[1]
  assert.equal(layers[2].props.backLabel, '返回作者')
  layers[2].props.onClose()
  layers = app.render().props.children.props.children.props.children[1]
  assert.equal(layers.length, 2)
  assert.equal(layers[1].props.backLabel, '返回文献')
  view = app.render()
  view.props.children.props.children.props.value('东北大学')
  view = app.render()
  layers = view.props.children.props.children.props.children[1]
  assert.equal(layers[2].props.backLabel, '返回作者')
  view.props.value('/library/182-046')
  layers = app.render().props.children.props.children.props.children[1]
  assert.equal(layers[3].props.backLabel, '返回单位')
})

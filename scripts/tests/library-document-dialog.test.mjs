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
    '@/lib/library-preview-history': { createLibraryPreviewHistory: (_window, onChange) => ({
      open: onChange, close: () => onChange(null), leave: () => onChange(null), dispose() {},
    }) },
  }
  const file = 'src/components/library/LibraryDocumentDialog.tsx'
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText, { module, exports: module.exports, require: name => {
    if (!(name in imports)) throw new Error('Unexpected import: ' + name)
    return imports[name]
  }, window: { addEventListener: (name, handler) => listeners.set(name, handler), removeEventListener() {} } }, { filename: file })
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
  const originalKey = view.props.children[0].key
  view.props.value('/library/182-046')
  view = app.render()
  assert.equal(view.props.children[1].props.href, '/library/182-046')
  view.props.children[1].props.onClose()
  view = app.render()
  assert.equal(view.props.children[0].key, originalKey)
  assert.equal(view.props.children[1], null)
  assert.equal(app.active(), true)
  app.home('/ai')
  assert.equal(app.render().props.children[0].key, originalKey)
  app.home('/library')
  assert.notEqual(app.render().props.children[0].key, originalKey)
  assert.equal(app.active(), false)
})

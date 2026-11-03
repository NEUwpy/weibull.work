import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import React from 'react'

// Exercise the actual card's pointer handlers with a clock, without simulating a browser/device.
function cardHarness() {
  const refs = [], states = [], timers = new Map()
  let refIndex = 0, stateIndex = 0, now = 0, nextTimer = 0
  const hooks = { ...React,
    useRef: initial => refs[refIndex++] ||= { current: initial },
    useState: initial => { const index = stateIndex++; if (!(index in states)) states[index] = initial
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value }] },
    useCallback: value => value, useEffect() {}, useLayoutEffect() {}, useId: () => 'card-content',
  }
  const module = { exports: {} }
  const imports = {
    react: hooks, 'next/link': () => null, 'lucide-react': { ChevronDown: () => null, ChevronUp: () => null, User: () => null },
    '@/lib/library-card-presentation': { libraryAuthorPreview: value => value },
    '@/components/shared/LibraryMathMarkdown': { LibraryMathMarkdown: () => null },
    './LibraryCardMetadata': { LibraryCardMetadata: () => null },
    '@/lib/utils': { cn: (...values) => values.filter(Boolean).join(' ') },
  }
  const file = 'src/components/library/LibraryCard.tsx'
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText, { module, exports: module.exports, require: name => {
    if (!(name in imports)) throw new Error('Unexpected import: ' + name)
    return imports[name]
  }, document: { querySelector: () => null }, window: { innerHeight: 900 }, Date: { now: () => now },
  setTimeout: (fn, delay) => { timers.set(++nextTimer, { fn, due: now + delay }); return nextTimer },
  clearTimeout: id => timers.delete(id) }, { filename: file })
  const paper = { slug: '182-103', title: 'Weibull', author: 'Author', year: 2026, summary: 'The full public note summary.',
    tags: ['one', 'two', 'three', 'four', 'one'], availableVersions: ['原文'] }
  const render = () => { refIndex = 0; stateIndex = 0
    const element = module.exports.LibraryCard({ paper })
    element.ref.current = { getBoundingClientRect: () => ({ height: 320, top: 400 }) }
    return element
  }
  const advance = ms => { now += ms
    for (const [id, timer] of timers) if (timer.due <= now) { timers.delete(id); timer.fn() } }
  render()
  return { render, advance }
}
const pointer = (type = 'touch', x = 20, y = 30) => ({ pointerType: type, clientX: x, clientY: y, target: { closest: () => null } })
function descendants(element) {
  if (!element || typeof element !== 'object') return []
  return [element, ...React.Children.toArray(element.props?.children).flatMap(descendants)]
}

test('hover waits briefly, reveals extra tags in the card flow and closes after leaving', () => {
  const { render, advance } = cardHarness()
  let card = render()
  const extras = element => descendants(element).find(node => node.props.className === 'library-card-extra-tags')
  assert.equal(extras(card).props['aria-hidden'], true)
  card.props.onPointerEnter(pointer('mouse'))
  advance(219); assert.equal(render().props['data-expanded'], undefined)
  advance(1); card = render()
  assert.equal(card.props['data-expanded'], true)
  assert.equal(card.props.style, undefined)
  assert.equal(extras(card).props['aria-hidden'], false)
  const summary = descendants(card).find(node => node.props.className?.split(' ').includes('library-card-summary'))
  assert.equal(summary.props.children, 'The full public note summary.')
  assert.doesNotMatch(summary.props.className, /line-clamp/)
  card.props.onPointerLeave(pointer('mouse'))
  advance(119); assert.equal(render().props['data-expanded'], true)
  advance(1); assert.equal(render().props['data-expanded'], undefined)
})

test('touch hold opens without navigating, but a short tap, pan or cancelled gesture does not open', () => {
  for (const interrupt of [card => card.props.onPointerUp(), card => card.props.onPointerCancel(),
    card => card.props.onPointerMove(pointer('touch', 35, 30))]) {
    const { render, advance } = cardHarness()
    const card = render()
    card.props.onPointerDown(pointer()); advance(200); interrupt(card); advance(500)
    assert.equal(render().props['data-expanded'], undefined)
  }
  const { render, advance } = cardHarness()
  let card = render()
  card.props.onPointerDown(pointer()); advance(479)
  assert.equal(render().props['data-expanded'], undefined)
  advance(1); card = render(); assert.equal(card.props['data-expanded'], true)
  advance(10000) // Holding longer than the click grace period must still never navigate on release.
  card.props.onPointerUp()
  let prevented = false, stopped = false
  card.props.onClickCapture({ clientX: 20, clientY: 30, preventDefault: () => { prevented = true }, stopPropagation: () => { stopped = true } })
  assert.equal(prevented && stopped, true)
  advance(500); assert.equal(render().props['data-expanded'], true)
})

test('the explicit control supports opening and closing without pointer timing', () => {
  const { render } = cardHarness()
  const control = element => descendants(element).find(node => node.type === 'button' && node.props['aria-controls'] === 'card-content')
  let button = control(render())
  assert.equal(button.props['aria-expanded'], false)
  button.props.onClick(); button = control(render())
  assert.equal(button.props['aria-expanded'], true)
  button.props.onClick(); assert.equal(control(render()).props['aria-expanded'], false)
})

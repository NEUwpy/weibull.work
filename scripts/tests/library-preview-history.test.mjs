import test from 'node:test'
import assert from 'node:assert/strict'
import { createLibraryPreviewHistory } from '../../src/lib/library-preview-history.ts'

const sourceState = { __NA: true, tree: ['library'], source: 'original window' }
function browserHarness() {
  const entries = [{ state: { __NA: true }, url: '/methods' }, { state: sourceState, url: '/library?q=Weibull' }]
  const listeners = new Set(), changes = [], pending = []
  let index = 1
  const target = {
    location: { get href() { return entries[index].url } },
    history: {
      get state() { return entries[index].state },
      pushState(state, _title, url) { entries.splice(index + 1); entries.push({ state, url }); index++ },
      replaceState(state, _title, url) { entries[index] = { state, url } },
      back() { pending.push(-1) }, forward() { pending.push(1) },
    },
    addEventListener: (_event, listener) => listeners.add(listener),
    removeEventListener: (_event, listener) => listeners.delete(listener),
  }
  const flush = () => {
    for (const direction of pending.splice(0)) {
      index = Math.max(0, Math.min(entries.length - 1, index + direction))
      for (const listener of listeners) listener({ state: target.history.state })
    }
  }
  const controller = createLibraryPreviewHistory(target, href => changes.push(href))
  return { target, controller, entries, changes, flush, index: () => index, pending }
}

test('opening adds one source-URL entry and version/paragraph changes replace it, preserving Next state', () => {
  const app = browserHarness()
  app.controller.open('/library/182-046')
  app.controller.open('/library/182-046?version=原文#passage-59')
  assert.equal(app.entries.length, 3)
  assert.equal(app.target.location.href, '/library?q=Weibull')
  assert.equal(app.target.history.state.__NA, true)
  assert.deepEqual(app.target.history.state.tree, sourceState.tree)
  assert.equal(app.target.history.state.source, sourceState.source)
  assert.equal(app.changes.at(-1), '/library/182-046?version=原文#passage-59')
})

test('browser Back closes the preview in one step and Forward reopens the last document', () => {
  const app = browserHarness()
  app.controller.open('/library/182-046?version=原文#passage-59')
  app.target.history.back(); app.flush()
  assert.equal(app.index(), 1)
  assert.equal(app.changes.at(-1), null)
  assert.equal(app.target.history.state, sourceState)
  app.target.history.forward(); app.flush()
  assert.equal(app.changes.at(-1), '/library/182-046?version=原文#passage-59')
})

test('repeated close clicks consume only the preview entry and leave ordinary Back available', () => {
  const app = browserHarness()
  app.controller.open('/library/182-046')
  app.controller.close(); app.controller.close()
  assert.deepEqual(app.pending, [-1])
  app.flush()
  assert.equal(app.index(), 1)
  assert.equal(app.changes.at(-1), null)
  app.target.history.back(); app.flush()
  assert.equal(app.target.location.href, '/methods')
})

test('full opening replaces the temporary entry so a single Back reaches the source window', () => {
  const app = browserHarness()
  app.controller.open('/library/182-046')
  app.controller.leave()
  app.target.history.replaceState(app.target.history.state, '', '/library/182-046')
  app.target.history.back(); app.flush()
  assert.equal(app.index(), 1)
  assert.equal(app.target.location.href, '/library?q=Weibull')
  app.target.history.forward(); app.flush()
  assert.equal(app.target.location.href, '/library/182-046')
  assert.equal(app.changes.at(-1), null)
})

test('remount reads the active preview and cleanup removes its history listener', () => {
  const app = browserHarness()
  app.controller.open('/library/182-046')
  app.controller.dispose()
  const changes = []
  const restored = createLibraryPreviewHistory(app.target, href => changes.push(href))
  assert.deepEqual(changes, ['/library/182-046'])
  restored.dispose()
  app.target.history.back(); app.flush()
  assert.deepEqual(changes, ['/library/182-046'])
})

test('author and paper layers return through their sources without changing earlier history entries', () => {
  const app = browserHarness()
  const author = '/library?author=Xiaoyu+Yang&from=181-004'
  app.controller.open('/library/181-004')
  app.controller.push(author)
  app.controller.push('/library/182-025')
  app.controller.open('/library/182-025?version=原文')
  assert.equal(app.entries.length, 5)
  assert.equal(app.target.location.href, '/library?q=Weibull')
  app.controller.close(); app.flush()
  assert.equal(app.changes.at(-1), author)
  app.controller.close(); app.flush()
  assert.equal(app.changes.at(-1), '/library/181-004')
  app.target.history.forward(); app.flush()
  assert.equal(app.changes.at(-1), author)
  app.target.history.forward(); app.flush()
  assert.equal(app.changes.at(-1), '/library/182-025?version=原文')
  app.controller.leave()
  app.target.history.replaceState(app.target.history.state, '', '/library/182-025?version=原文')
  app.target.history.back(); app.flush()
  app.controller.restore()
  assert.equal(app.changes.at(-1), author)
})

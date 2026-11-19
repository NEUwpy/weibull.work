import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const key = 'reliability-engineering-and-system-safety'
const papers = [
  { slug: '182-025', type: '期刊', publication: 'Reliability Engineering and System Safety', year: 2024 },
  { slug: '182-011', type: '期刊', publication: 'Reliability Engineering & System Safety, vol. 4', short_publication: 'RESS', year: 2026 },
  { slug: '182-048', type: '期刊', publication: 'IEEE Transactions on Reliability', year: 2025 },
  { slug: 'document', type: '文献', publication: 'Reliability Engineering & System Safety', year: 2025 },
]

const { GET } = loadServerModule('src/app/api/library/journals/route.ts', {
  'next/server': { NextResponse: { json: (body, init = {}) => ({ body, status: init.status || 200 }) } },
  '@/lib/server/literature': { listPapers: () => papers, LibraryConfigurationError: class extends Error {} },
})

const journalRequest = query => GET(new Request(`http://localhost/api/library/journals${query}`))

test('journal preview combines registered journal variants and keeps the same ordered papers from each entry', async () => {
  const directory = await journalRequest(`?key=${key}`)
  const overview = await journalRequest(`?key=${key}&from=182-025&category=other`)
  assert.equal(directory.status, 200)
  assert.equal(directory.body.journal.name, 'Reliability Engineering & System Safety')
  assert.equal(directory.body.journal.shortName, 'RESS')
  assert.equal(directory.body.journal.metrics.quartile, 'Q1')
  assert.equal(directory.body.journal.count, 2)
  assert.deepEqual(Array.from(directory.body.papers, paper => paper.slug), ['182-011', '182-025'])
  assert.deepEqual(directory.body, overview.body)
})

test('journal preview reports invalid keys and missing groups separately', async () => {
  assert.equal((await journalRequest('')).status, 400)
  assert.equal((await journalRequest('?key=wrong%2Fformat')).status, 400)
  assert.equal((await journalRequest('?key=not-in-the-library')).status, 404)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { enrichLibraryMetadata, applyJournalUpdate } from '../library-metadata.mjs'

const registry = { year: 2025, journals: [] }
const metadata = { title: 'A new reliability estimation method', author: 'Jane Smith', year: 2026, type: '期刊', publication: 'A New Journal' }
const source = { titles: [], dois: ['10.1234/local-mistake'], arxiv: [] }
const work = { DOI: '10.1234/verified', title: [metadata.title], author: [{ family: 'Smith' }],
  published: { 'date-parts': [[2026]] }, 'container-title': ['A New Journal'], ISSN: ['1234-5678'] }
const index = { year: 2025, source: 'https://publisher.test/2025-jcr', journals: [
  { name: 'A NEW JOURNAL', issns: ['1234-5678'], impactFactor: 3.2, quartile: 'Q2' },
] }

test('new papers recover from an incorrect local DOI and complete an unseen journal from the shared index', async () => {
  const calls = []
  const result = await enrichLibraryMetadata({ metadata, source }, { registry, index, fetchJson: async url => {
    calls.push(url)
    if (url.includes('local-mistake')) throw new Error('HTTP 404')
    return { message: { items: [work] } }
  } })
  assert.equal(result.metadata.doi, work.DOI)
  assert.deepEqual(result.journalUpdate.metrics, { impactFactor: 3.2, quartile: 'Q2', source: index.source })
  assert.deepEqual(result.warnings, [])
  assert.equal(calls.length, 2)
  assert.equal(metadata.doi, undefined)
  const savedJournal = { name: 'A New Journal', abbreviation: 'ANJ', abbreviationSource: 'https://publisher.test/short-name', aliases: ['ANJ'] }
  const refreshed = await enrichLibraryMetadata({ metadata: { ...metadata, doi: work.DOI }, source }, {
    registry: { ...registry, journals: [savedJournal] }, index,
  })
  assert.equal(refreshed.journalUpdate.abbreviation, savedJournal.abbreviation)
  assert.equal(refreshed.journalUpdate.abbreviationSource, savedJournal.abbreviationSource)
  assert.deepEqual(refreshed.journalUpdate.aliases, savedJournal.aliases)
})

test('wrong authors, different versions and ambiguous publication matches produce a concrete issue', async () => {
  for (const works of [[{ ...work, author: [{ family: 'Brown' }] }], [{ ...work, published: { 'date-parts': [[1990]] } }],
    [work, { ...work, DOI: '10.1234/ambiguous' }]]) {
    const result = await enrichLibraryMetadata({ metadata, source: { titles: [], dois: [], arxiv: [] } }, {
      registry, index, fetchJson: async () => ({ message: { items: works } }),
    })
    assert.equal(result.metadata.doi, undefined)
    assert.ok(result.warnings.some(message => message.includes('DOI')))
  }
  const result = await enrichLibraryMetadata({ metadata: { ...metadata, doi: work.DOI }, source }, {
    registry, index: { ...index, year: 2024 }, fetchJson: async () => { throw new Error('unused') },
  })
  assert.equal(result.journalUpdate, undefined)
  assert.ok(result.warnings[0].includes('2025'))
})

test('journal writes are idempotent and retain concurrent metadata and aliases', () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'journal-enrichment-'))
  const file = path.join(folder, 'journals.json')
  const report = { year: 2025, journalUpdate: { name: 'A New Journal', metrics: { impactFactor: 3.2, quartile: 'Q2', source: index.source } } }
  try {
    fs.writeFileSync(file, JSON.stringify({ ...registry, journals: [{ name: 'Existing Journal', aliases: ['Existing alias'], metrics: { impactFactor: 1 } }] }))
    applyJournalUpdate(report, file)
    const saved = fs.readFileSync(file, 'utf8')
    applyJournalUpdate(report, file)
    assert.equal(fs.readFileSync(file, 'utf8'), saved)
    assert.deepEqual(JSON.parse(saved).journals[1].aliases, ['Existing alias'])
    fs.writeFileSync(file + '.lock', '')
    assert.throws(() => applyJournalUpdate(report, file), /EEXIST/)
    assert.equal(fs.readFileSync(file, 'utf8'), saved)
  } finally { fs.rmSync(folder, { recursive: true, force: true }) }
})

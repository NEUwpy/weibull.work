import test from 'node:test'
import assert from 'node:assert/strict'
import { compareLibraryOrder, isLibrarySort } from '../../src/lib/library-sort.ts'

test('publication years sort in both directions, keep missing years last and use natural IDs for ties', () => {
  const papers = [{ slug: '182-010', year: 2020 }, { slug: '182-002', year: 2020 },
    { slug: '171-001', year: 2025 }, { slug: '421-001', year: 0 }, { slug: '421-002' }]
  const before = JSON.stringify(papers)
  const sorted = sort => [...papers].sort((a, b) => compareLibraryOrder(a, b, sort)).map(p => p.slug)
  assert.deepEqual(sorted('year-desc'), ['171-001', '182-002', '182-010', '421-001', '421-002'])
  assert.deepEqual(sorted('year-asc'), ['182-002', '182-010', '171-001', '421-001', '421-002'])
  assert.deepEqual(sorted('id-asc'), ['171-001', '182-002', '182-010', '421-001', '421-002'])
  assert.equal(JSON.stringify(papers), before)
  assert.equal(isLibrarySort('year-desc'), true)
  assert.equal(isLibrarySort('relevance'), true)
  assert.equal(isLibrarySort('date'), false)
})

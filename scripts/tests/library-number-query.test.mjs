import test from 'node:test'
import assert from 'node:assert/strict'
import { parseLibraryNumberQuery } from '../../src/lib/library-number-query.ts'

test('pasted IDs match exactly and deduplicate while single prefixes remain valid', () => {
  assert.deepEqual(parseLibraryNumberQuery('１８２－０４６，183-012\n182-046；421–001、'), {
    prefix: null, ids: ['182-046', '183-012', '421-001'],
  })
  for (const prefix of ['18', '182-', '182-0', '182-046']) {
    assert.deepEqual(parseLibraryNumberQuery(prefix), { prefix, ids: [] })
  }
  for (const query of ['2020', '10.1234/182-046', '比较 182-046 和 183-012', '182-046、183-0']) {
    assert.equal(parseLibraryNumberQuery(query), null)
  }
})

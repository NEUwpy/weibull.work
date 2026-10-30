import test from 'node:test'
import assert from 'node:assert/strict'
import { createLiteratureIndex, titleKey, extractDois } from '../../src/lib/literature-search.mjs'

const records = [
  {key:'a',id:'182-001',title:'三参数威布尔估计',title_en:'Three-parameter Weibull estimation: a new method',author:'J. Demidenko',year:2006,doi:'10.1000/test'},
  {key:'b',id:'121-001',title:'Fatigue crack propagation',author:'M. H. El Haddad, K. N. Smith',year:1979,doi:'10.2000/fatigue'},
  {key:'c',id:'182-002',title:'A different scientific paper',author:'K. Smith',year:2020,doi:'10.3000/other'},
]
const index = createLiteratureIndex(records)

test('DOI, citation title and typo-tolerant names are reusable search entrypoints', () => {
  for (const query of ['https://doi.org/10.1000/TEST.', 'three parameter WEIBULL estimation — a new method', 'Demidenco', '威布尔', 'Weibull 2006', '182001']) {
    assert.equal(index.search(query)[0]?.key, 'a', query)
  }
  assert.deepEqual(index.search('Smith').map(hit=>hit.key), ['b','c'])
  assert.equal(index.search('Smith 1979')[0]?.key, 'b')
  assert.deepEqual(index.search('10.1000/unknown'), [])
  assert.equal(index.search('10.1000/te')[0]?.key, 'a')
  assert.equal(index.search('完全不存在的文献').length, 0)
  assert.deepEqual(index.search(' ').map(hit=>hit.key), ['a','b','c'])
})

test('search candidates do not weaken automatic reference matching', () => {
  assert.equal(index.search('Demidenco').length, 1)
  assert.deepEqual(index.matchReference('Demidenco'), {key:null,method:'unmatched'})
  assert.equal(index.matchReference('J. Demidenco. Three-parameter Weibull estimation: a new method.').key, 'a')
  assert.equal(index.matchReference('“Three-parameter Weibull estimation: a new method, with an extra subtitle”. Demidenko 2006.').key, null)
  assert.equal(index.matchReference('doi:10.1000/test. A different scientific paper.').method, 'conflict')
  assert.equal(index.matchReference('Demidenko. Three-parameter Weibull estimation: a new method. 2020.').method, 'conflict')
  assert.equal(index.matchReference('Improved Three-parameter Weibull estimation: a new method. 2006.').key, null)
})

test('duplicate IDs are independent results and duplicate identities are not auto-linked', () => {
  const duplicate = createLiteratureIndex([records[0],{...records[0],key:'other-directory'}])
  assert.equal(duplicate.search('182-001').length, 2)
  assert.equal(duplicate.matchReference('doi:10.1000/test').key, null)
  assert.throws(()=>createLiteratureIndex([records[0],records[0]]), /身份重复/)
})

test('symbol handling, surname accents, initials and multiple authors', () => {
  assert.notEqual(titleKey('x < y'), titleKey('x > y'))
  assert.deepEqual(extractDois('doi:10.1016/S(01)12345-6.'), ['10.1016/s(01)12345-6'])
  const names = createLiteratureIndex([{key:'x',title:'An unrelated paper',author:'R. L. Smith; Darija Marković'}])
  assert.equal(names.search('R L Smith')[0]?.key, 'x')
  assert.equal(names.search('Richard L Smith')[0]?.key, 'x')
  assert.equal(names.search('Markovic')[0]?.key, 'x')
  assert.equal(names.search('Smiht')[0]?.key, 'x')
  assert.equal(createLiteratureIndex([{key:'d',title:'Pending paper',reason:'复现实验需要'}]).search('复现').length, 1)
})

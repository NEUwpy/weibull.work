import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { libraryAuthorNames, libraryAuthorIdentity, libraryAuthorMatchesQuery, libraryPapersByAuthor } = loadServerModule('src/lib/library-authors.ts')
const papers = [
  { slug: 'chinese', author: '杨小玉, 谢里阳, 杨奕凤, 赵丙峰', year: 2024 },
  { slug: 'english', author: 'Liyang Xie, Ningxiang Wu, Xiaoyu Yang', year: 2022 },
  { slug: 'reversed', author: 'YANG Xiao-yu, XIE Li-yang', year: 2023 },
  { slug: 'initials', author: 'X. Yang, Xiaoyu Zhang', year: 2025 },
  { slug: 'prefix', author: 'Xiaoyu Yangson', year: 2025 },
  { slug: 'unit-solo', author: 'Jane Doe', year: 2024, affiliation: 'Example University' },
  { slug: 'unit-multi', author: 'Jane Doe, John Roe', year: 2025, affiliation: 'Other University; Third University' },
  { slug: 'unit-annotated', author: 'Anne Doe（University of Examples）; John Roe', year: 2023, affiliation: 'Whole paper unit' },
]

test('author parsing preserves bilingual annotations, institution commas and suffixes', () => {
  assert.deepEqual(Array.from(libraryAuthorNames('Toru Ogura（小倉徹，三重大学）、Takatoshi Sugiyama（東京理科大学）')), ['Toru Ogura（小倉徹，三重大学）', 'Takatoshi Sugiyama（東京理科大学）'])
  assert.deepEqual(Array.from(libraryAuthorNames('Francis A. Roesch, Jr.、John Smith（Oceanweather, Inc.）')), ['Francis A. Roesch, Jr.', 'John Smith（Oceanweather, Inc.）'])
  assert.deepEqual(Array.from(libraryAuthorNames('Xiaoyu Yang, Liyang Xie, et al.')), ['Xiaoyu Yang', 'Liyang Xie'])
  assert.deepEqual(Array.from(libraryAuthorNames('杨小玉、谢里阳 等')), ['杨小玉', '谢里阳'])
  assert.deepEqual(Array.from(libraryAuthorNames('A and B; C & D')), ['A', 'B', 'C', 'D'])
})

test('reviewed bilingual and reversed names resolve to one author without initials or substring merging', () => {
  for (const name of ['杨小玉', 'Xiaoyu Yang', 'Yang Xiaoyu', 'YANG Xiao-yu']) {
    assert.equal(libraryAuthorIdentity(name).name, '杨小玉')
    assert.deepEqual(Array.from(libraryPapersByAuthor(papers, name), paper => paper.slug), ['chinese', 'english', 'reversed'])
  }
  assert.equal(libraryAuthorIdentity('X. Yang').evidence.length, 0)
  assert.deepEqual(Array.from(libraryPapersByAuthor(papers, 'Yang')), [])
  assert.deepEqual(Array.from(libraryPapersByAuthor(papers, 'Unknown')), [])
  assert.notEqual(libraryAuthorIdentity('Mary Ann Smith').key, libraryAuthorIdentity('Maryann Smith').key)
})

test('every registered spelling resolves uniquely to its reviewed author with source evidence', () => {
  const registered = JSON.parse(fs.readFileSync('src/data/library-authors.json', 'utf8'))
  for (const author of registered) {
    assert.ok(author.evidence.length)
    assert.ok(author.affiliations.every(item => item.name && item.slug && item.year))
    for (const alias of [author.name, author.englishName, ...author.aliases]) {
      assert.equal(libraryAuthorIdentity(alias).name, author.name, alias)
    }
  }
})

test('author search accepts surnames, Chinese fragments and reviewed bilingual names within one author', () => {
  for (const query of ['yang', 'YANG', '小玉', 'Xiaoyu Yang', 'Yang Xiaoyu', 'Yang Xiao-yu']) {
    assert.equal(libraryAuthorMatchesQuery('杨小玉, 谢里阳', query), true, query)
  }
  assert.equal(libraryAuthorMatchesQuery('Liyang Xie', 'yang'), false)
  assert.equal(libraryAuthorMatchesQuery('Xiaoyu Yang, Liyang Xie', 'Xiaoyu Xie'), false)
  assert.equal(libraryAuthorMatchesQuery('Xiaoyu Yang', 'Weibull'), false)
  assert.equal(libraryAuthorMatchesQuery('Xiaoyu Yang', '182'), false)
  assert.equal(libraryAuthorMatchesQuery('Xiaoyu Yang', 'X. Yang'), false)
  assert.equal(libraryAuthorIdentity('杨小玉').affiliations[0].name, '东北大学机械工程与自动化学院')
  assert.equal(libraryAuthorIdentity('朱文慧').affiliations[0].name, '中国国际工程咨询有限公司国防业务部')
})

test('the public author endpoint lists selected metadata and handles missing names and read failures', async () => {
  const response = { json: (body, init = {}) => ({ body, status: init.status || 200, headers: init.headers }) }
  let fail = false
  class LibraryConfigurationError extends Error {}
  const { GET } = loadServerModule('src/app/api/library/authors/route.ts', {
    'next/server': { NextResponse: response },
    '@/lib/server/literature': { listPapers: () => { if (fail) throw new LibraryConfigurationError(); return papers }, LibraryConfigurationError },
  }, { console: { error() {} } })
  const result = await GET(new Request('http://localhost/api/library/authors?name=Yang+Xiaoyu'))
  assert.equal(result.status, 200)
  assert.equal(result.body.author.englishName, 'Xiaoyu Yang')
  assert.deepEqual(Array.from(result.body.papers, paper => paper.slug), ['chinese', 'reversed', 'english'])
  assert.equal(result.headers['Cache-Control'], 'no-store')
  assert.equal((await GET(new Request('http://localhost/api/library/authors'))).status, 400)
  assert.equal((await GET(new Request('http://localhost/api/library/authors?name=Nobody'))).status, 404)
  const jane = await GET(new Request('http://localhost/api/library/authors?name=Jane+Doe'))
  assert.deepEqual(Array.from(jane.body.author.affiliations, item => item.name), ['Example University'])
  const anne = await GET(new Request('http://localhost/api/library/authors?name=Anne+Doe'))
  assert.deepEqual(Array.from(anne.body.author.affiliations, item => item.name), ['University of Examples'])
  fail = true
  assert.equal((await GET(new Request('http://localhost/api/library/authors?name=杨小玉'))).status, 503)
})

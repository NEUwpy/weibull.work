import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { libraryInstitutionIdentity, libraryInstitutionNames, libraryPaperInstitutions, libraryPapersByInstitution, libraryInstitutionMatchesQuery } = loadServerModule('src/lib/library-institutions.ts')
const papers = [
  { slug: '182-025', author: '杨小玉, 谢里阳, 杨奕凤, 赵丙峰', year: 2024, affiliation: '东北大学机械工程与自动化学院' },
  { slug: '182-103', author: 'Shenglei Liu', year: 2026, affiliation: 'Department of Mechanical Engineering and Automation, Northeastern University, Shenyang, China' },
  { slug: '182-046', author: '谢里阳, 朱文慧, 吴宁祥, 杨小玉', year: 2025, affiliation: '东北大学机械工程与自动化学院' },
  { slug: 'other', author: 'Someone Else', year: 2023, affiliation: 'Other University（Department of Mathematics, Example City）；Third University' },
]

test('institution parsing retains address commas and matches reviewed bilingual names at the correct level', () => {
  assert.deepEqual(Array.from(libraryInstitutionNames(papers[3].affiliation)), ['Other University（Department of Mathematics, Example City）', 'Third University'])
  assert.deepEqual(Array.from(libraryInstitutionNames(papers[1].affiliation)), ['东北大学机械工程与自动化学院'])
  assert.equal(libraryInstitutionIdentity('Northeastern University').name, '东北大学')
  assert.equal(libraryInstitutionIdentity('School of Mechanical Engineering & Automation, Northeastern University').name, '东北大学机械工程与自动化学院')
  assert.deepEqual(Array.from(libraryPapersByInstitution(papers, 'Northeastern University'), paper => paper.slug), ['182-025', '182-103', '182-046'])
  assert.equal(libraryPapersByInstitution(papers, '东北大学航空动力装备振动及控制教育部重点实验室').length, 1)
})

test('verified author-specific units use their source paper without attaching them to other papers', () => {
  assert.ok(libraryPaperInstitutions(papers[2]).includes('中国国际工程咨询有限公司国防业务部'))
  assert.deepEqual(Array.from(libraryPapersByInstitution(papers, '中国国际工程咨询有限公司'), paper => paper.slug), ['182-046'])
  assert.equal(libraryPaperInstitutions({ ...papers[2], slug: 'different' }).includes('中国国际工程咨询有限公司国防业务部'), false)
})

test('institution search matches Chinese and English names but cannot join terms from separate units', () => {
  for (const query of ['东北大学', '机械工程', 'Northeastern University', 'mechanical engineering']) {
    assert.equal(libraryInstitutionMatchesQuery(papers[0], query), true, query)
  }
  assert.equal(libraryInstitutionMatchesQuery(papers[3], 'Other Third'), false)
  assert.equal(libraryInstitutionMatchesQuery(papers[0], 'yang'), false)
  assert.equal(libraryInstitutionMatchesQuery(papers[0], '182'), false)
})

test('registered institution aliases and parent references resolve to their own documented identities', () => {
  const registered = JSON.parse(fs.readFileSync('src/data/library-institutions.json', 'utf8'))
  for (const institution of registered) {
    assert.ok(institution.evidence.length)
    for (const alias of [institution.name, institution.englishName, ...institution.aliases]) assert.equal(libraryInstitutionIdentity(alias).name, institution.name)
    if (institution.parent) assert.ok(registered.some(parent => parent.name === institution.parent))
  }
})

test('the institution endpoint returns selected papers and reports invalid or unavailable identities', async () => {
  const { GET } = loadServerModule('src/app/api/library/institutions/route.ts', {
    'next/server': { NextResponse: { json: (body, init = {}) => ({ body, status: init.status || 200 }) } },
    '@/lib/server/literature': { listPapers: () => papers, LibraryConfigurationError: class extends Error {} },
  })
  const result = await GET(new Request('http://localhost/api/library/institutions?name=Northeastern+University'))
  assert.equal(result.status, 200)
  assert.equal(result.body.institution.name, '东北大学')
  assert.deepEqual(Array.from(result.body.papers, paper => paper.slug), ['182-103', '182-046', '182-025'])
  assert.equal((await GET(new Request('http://localhost/api/library/institutions'))).status, 400)
  assert.equal((await GET(new Request('http://localhost/api/library/institutions?name=Missing'))).status, 404)
})

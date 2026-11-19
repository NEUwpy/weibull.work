import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { loadServerModule } from './helpers/load-server-module.mjs'

const {
  libraryInstitutionIdentity, libraryInstitutionNames, libraryPaperAuthorAffiliations, libraryPaperInstitutions,
  libraryPapersByInstitution, libraryInstitutionMatchesQuery, librarySignedAuthorsByInstitution, libraryAuthorAffiliationGroups,
} = loadServerModule('src/lib/library-institutions.ts')
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

test('the institution reverse lookup follows paper-specific author assignments', () => {
  const signed = { slug: 'signed', author: 'Alice Chen, Ben Wu, Clara Hu', year: 2025, credits: {
    authors: [{ name: 'Alice Chen', units: ['lab'] }, { name: 'Ben Wu', units: ['other'] }, { name: 'Clara Hu' }],
    institutions: [{ id: 'lab', name: 'Example Research Institute' }, { id: 'other', name: 'Other University' }],
  } }
  const annotation = { slug: 'annotation', author: 'Dana Li（Example Research Institute）, Evan Xu', year: 2024 }
  const unnamed = { slug: 'unnamed', author: 'Frank Yu, Grace Tang', affiliation: 'Example Research Institute', year: 2023 }
  const catalog = [signed, annotation, unnamed]
  const papers = libraryPapersByInstitution(catalog, 'Example Research Institute')
  assert.deepEqual(Array.from(papers, paper => paper.slug), ['signed', 'annotation', 'unnamed'])
  const identity = libraryInstitutionIdentity('Example Research Institute', catalog)
  assert.deepEqual(Array.from(librarySignedAuthorsByInstitution(papers, identity), author => [author.name, author.slug]),
    [['Alice Chen', 'signed'], ['Dana Li', 'annotation']])
  const older = { ...signed, slug: 'older', year: 2020 }
  assert.equal(librarySignedAuthorsByInstitution([...papers, older], identity, older.slug)[0].slug, 'older')
  const otherRecords = libraryPaperAuthorAffiliations({ ...annotation, slug: 'new', author: 'Dana Li, Evan Xu' })
  assert.deepEqual(Array.from(otherRecords, record => record.institutions.length), [0, 0])
})

test('author affiliation summaries preserve publication years and merge reviewed names per paper', () => {
  const groups = libraryAuthorAffiliationGroups([
    { name: '东北大学机械工程与自动化学院', slug: '2022-paper', year: 2022 },
    { name: 'School of Mechanical Engineering & Automation, Northeastern University', slug: '2024-joint', year: 2024 },
    { name: '东北大学机械工程与自动化学院', slug: '2024-joint', year: 2024 },
    { name: '示例研究所', slug: '2024-joint', year: 2024 },
    { name: '示例研究所', slug: '2026-paper', year: 2026 },
    { name: '示例研究所', slug: 'undated-paper', year: 0 },
    { name: '未登记', slug: 'other-paper', year: 2025 },
  ])
  assert.deepEqual(Array.from(groups, ({ name, years, records }) => [
    name, Array.from(years), Array.from(records, record => record.slug),
  ]), [
    ['示例研究所', [2026, 2024], ['2026-paper', '2024-joint', 'undated-paper']],
    ['东北大学机械工程与自动化学院', [2024, 2022], ['2024-joint', '2022-paper']],
  ])
})

test('institution labels and links unify address and spacing variants without merging named campuses', () => {
  const signatures = [
    '西北工业大学 航海学院，陕西 西安 710072',
    '西北工业大学航海学院',
    '西北工业大学 航空学院',
    'University of California, Irvine CA 92697, USA',
    'University of California, Berkeley CA 94720, USA',
  ]
  const catalog = signatures.map((name, index) => ({ slug: String(index), author: 'Example Author', year: 2025, credits: {
    authors: [{ name: 'Example Author', units: ['u'] }], institutions: [{ id: 'u', name }],
  } }))
  const groups = libraryAuthorAffiliationGroups(signatures.map((name, index) => ({ name, slug: String(index), year: 2025 })), catalog)
  assert.equal(groups.length, 4)
  const unit = libraryInstitutionIdentity('西北工业大学航海学院', catalog)
  assert.equal(unit.name, '西北工业大学航海学院')
  assert.deepEqual(Array.from(unit.evidence, item => item.slug), ['0', '1'])
  for (const name of [unit.name, signatures[0]]) {
    assert.deepEqual(Array.from(libraryPapersByInstitution(catalog, name), paper => paper.slug), ['0', '1'])
  }
  assert.equal(libraryInstitutionIdentity('沈阳理工大学 汽车与交通学院，110159，沈阳').name, '沈阳理工大学汽车与交通学院')
  assert.match(libraryInstitutionIdentity('示例研究院，上海分院 200000').name, /上海分院/)
  assert.equal(libraryInstitutionIdentity('University of Freiburg, Freiburg, Germany').name, 'University of Freiburg')
  const campus = libraryInstitutionIdentity(signatures[3], catalog)
  assert.match(campus.name, /Irvine/)
  assert.doesNotMatch(campus.name, /92697/)
  assert.deepEqual(Array.from(libraryPapersByInstitution(catalog, campus.name), paper => paper.slug), ['3'])
})

test('Northeastern University lab signature variants group together while the two labs stay distinct', () => {
  const ministry = '东北大学航空动力装备振动及控制教育部重点实验室'
  const provincial = '辽宁省复杂装备多学科设计优化技术重点实验室'
  const older = 'Lab. Vibration and Control of Aero-Propulsion System, Northeastern University, Shenyang, China'
  const later = 'Key Laboratory of Vibration and Control of Aeronautical Power Equipment, Ministry of Education, Northeastern University, Shenyang'
  const provincialEnglish = 'Liaoning Province Key Laboratory of Multidisciplinary Design Optimization of Complex Equipment, Northeastern University, Shenyang 110819, China'
  const catalog = [[older], [later, provincialEnglish], [provincial]].map((names, index) => ({
    slug: String(index), year: 2023 + index, author: '谢里阳', credits: {
      authors: [{ name: '谢里阳', units: names.map((_, unit) => String(unit)) }],
      institutions: names.map((name, unit) => ({ id: String(unit), name })),
    },
  }))
  const signatures = catalog.flatMap(paper => libraryPaperAuthorAffiliations(paper)[0].institutions.map(name => ({
    name, slug: paper.slug, year: paper.year,
  })))
  const groups = libraryAuthorAffiliationGroups(signatures, catalog)
  assert.deepEqual(Array.from(groups, ({ name, records }) => [name, Array.from(records, record => record.slug)]), [
    [provincial, ['2', '1']], [ministry, ['1', '0']],
  ])
  assert.deepEqual(Array.from(libraryPapersByInstitution(catalog, older), paper => paper.slug), ['0', '1'])
  assert.deepEqual(Array.from(libraryPapersByInstitution(catalog, provincialEnglish), paper => paper.slug), ['1', '2'])
  assert.equal(libraryPapersByInstitution(catalog, '东北大学').length, 3)
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

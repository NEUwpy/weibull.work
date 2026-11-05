import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule as load } from './helpers/load-server-module.mjs'

const { validateLibraryCredits, libraryCreditDiagnostics, findLibraryCredit } = load('src/lib/library-credits.ts')
const { libraryAuthorIdentity, libraryPapersByAuthor, libraryAuthorMatchesQuery } = load('src/lib/library-authors.ts')
const { libraryInstitutionIdentity, libraryPapersByInstitution, libraryInstitutionMatchesQuery } = load('src/lib/library-institutions.ts')
const credits = {
  authors: [{ name: '测试作者甲', name_en: 'Ming Example', aliases: ['Example Ming'], units: ['lab'] }, { name: 'Second Author', units: ['other'] }],
  institutions: [{ id: 'lab', name: '测试研究院', name_en: 'Example Research Institute', aliases: ['Example Institute'] }, { id: 'other', name: 'Other University' }],
}
const papers = [{ slug: 'new', author: '测试作者甲, Second Author', year: 2026, credits },
  { slug: 'english', author: 'Ming Example', year: 2025 },
  { slug: 'initials', author: 'M. Example', year: 2024 }]

test('new source credits power author and unit profiles and searches without static registry edits', () => {
  const author = libraryAuthorIdentity('Example Ming', papers)
  assert.equal(author.name, '测试作者甲')
  assert.equal(author.englishName, 'Ming Example')
  assert.deepEqual(Array.from(author.affiliations, unit => [unit.name, unit.slug, unit.year]), [['测试研究院', 'new', 2026]])
  assert.deepEqual(Array.from(libraryPapersByAuthor(papers, 'Ming Example'), paper => paper.slug), ['new', 'english'])
  assert.equal(libraryAuthorMatchesQuery(papers[0].author, 'example', credits), true)
  assert.equal(libraryAuthorMatchesQuery(papers[1].author, '测试作者甲', undefined, papers), true)
  assert.equal(libraryAuthorMatchesQuery(papers[0].author, 'Ming Second', credits), false)
  const unit = libraryInstitutionIdentity('Example Institute', papers)
  assert.equal(unit.name, '测试研究院')
  assert.equal(unit.englishName, 'Example Research Institute')
  assert.deepEqual(Array.from(libraryPapersByInstitution(papers, unit.name), paper => paper.slug), ['new'])
  assert.equal(libraryInstitutionMatchesQuery(papers[0], 'Example Institute'), true)
})

test('malformed or private credits and dangling author-unit assignments fail validation', () => {
  assert.equal(validateLibraryCredits(credits), credits)
  for (const invalid of [null, { authors: [] }, { ...credits, private_note: 'secret' },
    { authors: [{ name: 'A', units: ['missing'] }] },
    { authors: [{ name: 'A', email: 'private@example.com' }] },
    { authors: [{ name: 'Unknown' }] },
    { authors: [{ name: 'A' }], institutions: [{ id: 'u', name: 'Unit' }, { id: 'u', name: 'Other' }] }]) {
    assert.throws(() => validateLibraryCredits(invalid), /credits/)
  }
})

test('missing source evidence emits explicit diagnostics and ambiguous aliases never join identities', () => {
  assert.equal(libraryCreditDiagnostics({})[0].code, 'META_CREDITS_MISSING')
  const codes = Array.from(libraryCreditDiagnostics({ credits: { authors: [{ name: '待查作者' }] } }), row => row.code)
  assert.ok(codes.includes('META_CREDITS_EN_MISSING'))
  assert.ok(codes.includes('META_CREDITS_UNITS_MISSING'))
  assert.equal(findLibraryCredit([{ name: '张甲', aliases: ['J. Zhang'] }, { name: '张乙', aliases: ['J. Zhang'] }], 'J. Zhang'), undefined)
})

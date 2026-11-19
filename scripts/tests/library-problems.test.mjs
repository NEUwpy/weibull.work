import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { libraryProblemDirections, libraryProblems, libraryProblemGroups, matchesLibraryProblem, validateLibraryProblemTags } = loadServerModule('src/lib/library-problems.ts')

test('the supplied JRSE collection retains six directions and all 73 distinct questions', () => {
  assert.equal(libraryProblemDirections.length, 6)
  assert.equal(new Set(libraryProblems.map(problem => problem.key)).size, 73)
  assert.deepEqual(Array.from(libraryProblemDirections, direction => libraryProblems.filter(problem => problem.direction === direction.key).length), [19, 9, 6, 16, 8, 15])
  for (const problem of libraryProblems) assert.ok(problem.name && problem.challenge && problem.proposer)
})

test('new paper tags derive collection membership and deduplicated counts without a member table', () => {
  const papers = [
    { tags: ['普通关键词', 'problem:theory-02', 'problem:theory-05', 'problem:theory-02'] },
    { tags: ['problem:theory'] },
    { tags: ['problem:support-01'] },
    { tags: ['小样本', 'AI'] },
  ]
  assert.equal(libraryProblemGroups(papers).find(group => group.key === 'theory').count, 2)
  assert.equal(libraryProblemGroups(papers).find(group => group.key === 'theory').problems.find(problem => problem.key === 'theory-02').count, 1)
  assert.equal(matchesLibraryProblem(papers[1], 'theory-02'), false)
  assert.equal(matchesLibraryProblem(papers[3], 'theory'), false)
  papers.push({ tags: ['problem:theory-02', 'problem:phm-01'] })
  assert.equal(libraryProblemGroups(papers).find(group => group.key === 'theory').count, 3)
  assert.equal(matchesLibraryProblem(papers[4], 'phm'), true)
})

test('unknown reserved tags are diagnosed while unrelated legacy keywords remain valid', () => {
  assert.deepEqual(validateLibraryProblemTags(['关键词', 'problem:theory', 'problem:theory-02']), ['关键词', 'problem:theory', 'problem:theory-02'])
  for (const tag of ['problem:', 'problem:unknown', 'problem:theory-99']) assert.throws(() => validateLibraryProblemTags([tag]), /未知科学问题标签/)
  assert.equal(matchesLibraryProblem({ tags: ['problem:unknown'] }, 'unknown'), false)
})

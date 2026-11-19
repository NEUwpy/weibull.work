import assert from 'node:assert/strict'
import test from 'node:test'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { libraryPeopleGroups, libraryPeopleCollectionFilters, libraryVisiblePeople } =
  loadServerModule('src/lib/library-collections.ts')

const papers = [{
  slug: 'example',
  author: 'Alice Chen, Bob Smith, Zoe Lee',
  credits: {
    authors: [
      { name: 'Alice Chen', units: ['lab'] },
      { name: 'Bob Smith' },
      { name: 'Zoe Lee', units: ['lab', 'university'] },
    ],
    institutions: [
      { id: 'lab', name: '东北大学机械工程与自动化学院' },
      { id: 'university', name: 'Alpha University' },
    ],
  },
}]

test('author controls use signed units and their verified parent without including unassigned coauthors', () => {
  const groups = libraryPeopleGroups(papers, 'authors')
  const filters = libraryPeopleCollectionFilters(groups, 'authors')
  const school = filters.find(option => option.label === '东北大学')
  assert.equal(school.count, 2)
  assert.deepEqual(Array.from(libraryVisiblePeople(groups, school.value, 'name-asc'), author => author.name), ['Alice Chen', 'Zoe Lee'])
  assert.deepEqual(Array.from(libraryVisiblePeople(groups, 'all', 'institution-asc')).at(-1).name, 'Bob Smith')
  assert.deepEqual(Array.from(libraryVisiblePeople(groups, 'all', 'name-asc'), author => author.name), ['Alice Chen', 'Bob Smith', 'Zoe Lee'])
})

test('institution controls distinguish a known department from its university', () => {
  const groups = libraryPeopleGroups(papers, 'institutions')
  assert.deepEqual(Array.from(libraryVisiblePeople(groups, 'child', 'name-asc'), unit => unit.name), ['东北大学机械工程与自动化学院'])
  assert.deepEqual(new Set(Array.from(libraryVisiblePeople(groups, 'root', 'name-asc'), unit => unit.name)),
    new Set(['Alpha University', '东北大学']))
})

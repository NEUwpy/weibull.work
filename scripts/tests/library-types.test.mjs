import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { libraryTypeLabel, matchesLibraryType } = loadServerModule('src/lib/library-types.ts')

test('paper counts include article types and follow each added card type', () => {
  const papers = ['期刊', '会议', '书籍', '预印本', '学位论文', '待核实', undefined].map(type => ({ type }))
  const count = filter => papers.filter(paper => matchesLibraryType(paper, filter)).length
  assert.equal(count('all'), 7)
  assert.equal(count('paper'), 4)
  assert.equal(count('journal'), 1)
  assert.equal(count('book'), 1)
  assert.equal(count('journal-conf'), 2)
  papers.push({ type: '期刊' }, { type: '书籍' })
  assert.equal(count('all'), 9)
  assert.equal(count('paper'), 5)
  assert.equal(count('book'), 2)
  assert.equal(libraryTypeLabel('文献'), '待核实')
  assert.equal(libraryTypeLabel('预印本'), '预印本')
  papers.push({type: '论文'}, {type: '工作论文'}, {type: '软件文档'}, {type: '技术资料'})
  assert.equal(count('paper'), 7)
  assert.equal(count('book'), 2)
})

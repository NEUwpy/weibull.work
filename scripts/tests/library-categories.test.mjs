import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { libraryCategoryForSource: category, libraryCategoryGroups: groups, matchesLibraryCategory: matches, validLibraryCategoryFilter: valid } = loadServerModule('src/lib/library-categories.ts')

test('source folders map to reader-facing topics on Windows and POSIX paths', () => {
  const deep = category('D:\\博士阶段\\100科研文献管理\\180_AI辅助参数估计\\184_深度学习参数估计')
  assert.equal(deep.key, '180/184')
  assert.equal(deep.groupName, '参数估计')
  assert.equal(deep.name, '深度学习估计')
  assert.equal(category('/source/170_AI在参数估计外的实践/171_机器学习').groupName, 'AI 方法与实践')
  assert.equal(category('/source/420专业书籍/421可靠性工程').key, '420/421')
  assert.equal(category('/source/180_AI辅助参数估计-extra/184_深度学习参数估计').key, 'other')
  assert.equal(category('/source/182-001-paper').key, 'other')
})

test('new source categories and selected cards update topic counts without a maintained count list', () => {
  const papers = [
    { category: category('/source/180_AI辅助参数估计/181_综述文献') },
    { category: category('/source/180_AI辅助参数估计/184_深度学习参数估计') },
    { category: category('/source/170_AI在参数估计外的实践/171_机器学习') },
  ]
  assert.equal(groups(papers).find(group => group.key === '180').count, 2)
  const added = { category: category('/source/180_AI辅助参数估计/188_新增主题') }
  papers.push(added)
  assert.equal(added.category.name, '新增主题')
  assert.equal(groups(papers).find(group => group.key === '180').count, 3)
  assert.equal(papers.filter(p => matches(p, '180/188')).length, 1)
  assert.equal(papers.filter(p => matches(p, '170')).length, 1)
  assert.equal(papers.filter(p => matches(p)).length, 4)
  assert.equal(matches({}, 'other'), true)
  assert.equal(valid('180/184'), true)
  for (const value of ['../180', '180/184/1', 'D:/source', '180/private']) assert.equal(valid(value), false)
})

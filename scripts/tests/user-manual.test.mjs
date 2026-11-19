import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import matter from 'gray-matter'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { parseUserManualFeatures } = loadServerModule('src/lib/markdown.ts')

test('extracts public manual features from the checked-in source', () => {
  const raw = fs.readFileSync(new URL('../../07-用户手册.md', import.meta.url), 'utf8')
  const { body, diagnostics } = parseUserManualFeatures(`${matter(raw).content}\n\n## 内部维护\n\n[内部链接](docs/notes.md)`)
  assert.equal(JSON.stringify(diagnostics), '[]')
  assert.match(body, /^## 功能详解/)
  assert.match(body, /### 可靠性图书馆/)
  assert.doesNotMatch(body, /维护指南|docs\/library\/README|内部维护|docs\/notes\.md/)
})

test('reports missing public headings, empty sections, and repository links in rendered text', () => {
  const raw = `## 功能详解（草案）
~~~markdown
## 功能详解
~~~
## 功能详解
### 威布尔计算器
> [内部链接](docs/internals.md)
### 参数估计方法
[错误链接](docs/details.md#一)
### 人工智能方法
公开正文
### 案例数据库
[查看案例](/cases)
`
  const { body, diagnostics } = parseUserManualFeatures(raw)
  assert.ok(diagnostics.some(item => item.line === 5 && item.message.includes('可靠性图书馆')))
  assert.ok(diagnostics.some(item => item.line === 6 && item.message.includes('公开正文')))
  assert.ok(diagnostics.some(item => item.line === 9 && item.message.includes('仓库文档链接')))
  assert.equal(diagnostics.length, 3)
  assert.doesNotMatch(body, /草案|内部链接/)
})

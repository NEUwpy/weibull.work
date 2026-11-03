import test from 'node:test'
import assert from 'node:assert/strict'
import { loadServerModule } from './helpers/load-server-module.mjs'

const { extractLibraryNoteSummary } = loadServerModule('src/lib/library-note-summary.ts')

test('only the named summary section is selected, including numbered headings', () => {
  for (const heading of ['# 一句话总结', '## 1. 一句话总结', '## 一、一句话总结']) {
    const raw = `---\n摘要: PRIVATE_YAML\n---\n# 文献笔记\n\nPRIVATE_OPENING\n\n${heading}\n\n公开总结，保留 $\\beta$ 与**原有强调**。\n\n---\n\n## 问题背景和动机\n\nPRIVATE_REST\n`
    assert.equal(extractLibraryNoteSummary(raw), '公开总结，保留 $\\beta$ 与**原有强调**。')
  }
})

test('code headings cannot start or end a summary section', () => {
  const raw = '```md\n## 一句话总结\nPRIVATE_FAKE\n```\n\n## 一句话总结\n公开内容\n```text\n# 示例\n```\n\n## 对我的研究启发\nPRIVATE_RESEARCH'
  assert.equal(extractLibraryNoteSummary(raw), '公开内容\n```text\n# 示例\n```')
})

test('missing, empty or malformed summary input is not replaced with the rest of a note', () => {
  for (const raw of ['## 核心内容\nPRIVATE_CONTENT', '---\n## 一句话总结\nPRIVATE_YAML', '## 一句话总结\n\n## 不足\nPRIVATE_LIMITATIONS']) {
    assert.equal(extractLibraryNoteSummary(raw), '')
  }
})

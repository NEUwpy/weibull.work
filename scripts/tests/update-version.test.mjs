import assert from 'node:assert/strict'
import { execFileSync, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'

test('main commits save one matching version record, including retries and merges', () => {
  const tempRoot = fs.realpathSync(os.tmpdir())
  const repo = fs.mkdtempSync(path.join(tempRoot, 'weibull-version-'))
  const options = { cwd: repo, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }
  const git = (...args) => execFileSync('git', args, options).trim()
  const write = (file, text) => fs.writeFileSync(path.join(repo, file), text)
  const versionScript = path.join('scripts', 'update-version.mjs')

  function assertCommittedVersion(expected) {
    const pkg = JSON.parse(git('show', 'HEAD:package.json'))
    const lock = JSON.parse(git('show', 'HEAD:package-lock.json'))
    const log = git('show', 'HEAD:08-更新日志.md')
    const headings = [...log.matchAll(/^## v([^ ]+) \(((?:\d{4}-\d{2}-\d{2}))\)$/gm)]
    assert.equal(headings[0][1].split('-')[0], expected)
    assert.equal(headings[0][1], pkg.version)
    assert.equal(pkg.version, lock.version)
    assert.equal(pkg.version, lock.packages[''].version)
    assert.equal(new Set(headings.map(heading => heading[1])).size, headings.length)
    assert.ok(log.includes('## v4.2.0-261113 (2026-11-13)\n\n- 既有记录'))
    assert.equal(git('status', '--porcelain'), '')
  }

  try {
    git('init', '-q', '-b', 'main')
    git('config', 'user.name', 'Version test')
    git('config', 'user.email', 'version-test@example.invalid')
    git('config', 'commit.gpgSign', 'false')
    git('config', 'core.hooksPath', '.git/hooks')
    const initial = '4.2.0-261113'
    write('08-更新日志.md', '# 更新日志\n\n## v4.2.0-261113 (2026-11-13)\n\n- 既有记录\n')
    write('package.json', JSON.stringify({ version: initial }))
    write('package-lock.json', JSON.stringify({ version: initial, packages: { '': { version: initial } } }))
    write('overview.md', '初始内容\n')
    fs.mkdirSync(path.join(repo, 'scripts'))
    fs.copyFileSync(new URL('../update-version.mjs', import.meta.url), path.join(repo, versionScript))
    git('add', '-A')
    git('commit', '-qm', 'Initial files')
    execFileSync(process.execPath, [versionScript, '--install'], options)

    write('overview.md', '逐步读取\n')
    git('add', 'overview.md')
    git('commit', '-qm', 'Update overview')
    assertCommittedVersion('4.2.1')
    assert.match(git('show', 'HEAD:08-更新日志.md'), /项目文档（1 个文件）/)

    write('overview.md', '继续完善\n')
    git('add', 'overview.md')
    const cancelled = spawnSync('git', ['commit', '-qm', ''], options)
    assert.equal(cancelled.status, 1)
    assert.equal(JSON.parse(git('show', ':package.json')).version.split('-')[0], '4.2.2')
    git('commit', '-qm', 'Retry update')
    assertCommittedVersion('4.2.2')

    write('overview.md', '架构变更\n')
    git('-c', 'weibull.versionBump=minor', '-c', 'weibull.versionNote=架构变更', 'commit', '-qam', 'Update architecture')
    assertCommittedVersion('4.3.0')
    assert.match(git('show', 'HEAD:08-更新日志.md'), /- 架构变更/)

    write('overview.md', '局部提交\n')
    git('commit', '-qm', 'Commit one file', '--', 'overview.md')
    assertCommittedVersion('4.3.1')

    git('switch', '-qc', 'feature')
    write('overview.md', '分支改动\n')
    git('commit', '-qam', 'Feature work')
    assertCommittedVersion('4.3.1')
    git('switch', '-q', 'main')
    const merged = spawnSync('git', ['merge', '--no-ff', '-m', 'Merge feature', 'feature'], options)
    assert.notEqual(merged.status, 0)
    assert.match(merged.stderr, /git commit/)
    assert.equal(git('rev-parse', 'MERGE_HEAD'), git('rev-parse', 'feature'))
    git('commit', '-qm', 'Merge feature')
    assertCommittedVersion('4.3.2')
  } finally {
    if (path.dirname(fs.realpathSync(repo)) === tempRoot && path.basename(repo).startsWith('weibull-version-')) {
      fs.rmSync(repo, { recursive: true, force: true })
    }
  }
})

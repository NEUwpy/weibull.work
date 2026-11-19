/**
 * Markdown rendering utilities for user-facing content.
 *
 * The published manual hides blockquotes used for internal notes.
 */

/** Remove all blockquote lines and collapse excess blank lines. */
export function stripBlockquotes(markdown: string): string {
  return markdown
    .replace(/^ {0,3}>.*\n?/gm, '')
    .replace(/\n{3,}/g, '\n\n')
}

/** Extract only the first section (before the second ## heading). */
export function extractFirstSection(markdown: string): string {
  const match = markdown.match(/^[\s\S]*?(?=\n## )/)
  return match ? match[0] : markdown
}

/** Extract content from start up to (but not including) a specific ## heading. */
export function extractBeforeHeading(markdown: string, heading: string): string {
  const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`^## ${escaped}`, 'm')
  const match = regex.exec(markdown)
  if (!match) return markdown
  return markdown.slice(0, match.index).trim()
}

/** Extract content from a specific ## heading to end of document. */
export function extractFromHeading(markdown: string, heading: string): string {
  const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`^## ${escaped}`, 'm')
  const match = regex.exec(markdown)
  if (!match) return ''
  return markdown.slice(match.index).trim()
}

const FEATURE_SECTIONS = ['威布尔计算器', '参数估计方法', '人工智能方法', '案例数据库', '可靠性图书馆']

/** Extract the public features and report format errors at their source lines. */
export function parseUserManualFeatures(markdown: string) {
  const diagnostics: { line: number; message: string }[] = []
  const lines = markdown.split(/\r?\n/)
  let fence: string | undefined
  const visible = markdown.replace(/<!--[\s\S]*?-->/g, comment => comment.replace(/[^\r\n]/g, ''))
    .split(/\r?\n/).map(line => {
      const marker = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/)
      if (marker) {
        if (!fence) fence = marker[1]
        else if (marker[1].startsWith(fence) && !marker[2].trim()) fence = undefined
        return ''
      }
      return fence || /^\s*>/.test(line) ? '' : line
    })
  const heading = /^## 功能详解\s*$/
  const start = visible.findIndex(line => heading.test(line))
  if (start === -1) {
    diagnostics.push({ line: 1, message: '缺少「## 功能详解」公开章节。' })
    return { body: '', diagnostics }
  }

  let publicEnd = visible.length
  for (let index = start + 1; index < visible.length; index++) {
    if (heading.test(visible[index])) diagnostics.push({ line: index + 1, message: '「## 功能详解」公开章节重复。' })
    if (publicEnd === visible.length && /^#{1,2} /.test(visible[index])) publicEnd = index
  }

  const sections = new Map<string, number>()
  for (let index = start + 1; index < publicEnd; index++) {
    const line = visible[index]
    const section = /^### (.+?)\s*$/.exec(line)?.[1]
    if (section && FEATURE_SECTIONS.includes(section)) {
      if (sections.has(section)) diagnostics.push({ line: index + 1, message: `「${section}」功能小节重复。` })
      else sections.set(section, index)
    }
    for (const [, target] of Array.from(line.matchAll(/\]\(<?([^\s()>]+?\.md(?:#[^\s()>]+)?)>?\)/gi))) {
      if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(target)) {
        diagnostics.push({ line: index + 1, message: '公开手册中的链接应指向网站页面，仓库文档链接可放在引用注释中。' })
      }
    }
  }

  for (const section of FEATURE_SECTIONS) {
    const index = sections.get(section)
    if (index === undefined) {
      diagnostics.push({ line: start + 1, message: `缺少「${section}」功能小节。` })
      continue
    }
    let end = index + 1
    while (end < publicEnd && !/^#{1,3} /.test(visible[end])) end++
    if (!visible.slice(index + 1, end).some(line => line.trim() && !/^\s*#/.test(line))) {
      diagnostics.push({ line: index + 1, message: `「${section}」缺少公开正文。` })
    }
  }

  return { body: stripBlockquotes(lines.slice(start, publicEnd).join('\n')).trim(), diagnostics }
}

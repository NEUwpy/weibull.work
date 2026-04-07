/**
 * Markdown rendering utilities for user-facing content.
 *
 * Convention: blockquote lines (starting with ">") in source docs are
 * developer-only notes. They are stripped before rendering to end users.
 */

/** Remove all blockquote lines and collapse excess blank lines. */
export function stripBlockquotes(markdown: string): string {
  return markdown
    .replace(/^>.*\n?/gm, '')
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

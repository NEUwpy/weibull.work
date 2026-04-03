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

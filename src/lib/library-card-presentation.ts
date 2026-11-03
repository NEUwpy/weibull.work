/** A display-only preview; the catalog and introduction retain the full author list. */
export function libraryAuthorPreview(author: string): string {
  const text = author.trim()
  const suffix = /(?:[,，;；、]?\s*(?:et\s+al\.?|等人?)[.\s]*)$/i
  const alreadyShortened = suffix.test(text)
  const names = text.replace(suffix, '').split(/[,，;；、]\s*|\s+(?:and|&)\s+/i).map(name => name.trim()).filter(Boolean)
  if (names.length <= 3 && !alreadyShortened) return text
  const chinese = /[\u3400-\u9fff]/.test(text)
  return names.slice(0, 3).join(chinese ? '、' : ', ') + (chinese ? ' 等' : ', et al.')
}

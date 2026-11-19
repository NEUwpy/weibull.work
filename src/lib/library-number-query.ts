/** Single numbers can be prefixes. A batch must consist entirely of complete IDs. */
export function parseLibraryNumberQuery(query: string) {
  const normalized = query.normalize('NFKC').replace(/[‐‑‒–—−]/g, '-').trim()
  if (/^(?:\d{1,3}|\d{3}-\d{0,3})$/.test(normalized)) {
    return { prefix: normalized, ids: [] as string[] }
  }
  const ids = normalized.split(/[\s,;、]+/).filter(Boolean)
  if (ids.length < 2 || ids.some(id => !/^\d{3}-\d{3}$/.test(id))) return null
  return { prefix: null, ids: Array.from(new Set(ids)) }
}

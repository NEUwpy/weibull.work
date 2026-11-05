import registeredAuthors from '../data/library-authors.json'
import { findLibraryCredit, libraryCreditNames, type LibraryCreditPaper, type LibraryCredits } from './library-credits'

export interface LibraryAuthor {
  key: string
  name: string
  englishName?: string
  aliases: string[]
  evidence: { slug: string; note: string }[]
  affiliations: { name: string; slug: string; year: number }[]
}

/** Author-list separators inside affiliations and bilingual annotations stay intact. */
export function libraryAuthorNames(author: string): string[] {
  const text = author.trim().replace(/(?:[,，;；、]?\s*(?:et\s+al\.?|等人?)[.\s]*)$/i, '')
  const names: string[] = []
  let start = 0
  for (const match of Array.from(text.matchAll(/（[^）]*）|\([^)]*\)|\s+(?:and|&)\s+|[,&，;；、؛]/gi))) {
    if (/^[（(]/.test(match[0])) continue
    names.push(text.slice(start, match.index).trim())
    start = match.index! + match[0].length
  }
  names.push(text.slice(start).trim())
  const result: string[] = []
  for (const name of names) {
    if (!name) continue
    if (/^(?:Jr\.?|Sr\.?|II|III|IV)$/i.test(name) && result.length) result[result.length - 1] += `, ${name}`
    else result.push(name)
  }
  return result
}

export function libraryAuthorName(name: string): string {
  return name.replace(/（[^）]*）|\([^)]*\)/g, '').replace(/[*†‡]/g, '').trim()
}

function nameKey(name: string): string {
  return libraryAuthorName(name).normalize('NFKC').toLowerCase().replace(/[.,，'’\-‐‑]/g, '').replace(/\s+/g, ' ')
}

/** Only reviewed aliases join Chinese and romanized names. Initials never expand automatically. */
export function libraryAuthorIdentity(name: string, papers: LibraryCreditPaper[] = []): LibraryAuthor {
  const clean = libraryAuthorName(name)
  const key = nameKey(clean)
  const credit = findLibraryCredit(papers.flatMap(paper => paper.credits?.authors || []), clean)
  const spellings = credit ? libraryCreditNames(credit) : [clean]
  const registered = registeredAuthors.find(author => [author.name, author.englishName, ...author.aliases]
    .some(alias => spellings.some(spelling => nameKey(alias) === nameKey(spelling))))
  if (credit) {
    const sources = papers.filter(paper => paper.credits?.authors.some(author => nameKey(author.name) === nameKey(credit.name)))
    const name = registered?.name || credit.name
    const evidence = [...sources.map(paper => ({ slug: paper.slug, note: '源稿结构化署名 credits' })), ...(registered?.evidence || [])]
    const affiliations = [...sources.flatMap(paper => {
        const author = paper.credits!.authors.find(row => nameKey(row.name) === nameKey(credit.name))!
        return (paper.credits!.institutions || []).filter(unit => author.units?.includes(unit.id)).map(unit => ({ name: unit.name, slug: paper.slug, year: paper.year || 0 }))
      }), ...(registered?.affiliations || [])]
    return { key: nameKey(name), name, englishName: credit.name_en || registered?.englishName,
      aliases: Array.from(new Set([...libraryCreditNames(credit), ...(registered ? [registered.name, registered.englishName, ...registered.aliases] : [])])),
      evidence: evidence.filter((item, index) => evidence.findIndex(other => other.slug === item.slug) === index),
      affiliations: affiliations.filter((item, index) => affiliations.findIndex(other => other.slug === item.slug && other.name === item.name) === index) }
  }
  return registered ? { ...registered, affiliations: [...registered.affiliations], key: nameKey(registered.name), aliases: [registered.name, registered.englishName, ...registered.aliases] }
    : { key, name: clean, aliases: [clean], evidence: [], affiliations: [] }
}

/** Search may use a surname or a full-name fragment, while profile identity stays exact. */
export function libraryPaperAuthorNames(paper: { author: string; credits?: LibraryCredits }): string[] {
  return paper.credits ? paper.credits.authors.map(author => author.name) : libraryAuthorNames(paper.author)
}

export function libraryAuthorMatchesQuery(author: string, query: string, credits?: LibraryCredits, papers: LibraryCreditPaper[] = []): boolean {
  const normalized = nameKey(query.trim())
  if (!normalized || !new RegExp('\\p{L}', 'u').test(normalized)) return false
  const terms = normalized.split(' ')
  const catalog = papers.length ? papers : credits ? [{ slug: '', author, credits }] : []
  return libraryPaperAuthorNames({ author, credits }).some(name => libraryAuthorIdentity(name, catalog).aliases.some(alias => {
    const candidate = nameKey(alias)
    if (/[\u3400-\u9fff]/.test(normalized)) return candidate.includes(normalized)
    const words = candidate.split(' ')
    return terms.every(term => words.some(word => word === term || (term.length >= 2 && word.startsWith(term))))
  }))
}

export function libraryPapersByAuthor<T extends LibraryCreditPaper>(papers: T[], name: string): T[] {
  const key = libraryAuthorIdentity(name, papers).key
  if (!key || /^(?:unknown|未登记|佚名)$/i.test(key)) return []
  return papers.filter(paper => libraryPaperAuthorNames(paper).some(author => libraryAuthorIdentity(author, papers).key === key))
}

export function libraryAuthorPreviewHref(name: string, from?: string): string {
  const query = new URLSearchParams({ author: name })
  if (from) query.set('from', from)
  return `/library?${query}`
}

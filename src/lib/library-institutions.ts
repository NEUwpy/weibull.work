import registeredInstitutions from '../data/library-institutions.json'
import { libraryAuthorIdentity, libraryAuthorNames } from './library-authors'
import { findLibraryCredit, libraryCreditNames, type LibraryCreditPaper } from './library-credits'

export interface LibraryInstitution {
  key: string
  name: string
  englishName?: string
  aliases: string[]
  parent: string
  evidence: { slug: string; note: string }[]
}

function institutionKey(value: string): string {
  return value.normalize('NFKC').toLowerCase().replace(/&/g, ' and ').replace(/[.,，'’\-‐‑]/g, '').replace(/\s+/g, ' ').trim()
}

const aliasesOf = (institution: typeof registeredInstitutions[number]) => [institution.name, institution.englishName, ...institution.aliases]

function containsInstitution(text: string, alias: string): boolean {
  const key = institutionKey(alias)
  if (/[\u3400-\u9fff]/.test(key)) return text.includes(key)
  return (` ${text} `).includes(` ${key} `)
}

export function libraryInstitutionIdentity(name: string, papers: LibraryCreditPaper[] = []): LibraryInstitution {
  const key = institutionKey(name)
  const credit = findLibraryCredit(papers.flatMap(paper => paper.credits?.institutions || []), name)
  if (credit) return { key: institutionKey(credit.name), name: credit.name, englishName: credit.name_en, aliases: libraryCreditNames(credit),
    parent: registeredInstitutions.find(unit => institutionKey(unit.name) === institutionKey(credit.name))?.parent || '',
    evidence: papers.filter(paper => paper.credits?.institutions?.some(unit => institutionKey(unit.name) === institutionKey(credit.name)))
      .map(paper => ({ slug: paper.slug, note: '源稿结构化署名 credits' })) }
  const registered = registeredInstitutions.find(institution => aliasesOf(institution).some(alias => institutionKey(alias) === key))
  return registered ? { ...registered, key: institutionKey(registered.name), aliases: aliasesOf(registered) }
    : { key, name: name.trim(), aliases: [name.trim()], parent: '', evidence: [] }
}

/** Keep address commas and bilingual annotations together, splitting explicit unit separators only. */
export function libraryInstitutionNames(value = ''): string[] {
  const parts: string[] = []
  let start = 0
  for (const match of Array.from(value.matchAll(/（[^）]*）|\([^)]*\)|[;；、]/g))) {
    if (/^[（(]/.test(match[0])) continue
    parts.push(value.slice(start, match.index).trim())
    start = match.index! + match[0].length
  }
  parts.push(value.slice(start).trim())
  const names = parts.filter(Boolean).flatMap(part => {
    const text = institutionKey(part)
    const matched = registeredInstitutions.filter(institution => aliasesOf(institution).some(alias => containsInstitution(text, alias)))
    const specific = matched.filter(institution => !matched.some(other => other.parent === institution.name))
    return specific.length ? specific.map(institution => institution.name) : [part]
  })
  return Array.from(new Set(names))
}

export function libraryPaperInstitutions(paper: LibraryCreditPaper): string[] {
  if (paper.credits) return (paper.credits.institutions || []).map(unit => unit.name)
  const names = libraryInstitutionNames(paper.affiliation)
  for (const author of libraryAuthorNames(paper.author)) {
    for (const unit of libraryAuthorIdentity(author).affiliations) {
      if (unit.slug === paper.slug) names.push(unit.name)
    }
  }
  return Array.from(new Set(names))
}

export function libraryPapersByInstitution<T extends LibraryCreditPaper>(papers: T[], name: string): T[] {
  const identity = libraryInstitutionIdentity(name, papers)
  if (!identity.key || /^(?:unknown|未登记|未知单位)$/i.test(identity.key)) return []
  return papers.filter(paper => libraryPaperInstitutions(paper).some(unit => {
    const candidate = libraryInstitutionIdentity(unit, papers)
    return candidate.key === identity.key || Boolean(candidate.parent && institutionKey(candidate.parent) === identity.key)
  }))
}

/** Search includes verified bilingual aliases and parent units, while profile matching uses exact identities. */
export function libraryInstitutionMatchesQuery(paper: LibraryCreditPaper, query: string, catalog: LibraryCreditPaper[] = [paper]): boolean {
  const normalized = institutionKey(query)
  if (!normalized || !new RegExp('\\p{L}', 'u').test(normalized)) return false
  return libraryPaperInstitutions(paper).some(name => {
    const identity = libraryInstitutionIdentity(name, catalog)
    const aliases = [...identity.aliases, ...(identity.parent ? libraryInstitutionIdentity(identity.parent).aliases : [])]
    return aliases.some(alias => {
      const candidate = institutionKey(alias)
      if (/[\u3400-\u9fff]/.test(normalized)) return candidate.includes(normalized)
      const words = candidate.split(' ')
      return normalized.split(' ').every(term => words.some(word => word === term || (term.length >= 2 && word.startsWith(term))))
    })
  })
}

export function libraryInstitutionPreviewHref(name: string, from?: string): string {
  const query = new URLSearchParams({ institution: name })
  if (from) query.set('from', from)
  return `/library?${query}`
}

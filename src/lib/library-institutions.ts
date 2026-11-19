import registeredInstitutions from '../data/library-institutions.json'
import { libraryAuthorIdentity, libraryAuthorNames, type LibraryAuthor } from './library-authors'
import { findLibraryCredit, libraryCreditNameKey, libraryCreditNames, type LibraryCreditName, type LibraryCreditPaper } from './library-credits'

export interface LibraryInstitution {
  key: string
  name: string
  englishName?: string
  aliases: string[]
  parent: string
  evidence: { slug: string; note: string }[]
}

export const libraryInstitutionPreviewLimit = 2

const chinesePostalAddress = /^(.+(?:大学|学院|学部|学校|实验室|研究所|研究院|公司|中心|医院|集团|系|部))[，,]\s*([\u3400-\u9fff\d，, ]{1,40})$/
const latinPostalCode = new RegExp(String.raw`^(.+,\s*\p{L}[^,]*?)\s+(?:[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}|\d{5,6}(?:-\d{4})?)(\s*,[^,]+)?$`, 'iu')
const repeatedLocality = /^(.+),\s*([^,]+),\s*(?:China|P\.?\s*R\.?\s*China|Germany|Canada|Japan|Australia|U\.?K\.?|U\.?S\.?A\.?)$/i

function institutionName(value: string): string {
  const normalized = value.trim().replace(/\s+/g, ' ').replace(/(?<=[\u3400-\u9fff]) (?=[\u3400-\u9fff])/g, '')
  const chinese = chinesePostalAddress.exec(normalized)
  if (chinese && /\b\d{6}\b/.test(chinese[2]) && !/校区|分校|分院|分所|分中心|分公司|分部/.test(chinese[2])) return chinese[1]

  // Remove a printed postal code. Keep the locality when it can distinguish a campus.
  const withoutCode = normalized.replace(latinPostalCode, '$1$2')
  const locality = repeatedLocality.exec(withoutCode)
  if (locality && libraryCreditNameKey(locality[1]).endsWith(` ${libraryCreditNameKey(locality[2])}`)) return locality[1]
  return withoutCode
}

const institutionKey = (value: string) => libraryCreditNameKey(institutionName(value))
const aliasesOf = (institution: typeof registeredInstitutions[number]) => [institution.name, institution.englishName, ...institution.aliases]
const registeredByKey = new Map(registeredInstitutions.flatMap(institution =>
  aliasesOf(institution).map(name => [institutionKey(name), institution] as const)))

type SignedInstitution = LibraryCreditName & { slug: string }
const signedInstitutionCache = new WeakMap<LibraryCreditPaper[], Map<string, SignedInstitution[]>>()

function signedInstitutions(papers: LibraryCreditPaper[]): Map<string, SignedInstitution[]> {
  const cached = signedInstitutionCache.get(papers)
  if (cached) return cached
  const index = new Map<string, SignedInstitution[]>()
  for (const paper of papers) {
    for (const unit of paper.credits?.institutions || []) {
      const name = institutionName(unit.name)
      const registered = registeredByKey.get(libraryCreditNameKey(name))
      const signature = { slug: paper.slug, name: registered?.name ?? name,
        name_en: registered?.englishName ?? (unit.name_en && institutionName(unit.name_en)),
        aliases: libraryCreditNames(unit).map(institutionName) }
      const keys = new Set(libraryCreditNames(signature).map(libraryCreditNameKey))
      for (const key of Array.from(keys)) {
        const matches = index.get(key)
        if (matches) matches.push(signature)
        else index.set(key, [signature])
      }
    }
  }
  signedInstitutionCache.set(papers, index)
  return index
}

function containsInstitution(text: string, alias: string): boolean {
  const key = institutionKey(alias)
  if (/[\u3400-\u9fff]/.test(key)) return text.includes(key)
  return (` ${text} `).includes(` ${key} `)
}

export function libraryInstitutionIdentity(name: string, papers?: LibraryCreditPaper[]): LibraryInstitution {
  const formatted = institutionName(name)
  const index = papers?.length ? signedInstitutions(papers) : undefined
  const credit = findLibraryCredit(index?.get(libraryCreditNameKey(formatted)) || [], formatted)
  const registered = registeredByKey.get(libraryCreditNameKey(credit?.name ?? formatted))
  const primary = registered?.name ?? credit?.name ?? formatted
  const key = libraryCreditNameKey(primary)
  const signatures = index?.get(key)?.filter(row => libraryCreditNameKey(row.name) === key) || []
  const slugs = new Set(signatures.map(row => row.slug))
  const creditEvidence = Array.from(slugs, slug => ({ slug, note: '源稿结构化署名 credits' }))
  return {
    key, name: primary, englishName: registered?.englishName ?? credit?.name_en ?? signatures.find(row => row.name_en)?.name_en,
    aliases: Array.from(new Set([primary, ...(registered ? aliasesOf(registered) : []), ...signatures.flatMap(libraryCreditNames)])),
    parent: registered?.parent ?? '',
    evidence: creditEvidence.length ? creditEvidence : registered?.evidence ?? [],
  }
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

export function libraryPaperAuthorAffiliations(paper: LibraryCreditPaper): { name: string; institutions: string[] }[] {
  if (paper.credits) {
    const institutions = paper.credits.institutions || []
    return paper.credits.authors.map(author => ({
      name: author.name,
      institutions: institutions.filter(unit => author.units?.includes(unit.id)).map(unit => unit.name),
    }))
  }
  const names = libraryAuthorNames(paper.author)
  const soleAuthor = names.length === 1 && !/(?:et\s+al|等)/i.test(paper.author)
  return names.map(name => {
    const verified = libraryAuthorIdentity(name).affiliations.filter(item => item.slug === paper.slug).map(item => item.name)
    const annotation = /[（(]([^）)]+)[）)]/.exec(name)?.[1]
    const unit = annotation && /大学|学院|公司|实验室|研究|university|univ\.|institute|college|department|cent(?:er|re)|laboratory|school|IBM|USGS/i.test(annotation)
      ? annotation.replace(/^[\u3400-\u9fff]{2,5}[，,]\s*/, '')
      : soleAuthor ? paper.affiliation : undefined
    return { name, institutions: Array.from(new Set([...verified, ...libraryInstitutionNames(unit)])) }
  })
}

export function libraryAuthorAffiliationGroups(affiliations: LibraryAuthor['affiliations'], catalog: LibraryCreditPaper[] = []) {
  const groups = new Map<string, { key: string; name: string; records: LibraryAuthor['affiliations'] }>()
  const identities = new Map<string, LibraryInstitution>()
  for (const record of affiliations) {
    const identity = identities.get(record.name) ?? libraryInstitutionIdentity(record.name, catalog)
    identities.set(record.name, identity)
    if (!identity.key || /^(?:unknown|未登记|未知单位)$/i.test(identity.key)) continue
    const group = groups.get(identity.key)
    if (!group) groups.set(identity.key, { key: identity.key, name: identity.name, records: [record] })
    else if (!group.records.some(source => source.slug === record.slug)) group.records.push(record)
  }
  return Array.from(groups.values(), group => {
    const records = group.records.sort((a, b) => b.year - a.year || a.slug.localeCompare(b.slug, undefined, { numeric: true }))
    const years = Array.from(new Set(records.map(record => record.year).filter(year => year > 0)))
    return { ...group, records, years }
  }).sort((a, b) => (b.years[0] ?? 0) - (a.years[0] ?? 0) || a.name.localeCompare(b.name, 'zh-CN'))
}

export function libraryPaperInstitutions(paper: LibraryCreditPaper): string[] {
  if (paper.credits) return (paper.credits.institutions || []).map(unit => unit.name)
  return Array.from(new Set([
    ...libraryInstitutionNames(paper.affiliation),
    ...libraryPaperAuthorAffiliations(paper).flatMap(author => author.institutions),
  ]))
}

export function libraryPaperInstitutionIdentities(paper: LibraryCreditPaper, catalog: LibraryCreditPaper[]) {
  const units = new Map<string, LibraryInstitution>()
  for (const name of libraryPaperInstitutions(paper)) {
    const unit = libraryInstitutionIdentity(name, catalog)
    if (!unit.key || /^(?:unknown|未登记|未知单位)$/i.test(unit.key)) continue
    units.set(unit.key, unit)
    if (unit.parent) {
      const parent = libraryInstitutionIdentity(unit.parent, catalog)
      units.set(parent.key, parent)
    }
  }
  return Array.from(units.values())
}

function belongsToInstitution(candidate: LibraryInstitution, key: string): boolean {
  return candidate.key === key || Boolean(candidate.parent && institutionKey(candidate.parent) === key)
}

export function libraryPapersByInstitution<T extends LibraryCreditPaper>(papers: T[], name: string): T[] {
  const identity = libraryInstitutionIdentity(name, papers)
  if (!identity.key || /^(?:unknown|未登记|未知单位)$/i.test(identity.key)) return []
  return papers.filter(paper => libraryPaperInstitutionIdentities(paper, papers).some(unit => unit.key === identity.key))
}

export function librarySignedAuthorsByInstitution(papers: LibraryCreditPaper[], institution: LibraryInstitution, from?: string | null) {
  const authors = new Map<string, { name: string; slug: string }>()
  for (const paper of papers) {
    for (const record of libraryPaperAuthorAffiliations(paper)) {
      if (!record.institutions.some(unit => belongsToInstitution(libraryInstitutionIdentity(unit, papers), institution.key))) continue
      const identity = libraryAuthorIdentity(record.name, papers)
      if (identity.key && !/^(?:unknown|未登记|佚名)$/i.test(identity.key) && (paper.slug === from || !authors.has(identity.key))) {
        authors.set(identity.key, { name: identity.name, slug: paper.slug })
      }
    }
  }
  return Array.from(authors.values())
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

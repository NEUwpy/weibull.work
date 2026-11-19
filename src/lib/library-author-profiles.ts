import { libraryAuthorIdentity, libraryPaperAuthorNames, type LibraryAuthor } from './library-authors'
import type { LibraryCreditPaper } from './library-credits'
import { libraryPaperAuthorAffiliations } from './library-institutions'
import { compareLibraryOrder } from './library-sort'

export type LibraryAuthorProfile<T> = { author: LibraryAuthor; papers: T[] }

export function createLibraryAuthorProfiles<T extends LibraryCreditPaper>(catalog: T[]) {
  const profiles = new Map<string, LibraryAuthorProfile<T>>()
  for (const paper of [...catalog].sort((a, b) => compareLibraryOrder(a, b, 'year-desc'))) {
    const members = new Map(libraryPaperAuthorNames(paper).map(name => {
      const author = libraryAuthorIdentity(name, catalog)
      return [author.key, author]
    }))
    const affiliations = new Map<string, Set<string>>()
    for (const record of libraryPaperAuthorAffiliations(paper)) {
      const { key } = libraryAuthorIdentity(record.name, catalog)
      const units = affiliations.get(key) || new Set<string>()
      record.institutions.forEach(name => units.add(name))
      affiliations.set(key, units)
    }
    for (const [key, author] of Array.from(members)) {
      if (!key || /^(?:unknown|未登记|佚名)$/i.test(key)) continue
      const profile = profiles.get(key) ?? { author: { ...author, affiliations: [] }, papers: [] }
      profile.papers.push(paper)
      for (const name of Array.from(affiliations.get(key) || [])) {
        profile.author.affiliations.push({ name, slug: paper.slug, year: paper.year || 0 })
      }
      profiles.set(key, profile)
    }
  }
  return (name: string): LibraryAuthorProfile<T> | undefined => profiles.get(libraryAuthorIdentity(name, catalog).key)
}

import { createLibraryAuthorProfiles } from './library-author-profiles'
import type { LibraryAuthor } from './library-authors'
import type { LibraryCreditPaper } from './library-credits'
import { libraryInstitutionIdentity, libraryPaperInstitutionIdentities, type LibraryInstitution } from './library-institutions'
import { groupLibraryJournalPapers, validLibraryJournalFilter, type LibraryJournal } from './library-journals'
import { libraryProblemGroups, matchesLibraryProblem } from './library-problems'
import type { libraryEntityDirectories } from './library-preview-history'
import { compareLibraryOrder } from './library-sort'

type DirectoryPaper = LibraryCreditPaper & { type?: string; publication?: string; short_publication?: string; tags?: string[] }
export type LibraryEntityKind = keyof typeof libraryEntityDirectories
export type LibraryEntityProfile<T> = {
  author?: LibraryAuthor
  institution?: LibraryInstitution
  journal?: LibraryJournal
  papers: T[]
}

const problemDirectory = libraryProblemGroups([])

function byNewest<T extends LibraryCreditPaper>(a: T, b: T) {
  return compareLibraryOrder(a, b, 'year-desc')
}

export function createLibraryJournalProfiles<T extends DirectoryPaper>(catalog: T[]) {
  const groups = groupLibraryJournalPapers(catalog)
  for (const { papers } of Array.from(groups.values())) papers.sort(byNewest)
  return {
    journals: Array.from(groups.values(), group => group.journal),
    findJournal: (key: string) => validLibraryJournalFilter(key) ? groups.get(key) : undefined,
  }
}

export function createLibraryInstitutionProfiles<T extends LibraryCreditPaper>(catalog: T[]) {
  const groups = new Map<string, { institution: LibraryInstitution; papers: T[] }>()
  for (const paper of catalog) {
    for (const institution of libraryPaperInstitutionIdentities(paper, catalog)) {
      const group = groups.get(institution.key)
      if (group) group.papers.push(paper)
      else groups.set(institution.key, { institution, papers: [paper] })
    }
  }
  for (const { papers } of Array.from(groups.values())) papers.sort(byNewest)
  return (name: string) => groups.get(libraryInstitutionIdentity(name, catalog).key)
}

export function createLibraryDirectoryIndex<T extends DirectoryPaper>(catalog: T[]) {
  const findAuthor = createLibraryAuthorProfiles(catalog)
  const findInstitution = createLibraryInstitutionProfiles(catalog)
  const { journals, findJournal } = createLibraryJournalProfiles(catalog)
  const ordered = [...catalog].sort(byNewest)
  const problemPapers = new Map<string, T[]>()
  const countProblemPapers = (key: string) => {
    const papers = ordered.filter(paper => matchesLibraryProblem(paper, key))
    problemPapers.set(key, papers)
    return papers.length
  }
  const problemGroups = problemDirectory.map(direction => ({
    ...direction, count: countProblemPapers(direction.key),
    problems: direction.problems.map(problem => ({ ...problem, count: countProblemPapers(problem.key) })),
  }))
  function findEntity(kind: LibraryEntityKind, value: string): LibraryEntityProfile<T> | undefined {
    const key = value.trim()
    if (kind === 'author') return findAuthor(key)
    if (kind === 'institution') return findInstitution(key)
    return findJournal(key)
  }
  return { catalog, journals, problemGroups, problemPapers, findEntity }
}

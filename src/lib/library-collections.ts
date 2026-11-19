import { libraryAuthorIdentity, libraryPaperAuthorNames, type LibraryAuthor } from './library-authors'
import type { LibraryCreditPaper } from './library-credits'
import { libraryAuthorAffiliationGroups, libraryInstitutionIdentity, libraryPaperAuthorAffiliations, libraryPaperInstitutionIdentities } from './library-institutions'

const nameCollator = new Intl.Collator('zh-CN-u-co-pinyin', { sensitivity: 'base', numeric: true })
export const compareLibraryCollectionNames = nameCollator.compare

const countSort = { value: 'count-desc', label: '论文数降序' } as const
export const libraryCollectionSortOptions = {
  problems: [
    { value: 'source-order', label: '原目录顺序' },
    countSort,
  ],
  journals: [
    { value: 'impact-desc', label: '影响因子降序' },
    { value: 'name-asc', label: '刊名 A–Z' },
    countSort,
  ],
  authors: [
    { value: 'name-asc', label: '姓名 A–Z', description: '中文按拼音，其他姓名按字母' },
    { value: 'institution-asc', label: '按署名机构', description: '按机构名称，同机构按姓名' },
    countSort,
  ],
  institutions: [
    { value: 'name-asc', label: '机构 A–Z' },
    countSort,
  ],
} as const

export type LibraryCollection = keyof typeof libraryCollectionSortOptions
export type LibraryCollectionSort = typeof libraryCollectionSortOptions[LibraryCollection][number]['value']
export type LibraryPeopleCollection = 'authors' | 'institutions'

type CollectionInstitution = { key: string; name: string }
type PeopleIdentity = ReturnType<typeof libraryAuthorIdentity> | ReturnType<typeof libraryInstitutionIdentity>
type PeopleGroup = Pick<PeopleIdentity, 'key' | 'name' | 'englishName'> & {
  count: number
  parent: string
  affiliations: LibraryAuthor['affiliations']
}
export type LibraryPeopleGroup = Omit<PeopleGroup, 'affiliations'> & {
  affiliations: string[]
  institutions: CollectionInstitution[]
  sortInstitution: string
}

export function libraryPeopleGroups(papers: LibraryCreditPaper[], kind: LibraryPeopleCollection): LibraryPeopleGroup[] {
  const groups = new Map<string, PeopleGroup>()
  const authors = new Map<string, ReturnType<typeof libraryAuthorIdentity>>()
  const units = new Map<string, ReturnType<typeof libraryInstitutionIdentity>>()
  function resolveAuthor(name: string) {
    const author = authors.get(name) ?? libraryAuthorIdentity(name, papers)
    authors.set(name, author)
    return author
  }
  function resolveUnit(name: string) {
    const unit = units.get(name) ?? libraryInstitutionIdentity(name, papers)
    units.set(name, unit)
    return unit
  }

  for (const paper of papers) {
    const members = kind === 'authors' ? libraryPaperAuthorNames(paper).map(resolveAuthor)
      : libraryPaperInstitutionIdentities(paper, papers)
    const uniqueMembers = new Map(members.map(member => [member.key, member]))
    for (const member of Array.from(uniqueMembers.values())) {
      if (!member.key || /^(?:unknown|未登记|佚名|未知单位)$/i.test(member.key)) continue
      const group = groups.get(member.key)
      if (group) group.count += 1
      else groups.set(member.key, {
        key: member.key, name: member.name, englishName: member.englishName,
        count: 1, parent: 'parent' in member ? member.parent : '', affiliations: [],
      })
    }
    if (kind !== 'authors') continue
    for (const { name, institutions } of libraryPaperAuthorAffiliations(paper)) {
      const author = groups.get(resolveAuthor(name).key)
      author?.affiliations.push(...institutions.map(unit => ({ name: unit, slug: paper.slug, year: paper.year ?? 0 })))
    }
  }

  return Array.from(groups.values(), ({ affiliations, ...group }) => {
    const signedUnits = libraryAuthorAffiliationGroups(affiliations, papers)
    const institutions = new Map<string, CollectionInstitution>()
    const sortInstitutions = signedUnits.map(({ key, name }) => {
      institutions.set(key, { key, name })
      const { parent } = resolveUnit(name)
      if (!parent) return name
      const school = resolveUnit(parent)
      institutions.set(school.key, { key: school.key, name: school.name })
      return school.name
    })
    return { ...group, affiliations: signedUnits.map(unit => unit.name), institutions: Array.from(institutions.values()),
      sortInstitution: sortInstitutions.sort(compareLibraryCollectionNames)[0] ?? '' }
  })
}

export function libraryPeopleCollectionFilters(groups: LibraryPeopleGroup[], kind: LibraryPeopleCollection) {
  if (kind === 'institutions') {
    const childCount = groups.filter(group => group.parent).length
    return [
      { value: 'all', label: '全部机构', count: groups.length },
      { value: 'root', label: '上级及独立机构', count: groups.length - childCount },
      { value: 'child', label: '下属机构', count: childCount },
    ]
  }
  const filters = new Map<string, { value: string; label: string; count: number }>()
  for (const group of groups) {
    for (const { key, name } of group.institutions) {
      const value = `unit:${key}`
      const filter = filters.get(value)
      if (filter) filter.count += 1
      else filters.set(value, { value, label: name, count: 1 })
    }
  }
  return [{ value: 'all', label: '全部机构', count: groups.length },
    ...Array.from(filters.values()).sort((a, b) => compareLibraryCollectionNames(a.label, b.label))]
}

export function libraryVisiblePeople(groups: LibraryPeopleGroup[], filter: string, sort: LibraryCollectionSort) {
  return groups.filter(group => {
    if (filter === 'all') return true
    if (filter === 'root') return !group.parent
    if (filter === 'child') return Boolean(group.parent)
    return group.institutions.some(unit => `unit:${unit.key}` === filter)
  }).sort((a, b) => {
    const byName = compareLibraryCollectionNames(a.name, b.name) || a.key.localeCompare(b.key)
    if (sort === 'count-desc') return b.count - a.count || byName
    if (sort === 'institution-asc' && filter === 'all') {
      if (!a.sortInstitution || !b.sortInstitution) return Number(!a.sortInstitution) - Number(!b.sortInstitution) || byName
      return compareLibraryCollectionNames(a.sortInstitution, b.sortInstitution) || byName
    }
    return byName
  })
}

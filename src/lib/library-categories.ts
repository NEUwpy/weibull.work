import mapping from '../data/library-categories.json'

export interface LibraryCategory {
  key: string
  name: string
  groupKey: string
  groupName: string
}

interface CategorizedPaper { category?: LibraryCategory }

const other: LibraryCategory = { key: 'other', name: '其他主题', groupKey: 'other', groupName: '其他主题' }
export const libraryCategoryMappingVersion = JSON.stringify(mapping)

/** Map the actual selected source directory; never infer a topic from a paper ID. */
export function libraryCategoryForSource(directory: string): LibraryCategory {
  const segments = directory.split(/[\\/]+/)
  for (const group of mapping) {
    const start = segments.lastIndexOf(group.source)
    if (start < 0) continue
    const descendants = segments.slice(start + 1)
    const child = group.children.find(item => descendants.includes(item.source))
    if (child) return { key: `${group.key}/${child.key}`, name: child.name, groupKey: group.key, groupName: group.name }
    // A newly selected source category can appear before it has an editorial label.
    const folder = descendants.find(segment => /^\d{3}_(?!$)/.test(segment))
    if (folder) return { key: `${group.key}/${folder.slice(0, 3)}`, name: folder.slice(4), groupKey: group.key, groupName: group.name }
    return { key: group.key, name: group.name, groupKey: group.key, groupName: group.name }
  }
  return other
}

export function validLibraryCategoryFilter(value: string): boolean {
  return value === 'all' || value === 'other' || /^\d{3}(?:\/\d{3})?$/.test(value)
}

export function matchesLibraryCategory(paper: CategorizedPaper, filter = 'all'): boolean {
  const category = paper.category ?? other
  return filter === 'all' || category.key === filter || category.groupKey === filter
}

/** Navigation and all its counts are derived from the currently selected cards. */
export function libraryCategoryGroups(papers: CategorizedPaper[]) {
  const groups = new Map<string, { key: string; name: string; count: number; categories: Map<string, LibraryCategory & { count: number }> }>()
  for (const paper of papers) {
    const category = paper.category ?? other
    let group = groups.get(category.groupKey)
    if (!group) {
      group = { key: category.groupKey, name: category.groupName, count: 0, categories: new Map() }
      groups.set(group.key, group)
    }
    group.count++
    const entry = group.categories.get(category.key) ?? { ...category, count: 0 }
    entry.count++
    group.categories.set(category.key, entry)
  }
  return Array.from(groups.values()).sort((a, b) => a.key.localeCompare(b.key, 'en', { numeric: true }))
    .map(group => ({ ...group, categories: Array.from(group.categories.values()).sort((a, b) => a.key.localeCompare(b.key, 'en', { numeric: true })) }))
}

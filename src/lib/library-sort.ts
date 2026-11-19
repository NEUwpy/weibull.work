export const librarySortOptions = [
  { value: 'year-desc', label: '年份降序' },
  { value: 'year-asc', label: '年份升序' },
  { value: 'id-asc', label: '编号顺序' },
  { value: 'impact-desc', label: '影响因子降序' },
  { value: 'relevance', label: '相关度' },
] as const

export type LibrarySort = typeof librarySortOptions[number]['value']

export function isLibrarySort(value: string): value is LibrarySort {
  return librarySortOptions.some(option => option.value === value)
}

type SortablePaper = { slug: string; year?: number; impactFactor?: number }

/** Missing values stay last; IDs provide a stable tie break. */
export function compareLibraryOrder(left: SortablePaper, right: SortablePaper, sort: LibrarySort): number {
  const idOrder = () => left.slug.localeCompare(right.slug, 'en', { numeric: true })
  if (sort === 'id-asc' || sort === 'relevance') return idOrder()
  if (sort === 'impact-desc' && left.impactFactor !== right.impactFactor) {
    return (right.impactFactor ?? -1) - (left.impactFactor ?? -1)
  }
  const a = Number.isInteger(left.year) && left.year! > 0 ? left.year! : 0
  const b = Number.isInteger(right.year) && right.year! > 0 ? right.year! : 0
  if (!a || !b) return a ? -1 : b ? 1 : idOrder()
  return (sort === 'year-asc' ? a - b : b - a) || idOrder()
}

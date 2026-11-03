export const librarySortOptions = [
  { value: 'year-desc', label: '年份降序' },
  { value: 'year-asc', label: '年份升序' },
  { value: 'id-asc', label: '编号顺序' },
  { value: 'relevance', label: '相关度' },
] as const

export type LibrarySort = typeof librarySortOptions[number]['value']

export function isLibrarySort(value: string): value is LibrarySort {
  return librarySortOptions.some(option => option.value === value)
}

/** Missing publication years stay last in either direction; IDs provide a stable tie break. */
export function compareLibraryOrder(left: { slug: string; year?: number }, right: { slug: string; year?: number }, sort: LibrarySort): number {
  const idOrder = () => left.slug.localeCompare(right.slug, 'en', { numeric: true })
  if (sort === 'id-asc' || sort === 'relevance') return idOrder()
  const a = Number.isInteger(left.year) && left.year! > 0 ? left.year! : 0
  const b = Number.isInteger(right.year) && right.year! > 0 ? right.year! : 0
  if (!a || !b) return a ? -1 : b ? 1 : idOrder()
  return (sort === 'year-desc' ? b - a : a - b) || idOrder()
}

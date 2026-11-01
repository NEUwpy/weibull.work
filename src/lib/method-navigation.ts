export const METHOD_SECTIONS = {
  process: 'flow', calculation: 'lab', analysis: 'analysis', applicability: 'examples', verification: 'cases', compare: 'compare',
} as const
export type MethodTab = (typeof METHOD_SECTIONS)[keyof typeof METHOD_SECTIONS] | null
export function methodTabFromPath(pathname: string): MethodTab {
  const section = pathname.split('/')[3]
  return METHOD_SECTIONS[section as keyof typeof METHOD_SECTIONS] ?? null
}
export function methodHref(method: string, tab: MethodTab, query: { toString(): string } | string = ''): string {
  const section = Object.entries(METHOD_SECTIONS).find(([, value]) => value === tab)?.[0]
  const search = query.toString()
  return `/methods/${encodeURIComponent(method)}${section ? `/${section}` : ''}${search ? `?${search}` : ''}`
}

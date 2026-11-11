export const METHOD_SECTIONS = {
  calculation: 'lab', analysis: 'analysis', applicability: 'examples', verification: 'cases', compare: 'compare',
} as const
export type MethodTab = (typeof METHOD_SECTIONS)[keyof typeof METHOD_SECTIONS] | null
export function methodTabFromPath(pathname: string): MethodTab {
  const section = pathname.split('/')[3]
  if (section === 'process') return 'lab'
  return METHOD_SECTIONS[section as keyof typeof METHOD_SECTIONS] ?? null
}

export function legacyProcessHref(method: string, query: URLSearchParams): string {
  const params = new URLSearchParams(query)
  const step = Number(params.get('step'))
  params.set('sourceStep', Number.isSafeInteger(step) && step > 0 ? String(step) : '1')
  params.delete('step')
  return methodHref(method, 'lab', params)
}
export function methodHref(method: string, tab: MethodTab, query: { toString(): string } | string = ''): string {
  const section = Object.entries(METHOD_SECTIONS).find(([, value]) => value === tab)?.[0]
  const search = query.toString()
  return `/methods/${encodeURIComponent(method)}${section ? `/${section}` : ''}${search ? `?${search}` : ''}`
}

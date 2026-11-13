export const METHOD_SECTIONS = {
  calculation: 'lab', analysis: 'analysis', verification: 'cases', compare: 'compare',
} as const
export type MethodTab = (typeof METHOD_SECTIONS)[keyof typeof METHOD_SECTIONS] | null

export const METHOD_ANALYSIS_SOURCES = [
  { id: 'basic', label: '预计算结果' },
  { id: 'simulation', label: '现场计算' },
] as const

type MethodQuery = Pick<URLSearchParams, 'get'>

export function methodAnalysisTruth(query: MethodQuery) {
  const beta = Number(query.get('trueBeta')), eta = Number(query.get('trueEta'))
  const gamma = query.get('model') === '2p' ? 0 : Number(query.get('trueGamma'))
  if ([beta, eta, gamma].every(Number.isFinite) && beta > 0 && eta > 0) return { beta, eta, gamma }
}

export function methodAnalysisSource(query: MethodQuery): (typeof METHOD_ANALYSIS_SOURCES)[number]['id'] {
  const source = query.get('source')
  if (source === 'simulation' || (source === null && (query.get('analysisBatch') || methodAnalysisTruth(query)))) return 'simulation'
  return 'basic'
}

export function methodTabFromPath(pathname: string): MethodTab {
  const section = pathname.split('/')[3]
  if (section === 'process') return 'lab'
  if (section === 'applicability') return 'analysis'
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

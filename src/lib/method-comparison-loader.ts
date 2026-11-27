import { requestMethodComparisonSimulation, type MethodComparisonParams, type MethodComparisonRow } from './method-comparison'
import type { SimulationBatch } from './simulation-analysis'

export interface MethodComparisonCatalog {
  chunks: string[]
  parsedParams: Partial<Record<keyof MethodComparisonParams | 'd', number[]>>
  total: number
}

export interface MethodComparisonSelection {
  params: MethodComparisonParams
  complete: boolean
  multiple: boolean
}

type LoadStage = 'catalog' | 'archive' | 'simulation'

export type MethodComparisonResult =
  | { status: 'loading'; stage: 'catalog' | 'archive' }
  | { status: 'waiting-for-parameters' | 'missing' | 'waiting-for-simulation' | 'simulating' }
  | { status: 'error'; stage: LoadStage; message: string }
  | { status: 'ready'; source: 'archive'; filename: string; rows: MethodComparisonRow[] }
  | ({ status: 'ready'; source: 'simulation' } & SimulationBatch)

export interface MethodComparisonState {
  selectionKey: string
  catalog: MethodComparisonCatalog | null
  result: MethodComparisonResult
}

const ARCHIVE_PARAMS = [
  ['beta', 'b'], ['eta', 'e'], ['gamma', 'g'], ['n', 'n'], ['offset', 'd'],
  ['rep', 'rep'], ['seed', 'seed'], ['step', 'step']
] as const

function isMDM(methodId: string): boolean {
  return methodId.toLowerCase() === 'mdm'
}

export function methodComparisonSelectionKey(methodId: string, selection: MethodComparisonSelection): string {
  return JSON.stringify([
    ...ARCHIVE_PARAMS.map(([key]) => key === 'offset' && !isMDM(methodId) ? null : selection.params[key]),
    selection.complete, selection.multiple
  ])
}

function archiveFilename(methodId: string, params: MethodComparisonParams): string {
  return ARCHIVE_PARAMS
    .filter(([key]) => key !== 'offset' || isMDM(methodId))
    .map(([key, prefix]) => `${prefix}${params[key]}`)
    .join('_') + '.csv'
}

export function initialMethodComparisonParams(catalog: MethodComparisonCatalog): Partial<MethodComparisonParams> {
  const parsed = catalog.chunks.map(filename => {
    const parts = filename.slice(0, -4).split('_')
    const params: Partial<MethodComparisonParams> = {}
    for (const [key, prefix] of ARCHIVE_PARAMS) {
      const part = parts.find(value => value.startsWith(prefix) && /^\d+(?:\.\d+)?$/.test(value.slice(prefix.length)))
      if (part) params[key] = Number(part.slice(prefix.length))
    }
    return params
  })
  const matchesDefaultTruth = (params: Partial<MethodComparisonParams>) => params.beta === 2 && params.eta === 1000
  return parsed.find(params => matchesDefaultTruth(params) && (params.offset === undefined || params.offset === 0.1))
    ?? parsed.find(matchesDefaultTruth)
    ?? parsed[0]
    ?? {}
}

function parseArchiveRows(text: string, params: MethodComparisonParams): MethodComparisonRow[] {
  const [header, ...lines] = text.trim().split(/\r?\n/)
  const columns = new Map(header.split(',').map((name, index) => [name, index]))
  return lines.filter(Boolean).map(line => {
    const values = line.split(',')
    const read = (key: string) => {
      const value = values[columns.get(key) ?? -1]
      if (!value?.trim()) return null
      const number = Number(value)
      return Number.isFinite(number) ? number : null
    }
    // The requested archive filename encodes these settings. Some early CSV files omit gamma.
    const beta = read('beta_true') ?? params.beta
    const eta = read('eta_true') ?? params.eta
    const gamma = read('gamma') ?? params.gamma
    const n = read('sample_size') ?? params.n
    if (beta !== params.beta || eta !== params.eta || gamma !== params.gamma || n !== params.n) {
      throw new Error('历史分片的真值或样本量与文件名不一致。')
    }
    return {
      beta_true: beta, eta_true: eta, gamma,
      sample_size: n, offset_value: read('offset_value') ?? undefined, sim_id: read('sim_id') ?? 0,
      est_beta: read('est_beta'), est_eta: read('est_eta'), est_gamma: read('est_gamma'),
      bias_beta: read('bias_beta'), bias_eta: read('bias_eta'), bias_gamma: read('bias_gamma'), r_squared: read('r_squared')
    }
  })
}

interface ActiveSelection {
  methodId: string
  selection: MethodComparisonSelection
  state: MethodComparisonState
  request: AbortController
  simulationTimer?: ReturnType<typeof setTimeout>
}

export function createMethodComparisonLoader(
  onState: (methodId: string, state: MethodComparisonState) => void,
  request: typeof fetch = fetch
) {
  const session = new AbortController()
  const catalogs = new Map<string, Promise<MethodComparisonCatalog>>()
  const active = new Map<string, ActiveSelection>()

  function catalog(methodId: string): Promise<MethodComparisonCatalog> {
    const cached = catalogs.get(methodId)
    if (cached) return cached
    const result = request(`/api/studies/${encodeURIComponent(methodId.toLowerCase())}/chunks`, { signal: session.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`无法读取分片目录（HTTP ${response.status}）。`)
        const data = await response.json() as MethodComparisonCatalog
        if (!data || !Array.isArray(data.chunks) || !data.parsedParams) throw new Error('分片目录格式无效。')
        return data
      })
    catalogs.set(methodId, result)
    return result
  }

  function current(entry: ActiveSelection): boolean {
    return active.get(entry.methodId) === entry && !entry.request.signal.aborted
  }

  function publish(entry: ActiveSelection, result: MethodComparisonResult): void {
    if (!current(entry)) return
    entry.state = { ...entry.state, result }
    onState(entry.methodId, entry.state)
  }

  function stop(entry: ActiveSelection): void {
    clearTimeout(entry.simulationTimer)
    entry.request.abort()
  }

  function fail(entry: ActiveSelection, stage: LoadStage, error: unknown): void {
    publish(entry, { status: 'error', stage, message: error instanceof Error ? error.message : String(error) })
  }

  async function simulate(entry: ActiveSelection): Promise<void> {
    if (!current(entry)) return
    clearTimeout(entry.simulationTimer)
    publish(entry, { status: 'simulating' })
    try {
      const batch = await requestMethodComparisonSimulation(entry.methodId, entry.selection.params, entry.request.signal, request)
      publish(entry, { status: 'ready', source: 'simulation', ...batch })
    } catch (error) {
      fail(entry, 'simulation', error)
    }
  }

  async function load(entry: ActiveSelection): Promise<void> {
    let stage: LoadStage = 'catalog'
    try {
      const index = await catalog(entry.methodId)
      if (!current(entry)) return
      entry.state = { ...entry.state, catalog: index }
      if (!entry.selection.complete) {
        publish(entry, { status: 'waiting-for-parameters' })
        return
      }
      const filename = archiveFilename(entry.methodId, entry.selection.params)
      if (!index.chunks.includes(filename)) {
        if (entry.selection.multiple) {
          publish(entry, { status: 'missing' })
        } else {
          publish(entry, { status: 'waiting-for-simulation' })
          entry.simulationTimer = setTimeout(() => void simulate(entry), 300)
        }
        return
      }
      stage = 'archive'
      publish(entry, { status: 'loading', stage })
      const url = `/studies/${encodeURIComponent(entry.methodId.toLowerCase())}/chunks/${encodeURIComponent(filename)}`
      const response = await request(url, { signal: entry.request.signal })
      if (!response.ok) throw new Error(`无法读取历史分片（HTTP ${response.status}）。`)
      const rows = parseArchiveRows(await response.text(), entry.selection.params)
      if (rows.length === 0) throw new Error('历史分片没有结果记录。')
      publish(entry, { status: 'ready', source: 'archive', filename, rows })
    } catch (error) {
      fail(entry, stage, error)
    }
  }

  function start(methodId: string, selection: MethodComparisonSelection): void {
    const previous = active.get(methodId)
    if (previous) stop(previous)
    const entry: ActiveSelection = {
      methodId, selection, request: new AbortController(),
      state: {
        selectionKey: methodComparisonSelectionKey(methodId, selection),
        catalog: previous?.state.catalog ?? null,
        result: { status: 'loading', stage: 'catalog' }
      }
    }
    active.set(methodId, entry)
    onState(methodId, entry.state)
    void load(entry)
  }

  return {
    catalog,
    select(methodIds: string[], selection: MethodComparisonSelection): void {
      active.forEach((entry, id) => {
        if (methodIds.includes(id)) return
        stop(entry)
        active.delete(id)
      })
      for (const id of methodIds) {
        if (active.get(id)?.state.selectionKey !== methodComparisonSelectionKey(id, selection)) start(id, selection)
      }
    },
    retry(methodId: string): void {
      const entry = active.get(methodId)
      if (!entry) return
      const { result } = entry.state
      if (result.status === 'waiting-for-simulation' || (result.status === 'error' && result.stage === 'simulation')) {
        void simulate(entry)
      } else if (result.status === 'error') {
        catalogs.delete(methodId)
        start(methodId, entry.selection)
      }
    },
    dispose(): void {
      session.abort()
      active.forEach(stop)
      active.clear()
    }
  }
}

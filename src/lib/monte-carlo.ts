export type WorkbookCell = string | number | boolean | null
export type WorkbookView = 'samples' | 'results'
export interface WorkbookBlock { method: string; delta: number | null; label: string; column: number; parameterLabels: string[] }
export interface WorkbookSheet { name: string; rows: WorkbookCell[][]; formats: string[][]; merges: [number, number, number, number][] }
export interface WorkbookGroup { samples: WorkbookCell[][]; resultRows: WorkbookCell[][]; blocks: WorkbookBlock[]; sampleSheet: string; resultSheet: string }
export interface WorkbookSource {
  kind: 'archive' | 'imported'; calculationTime?: string | null; importedAt?: string
  protocol?: string; directory?: string; manifestSha256?: string
  configuration?: Record<string, unknown>; code?: { path: string; sha256: string }[]
}
export interface MonteCarloWorkbook {
  schemaVersion: 1; id: string; filename: string; title: string; truth: number[] | null; sha256: string
  groups: Record<string, WorkbookGroup>; sheets: WorkbookSheet[]; source: WorkbookSource
}
export interface WorkbookCard {
  id: string; title: string; truth: number[]; ns: number[]; methods: string[]; offsets: number[]
  protocol: string; filename: string; workbookSha256: string; available?: boolean; error?: string
}
export const WORKBOOK_VIEWS: WorkbookView[] = ['samples', 'results']
export function workbookMatches(card: WorkbookCard, truth: number[], n: number, method: string): boolean {
  return card.available !== false && card.ns.includes(n) && card.methods.includes(method) && card.truth.every((v, i) => v === truth[i])
}
export function formatWorkbookCell(value: WorkbookCell | undefined, format = '0.000000'): string {
  if (value === null || value === undefined) return ''
  if (typeof value !== 'number') return String(value)
  return /^0\.0+$/.test(format) ? value.toFixed(Math.min(20, format.length - 2)) : String(value)
}

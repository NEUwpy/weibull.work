import type { MethodFlow } from './method-flow'
import type { CalculationTrace } from './calculation-trace'

/** Persistent numerical evidence. Project names and workbook paths are not part of this format. */
export interface CalculationRecord {
  id: number
  input: { observations: number[] }
  result: { beta: number | null; eta: number | null; gamma: number | null; rSquared: number | null; converged: boolean | string }
  calculation?: CalculationTrace
  traceData?: unknown
  process?: Omit<MDMProcessRun, 'id' | 'sample' | 'beta' | 'eta' | 'gamma' | 'rSquared'>
}

export interface CalculationRecordSet {
  schemaVersion: 1
  method: string
  model: '3p'
  title: string
  settings: Record<string, number | string | boolean>
  truth: number[]
  implementation: { sources: { path: string; sha256: string }[] }
  flow?: MethodFlow
  records: CalculationRecord[]
}

export interface MDMProcessTrace {
  profile: [gamma: number, sigma: number, beta: number][]
  shape: [beta: number, sigma: number][]
  pseudoScales: [denominator: number, eta: number][]
  scaleSum: number
  trialShapes?: [beta: number, sigma: number][][]
}
export interface MDMProcessRun {
  id: number; sample: number[]; beta: number; eta: number; gamma: number; rSquared: number
  curve: { gamma: number; gradient: number }[]; bracket: [number, number]; trace: MDMProcessTrace
  solver?: string; branch?: 'ready' | 'zero' | 'extrapolated'; offset?: number
  sampleRanks?: number[]; rankMethod?: string
}
export interface MDMProcessBatch {
  selection: { id: string; n: number; delta: number }
  title: string; truth: number[]; flow: MethodFlow; runs: MDMProcessRun[]
}

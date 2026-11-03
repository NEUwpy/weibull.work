export interface FlowVariable { symbol: string; meaning: string; code: string }
export interface FlowSource { path: string; sha256: string; lines: string[] }
export interface FlowReference { file: string; symbol?: string; label: string; start: number; end: number }
export interface FlowStep {
  id: number; name: string; description: string; basis: string; notes: string
  formula: { expression: string; symbols: { symbol: string; meaning: string }[]; explanation: string }
  inputs: FlowVariable[]; outputs: FlowVariable[]; sources: FlowReference[]
  primarySource?: number
  depth: number; number: string; context?: string; kind: 'step' | 'call' | 'loop' | 'condition' | 'return'
  isLoop?: boolean; loopCount?: string
}
export interface MethodFlow {
  schemaVersion: 2; methodId: string; methodName: string; description: string; implementation: string
  steps: FlowStep[]; sources: FlowSource[]
  artifacts: { path: string; sha256: string; bytes: number }[]
}

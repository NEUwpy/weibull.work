"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import dynamic from 'next/dynamic'
import { useSearchParams } from 'next/navigation'
import { Code2, X } from 'lucide-react'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import { calculationSteps } from '@/lib/calculation-steps'

const VariableFlowViewer = dynamic(() => import('./VariableFlowViewer'))

type SourceSelection = { stage: number; step?: number; fromUrl?: boolean }
const StageContext = createContext<{
  activeStage: number
  selectStage: (index: number) => void
  openSource?: (stage: number, step?: number) => void
  sourceRequest?: SourceSelection | null
} | null>(null)

export function useCalculationStage() {
  return useContext(StageContext)
}

export function CalculationStageProvider({ method, sourceAvailable, children }: {
  method: string; sourceAvailable: boolean; children: ReactNode
}) {
  const sourceStep = Number(useSearchParams().get('sourceStep'))
  const inlineSource = method === 'mdm' || method === 'mle'
  const stages = calculationSteps[method]
  const [activeStage, selectStage] = useState(0)
  const [source, setSource] = useState<SourceSelection | null>(null)

  useEffect(() => {
    if (!sourceAvailable || !Number.isSafeInteger(sourceStep) || sourceStep < 1) return
    const stage = stages?.findIndex(item => item.programSteps.includes(sourceStep)) ?? -1
    selectStage(Math.max(0, stage))
    setSource({ stage, step: sourceStep, fromUrl: true })
  }, [sourceStep, sourceAvailable, stages])

  return <StageContext.Provider value={{ activeStage, selectStage, openSource: sourceAvailable ? (stage, step) => setSource({ stage, step }) : undefined,
    sourceRequest: inlineSource ? source : undefined }}>
    {children}
    {!inlineSource && source && sourceAvailable && <CalculationSourceDialog method={method} selection={source} close={() => setSource(null)} />}
  </StageContext.Provider>
}

export function CalculationSourceButton({ stage = -1, programStep, label }: { stage?: number; programStep?: number; label?: string }) {
  const stageContext = useCalculationStage()
  const openSource = stageContext?.openSource
  const inlineSource = stageContext?.sourceRequest !== undefined
  if (!openSource) return null
  return <button type="button" aria-haspopup={inlineSource ? undefined : 'dialog'} aria-label={label ? `查看${label}的源码` : undefined} onClick={() => openSource(stage, programStep)}
    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-blue-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500">
    <Code2 size={16} aria-hidden="true" />查看源码
  </button>
}

function CalculationSourceDialog({ method, selection, close }: { method: string; selection: SourceSelection; close: () => void }) {
  const { dialog, closeButton } = usePreviewDialog(close)
  const stage = calculationSteps[method]?.[selection.stage]
  return <dialog {...dialog} aria-labelledby="calculation-source-title"
    className="fixed inset-y-0 left-auto right-0 m-0 h-dvh max-h-none w-full max-w-none overflow-y-auto overscroll-contain bg-white text-slate-900 shadow-2xl backdrop:bg-slate-900/30 sm:w-[min(900px,90vw)]">
    <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
      <h2 id="calculation-source-title" className="text-lg font-semibold">{stage ? `${stage.label} · 源码` : '计算过程源码'}</h2>
      <button ref={closeButton} type="button" aria-label="关闭源码" onClick={close}
        className="shrink-0 rounded-lg p-2 text-slate-600 hover:bg-slate-100"><X size={22} aria-hidden="true" /></button>
    </header>
    <div className="min-w-0 p-4 sm:p-6">
      <VariableFlowViewer methodId={method} programSteps={stage?.programSteps} focusStep={selection.step} />
    </div>
  </dialog>
}

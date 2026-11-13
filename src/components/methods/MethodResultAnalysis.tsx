'use client'

import { useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import MethodBuildStatus from './MethodBuildStatus'
import AnalysisSampleCard from './shared/studies/AnalysisSampleCard'
import MonteCarloWorkbookViewer from './shared/studies/MonteCarloWorkbookViewer'
import type { MethodCapability } from '@/lib/method-status'
import { parseMdmOffsetOption } from '@/lib/calculator-state'
import { methodAnalysisSource, methodAnalysisTruth } from '@/lib/method-navigation'

export default function MethodResultAnalysis({ methodId, capability }: { methodId: string; capability?: MethodCapability }) {
  const query = useSearchParams()
  const analysisBatch = query.get('analysisBatch')
  const truth = methodAnalysisTruth(query)
  const offset = parseMdmOffsetOption(query.get('offset'))
  const sampleSize = Number(query.get('simulationN'))
  const is3P = query.get('model') !== '2p'
  const hasCard = capability?.calculatorEnabled === true
  const live = hasCard && methodAnalysisSource(query) === 'simulation'
  const [liveVisited, setLiveVisited] = useState(live)

  useEffect(() => { if (live) setLiveVisited(true) }, [live])

  return <div className="space-y-4">
    {!live && <MonteCarloWorkbookViewer methodId={methodId} />}
    {hasCard && (live || liveVisited) && <div hidden={!live}>
      <AnalysisSampleCard key={JSON.stringify([analysisBatch, truth, offset, sampleSize, is3P])}
        methodId={methodId} batchId={analysisBatch} initialTruth={truth} initialOffset={offset} initialIs3P={is3P}
        initialSize={Number.isSafeInteger(sampleSize) && sampleSize > 0 ? sampleSize : undefined} />
    </div>}
    {!hasCard && analysisBatch && <MethodBuildStatus label="现场计算"
      status={capability?.layer1.calculator.status ?? 'todo'} reason={capability?.layer1.calculator.reason}
      evidence={capability?.layer1.calculator.evidence} />}
  </div>
}

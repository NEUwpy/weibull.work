'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'
import dynamic from 'next/dynamic'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { ArchivedMDMWorkspace } from './mdm/ArchivedMDMWorkspace'
import type { ArchivedMDMProcess, WorkbookProcessSelection } from '@/lib/monte-carlo'
import styles from './CalculationInputCard.module.css'
import type { CalculatorParameters } from '@/lib/calculator-state'
import type { DataSource } from '@/lib/weibull'

const WorkbookPicker = dynamic(() => import('./shared/studies/MonteCarloWorkbookViewer'), {
  loading: () => <p className="p-4 text-sm text-slate-500" role="status">正在读取适用范围表格…</p>,
})

export function CalculationInputCard({ sampleCard, children, allowArchive, onLoadSources }: {
  sampleCard: ReactNode; children: ReactNode; allowArchive: boolean
  onLoadSources?: (sources: DataSource[], origin: CalculatorParameters | undefined, offset: number) => void
}) {
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [archiveVisited, setArchiveVisited] = useState(false)
  const [process, setProcess] = useState<ArchivedMDMProcess | null>(null)
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])

  function reset() {
    request.current?.abort()
    setProcess(null)
    setSelectedRun(null)
    setError('')
    setLoading(false)
  }

  async function show({ id, n, delta }: WorkbookProcessSelection) {
    reset()
    const controller = new AbortController()
    request.current = controller
    setLoading(true)
    try {
      const query = new URLSearchParams({ n: String(n), delta: String(delta) })
      const response = await fetch(`/api/monte-carlo/${encodeURIComponent(id)}/process?${query}`, { signal: controller.signal })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || '归档计算过程读取失败')
      if (!controller.signal.aborted) setProcess(result)
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '归档计算过程读取失败')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }

  if (!allowArchive) return <>{sampleCard}{children}</>
  const switchLabel = archiveOpen ? '切回样本卡片' : '切换到适用范围结果'
  return <>
    <div className={styles.inputCard} data-calculation-input={archiveOpen ? 'archive' : 'sample'}>
      <div hidden={archiveOpen}>{sampleCard}</div>
      {archiveVisited && <div hidden={!archiveOpen} className={styles.archiveCard}>
        <WorkbookPicker methodId="mdm" process={{ show, reset, loading, selectedRun, selectRun: process ? setSelectedRun : undefined,
          loadSources: onLoadSources && ((sources, origin, offset) => {
            reset()
            setArchiveOpen(false)
            onLoadSources(sources, origin, offset)
          }) }} />
      </div>}
      <button type="button" className={styles.switchButton} data-direction={archiveOpen ? 'previous' : 'next'}
        title={switchLabel} aria-label={switchLabel} onClick={() => {
          setArchiveVisited(true)
          setArchiveOpen(!archiveOpen)
        }}>
        {archiveOpen ? <ChevronLeft size={22} aria-hidden="true" /> : <ChevronRight size={22} aria-hidden="true" />}
      </button>
    </div>
    {archiveOpen ? error ? <p role="alert" className="text-sm text-red-700">{error}</p>
      : process && <ArchivedMDMWorkspace process={process} selectedRun={selectedRun} onSelect={setSelectedRun} /> : children}
  </>
}

'use client'

import { useState } from 'react'
import { analysisWorkbookCsv } from '@/lib/analysis-workbook'
import type { CalculatorParameters } from '@/lib/calculator-state'
import type { WorkbookCell, WorkbookGroup, WorkbookRun, WorkbookView } from '@/lib/monte-carlo'
import WorkbookResults, { workbookDownload } from './WorkbookResults'
import styles from './Workbook.module.css'

export function SimulationWorkbook({ n, truth, group, runs, filename }: {
  n: number
  truth: CalculatorParameters
  group: WorkbookGroup
  runs: ReadonlyMap<WorkbookCell, WorkbookRun>
  filename: string
}) {
  const [view, setView] = useState<WorkbookView>('results')
  const csvName = `${filename}-${view}.csv`
  const label = `下载${view === 'samples' ? '样本数据' : '估计结果'} CSV`

  function download() {
    const url = URL.createObjectURL(new Blob([analysisWorkbookCsv(view, group, runs, n)], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = csvName
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return <div className={styles.workbook}>
    <WorkbookResults n={n} group={group} block={group.blocks[0]} truth={[truth.beta, truth.eta, truth.gamma]}
      view={view} onViewChange={setView} runs={runs}
      download={workbookDownload(csvName, download, label)} />
  </div>
}

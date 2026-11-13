'use client'
import React, { useEffect, useId, useState } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import ChoiceSelect from '@/components/shared/ChoiceSelect'
import { MonteCarloWorkbook, WorkbookCard, WorkbookView, WorkbookProcessSelection, WORKBOOK_VIEWS, workbookMatches } from '@/lib/monte-carlo'
import WorkbookResults, { workbookDownload } from './WorkbookResults'
import styles from './Workbook.module.css'
import { workbookSampleSources } from '@/lib/calculator-batch'
import type { CalculatorParameters } from '@/lib/calculator-state'
import type { DataSource } from '@/lib/weibull'

const cache = new Map<string, MonteCarloWorkbook>()
async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init), result = await response.json()
  if (!response.ok) throw new Error(result.error || '无法读取数据')
  return result
}

export default function MonteCarloWorkbookViewer({ methodId, process }: { methodId: string; process?: {
  show: (selection: WorkbookProcessSelection) => void; reset: () => void
  selectedRun?: number | null; selectRun?: (id: number) => void; loading: boolean
  loadSources?: (sources: DataSource[], origin: CalculatorParameters | undefined, offset: number) => void
} }) {
  const router = useRouter(), pathname = usePathname(), query = useSearchParams()
  const [catalog, setCatalog] = useState<WorkbookCard[] | null>(null), [book, setBook] = useState<MonteCarloWorkbook | null>(null)
  const [error, setError] = useState(''), [loading, setLoading] = useState(true)
  const settingsId = useId()
  const cards = catalog ?? []
  const requestedId = query.get('batch')
  const card = requestedId ? cards.find(c => c.id === requestedId) : cards.find(c => c.available !== false && c.methods.includes(methodId) && c.truth.join(',') === '2,1000,500') || cards.find(c => c.available !== false && c.methods.includes(methodId))
  const nParam = Number(query.get('n') || (process ? card?.mdmProcess?.n : undefined) || 7)
  const n = card?.ns.includes(nParam) ? nParam : card?.ns[0] ?? 7
  const deltaParam = Number(query.get('delta') ?? .1), delta = card?.offsets.includes(deltaParam) ? deltaParam : card?.offsets[0] ?? .1
  const view = WORKBOOK_VIEWS.includes(query.get('view') as WorkbookView) ? query.get('view') as WorkbookView : 'results'
  const group = book?.id === card?.id ? book?.groups[String(n)] : undefined
  const block = group?.blocks.find(b => b.method === methodId && (methodId !== 'mdm' || b.delta === delta))
  const selection = process ? String(process.selectedRun ?? '') : query.get('sample')

  useEffect(() => { const controller = new AbortController(); readJson<{ entries: WorkbookCard[] }>('/api/monte-carlo', { signal: controller.signal })
    .then(r => setCatalog(r.entries)).catch(e => {
      if (!controller.signal.aborted) { setError(e.message); setLoading(false) }
    }); return () => controller.abort() }, [])
  useEffect(() => {
    if (!catalog) return
    if (!card) { setError(''); setLoading(false); return }
    if (card.available === false) { setError(card.error || '该批次外部数据缺失'); setLoading(false); return }
    if (cache.has(card.id)) { setBook(cache.get(card.id)!); setLoading(false); setError(''); return }
    const controller = new AbortController(); setLoading(true); setError('')
    readJson<MonteCarloWorkbook>('/api/monte-carlo/' + card.id, { signal: controller.signal }).then(b => { cache.set(b.id, b); setBook(b) })
      .catch(e => { if (e.name !== 'AbortError') setError(e.message) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [catalog, card])
  useEffect(() => { process?.reset() }, [card?.id, n, delta])

  function navigate(values: Record<string, string | number | null>) {
    const next = new URLSearchParams(query.toString())
    if (card) next.set('batch', card.id)
    for (const [key, value] of Object.entries(values)) value === null ? next.delete(key) : next.set(key, String(value))
    router.push(`${pathname}?${next}`, { scroll: false })
  }
  function parameterOptions(index: number) {
    return Array.from(new Set(cards.flatMap(c => c.truth.length === 3 ? [c.truth[index]] : []))).sort((a, b) => a - b).map(value => {
      const truth = [...(card?.truth || [])]; truth[index] = value
      return { value, disabled: !cards.some(c => workbookMatches(c, truth, n, methodId)) }
    })
  }
  function chooseParameter(index: number, value: string | number) {
    const truth = [...(card?.truth || [])]; truth[index] = Number(value)
    const target = cards.find(c => workbookMatches(c, truth, n, methodId))
    if (target) navigate({ batch: target.id, sample: null })
  }
  const currentBook = book?.id === card?.id ? book : null
  const noData = !loading && !card
  const processAvailable = !!(currentBook && card?.mdmProcess?.n === n && card.mdmProcess.delta === delta && methodId === 'mdm')

  return <div className={styles.workbook} data-process-picker={process ? true : undefined}>
    {card && <section aria-labelledby={settingsId} className={styles.settings}>
      <h2 id={settingsId} className={styles.settingsTitle}>{process ? '适用范围结果' : '参数设置'}</h2>
      <div className={styles.controls}>
      <div className={styles.parameters} aria-label="分布参数">
      {card.truth.length === 3 && ['形状 β', '尺度 η', '位置 γ'].map((label, i) => <div className={styles.control} key={label}><ChoiceSelect label={['β', 'η', 'γ'][i]} displayLabel={label} value={card.truth[i]} options={parameterOptions(i)} onChange={v => chooseParameter(i, v)} /></div>)}
      {methodId === 'mdm' && <div className={styles.control}><ChoiceSelect label="δ" displayLabel="偏移量 δ" value={delta} options={card.offsets.map(v => ({ value: v, label: v.toFixed(2) }))} onChange={v => navigate({ delta: v })} /></div>}
      </div>
      <div className={styles.sampleControl}><ChoiceSelect tone="sample" label="样本量" displayLabel="样本量 n" value={n} options={Array.from(new Set(cards.flatMap(c => c.ns))).sort((a, b) => a - b).map(value => ({ value, disabled: !card.ns.includes(value) }))} onChange={v => navigate({ n: v, sample: null })} /></div>
    </div>
      {process && <button type="button" className={styles.showProcess} disabled={!processAvailable || process.loading}
        onClick={() => process.show({ id: card.id, n, delta, recordId: card.mdmProcess!.recordId })}>
        {process.loading ? '读取中…' : processAvailable ? '显示这组过程' : '暂无整组过程'}
      </button>}
      {process?.loadSources && <button type="button" className={styles.showProcess} disabled={!currentBook || !group || !block || loading}
        onClick={() => {
          try {
            const sources = workbookSampleSources(currentBook!, n, methodId, delta)
            process.loadSources!(sources, sources[0]?.generatedFrom, delta)
          } catch (cause) { setError(cause instanceof Error ? cause.message : '载入失败') }
        }}>载入卡片</button>}
    </section>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {loading ? <p role="status" className={styles.empty}>正在读取数据…</p>
      : noData && !error ? <p className={styles.empty}>{requestedId ? '该批次未登记，请检查批次地址。' : '此方法暂无完整样本工作簿。'}</p>
      : currentBook && group && block ? (
        <WorkbookResults key={`${currentBook.id}:${methodId}:${n}`} group={group} block={block} truth={currentBook.truth} n={n}
          view={view} onViewChange={next => navigate({ view: next })} selection={selection}
          onSelect={id => {
            if (process?.selectRun && typeof id === 'number') { process.selectRun(id); return true }
            navigate({ sample: String(id) })
          }}
          sampleHeaders={currentBook.sheets.find(sheet => sheet.name === group.sampleSheet)?.rows[0]}
          sampleFormats={currentBook.sheets.find(sheet => sheet.name === group.sampleSheet)?.formats}
          resultFormats={currentBook.sheets.find(sheet => sheet.name === group.resultSheet)?.formats}
          download={!process && workbookDownload(currentBook.filename, `/api/monte-carlo/${currentBook.id}/export`,
            `下载 Excel（完整${currentBook.sheets.length}张表）`)}
          showStatistics={!process}
        />
      ) : !error && <p className={styles.empty}>该工作簿没有当前方法的估计列。</p>}
  </div>
}

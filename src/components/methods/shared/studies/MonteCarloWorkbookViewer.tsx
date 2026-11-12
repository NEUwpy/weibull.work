'use client'
import React, { useEffect, useRef, useState } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { Download } from 'lucide-react'
import ChoiceSelect from '@/components/shared/ChoiceSelect'
import { formatWorkbookCell as fmt, MonteCarloWorkbook, WorkbookCard, WorkbookCell, WorkbookView, WorkbookProcessSelection, WORKBOOK_VIEWS, workbookMatches } from '@/lib/monte-carlo'
import { paramAbsoluteErrors, summarizeStandardErrors } from '@/lib/metrics'
import { Histogram } from '@/components/ai/charts/Histogram'
import styles from './Workbook.module.css'
import { workbookSampleSources } from '@/lib/calculator-batch'
import type { CalculatorParameters } from '@/lib/calculator-state'
import type { DataSource } from '@/lib/weibull'

const cache = new Map<string, MonteCarloWorkbook>()
const views: { id: WorkbookView; label: string }[] = [{ id: 'samples', label: '样本数据' }, { id: 'results', label: '估计结果' }]
const signed = (value: number) => value === 0 ? '0.000000' : (value > 0 ? '+' : '−') + (Math.abs(value) < .0000005 ? Math.abs(value).toExponential(2) : Math.abs(value).toFixed(6))
const numeric = (v: WorkbookCell): v is number => typeof v === 'number' && Number.isFinite(v)
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
  const [catalog, setCatalog] = useState<WorkbookCard[]>([]), [book, setBook] = useState<MonteCarloWorkbook | null>(null)
  const [error, setError] = useState(''), [loading, setLoading] = useState(true)
  const [detailId, setDetailId] = useState<WorkbookCell>(null)
  const gridRef = useRef<HTMLDivElement>(null), dialogRef = useRef<HTMLDialogElement>(null)
  const positions = useRef<Record<string, { top: number; left: number }>>({})
  const cards = catalog
  const requestedId = query.get('batch')
  const card = requestedId ? cards.find(c => c.id === requestedId) : cards.find(c => c.available !== false && c.methods.includes(methodId) && c.truth.join(',') === '2,1000,500') || cards.find(c => c.available !== false && c.methods.includes(methodId))
  const nParam = Number(query.get('n') || (process ? card?.mdmProcess?.n : undefined) || 7)
  const n = card?.ns.includes(nParam) ? nParam : card?.ns[0] ?? 7
  const deltaParam = Number(query.get('delta') ?? .1), delta = card?.offsets.includes(deltaParam) ? deltaParam : card?.offsets[0] ?? .1
  const view = WORKBOOK_VIEWS.includes(query.get('view') as WorkbookView) ? query.get('view') as WorkbookView : 'results'
  const group = book?.id === card?.id ? book?.groups[String(n)] : undefined
  const block = group?.blocks.find(b => b.method === methodId && (methodId !== 'mdm' || b.delta === delta))
  const positionKey = `${card?.id}:${n}:${view}`
  const selection = process ? String(process.selectedRun ?? '') : query.get('sample')

  useEffect(() => { const controller = new AbortController(); readJson<{ entries: WorkbookCard[] }>('/api/monte-carlo', { signal: controller.signal })
    .then(r => setCatalog(r.entries)).catch(e => { if (e.name !== 'AbortError') setError(e.message) }); return () => controller.abort() }, [])
  useEffect(() => {
    if (!card) { setLoading(false); return }
    if (card.available === false) { setError(card.error || '该批次外部数据缺失'); setLoading(false); return }
    if (cache.has(card.id)) { setBook(cache.get(card.id)!); setLoading(false); setError(''); return }
    const controller = new AbortController(); setLoading(true); setError('')
    readJson<MonteCarloWorkbook>('/api/monte-carlo/' + card.id, { signal: controller.signal }).then(b => { cache.set(b.id, b); setBook(b) })
      .catch(e => { if (e.name !== 'AbortError') setError(e.message) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [card?.id, card?.available])
  useEffect(() => { const saved = positions.current[positionKey]; if (saved && gridRef.current) { gridRef.current.scrollTop = saved.top; gridRef.current.scrollLeft = saved.left } }, [positionKey, book, methodId])
  useEffect(() => { process?.reset() }, [card?.id, n, delta])

  function navigate(values: Record<string, string | number | null>) {
    if (gridRef.current) positions.current[positionKey] = { top: gridRef.current.scrollTop, left: gridRef.current.scrollLeft }
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
  function openDetail(id: WorkbookCell) {
    if (process?.selectRun && numeric(id)) { process.selectRun(id); return }
    setDetailId(id); navigate({ sample: String(id) }); dialogRef.current?.showModal()
  }
  const resultRows = group && block ? group.resultRows.map(row => ({ id: row[0], values: row.slice(block.column, block.column + 3) })) : []
  const selectedSample = group?.samples.find(r => r[0] === detailId), selectedResults = group?.resultRows.find(r => r[0] === detailId)
  const currentBook = book?.id === card?.id ? book : null
  const noData = !loading && catalog.length > 0 && !card
  const processAvailable = !!(currentBook && card?.mdmProcess?.n === n && card.mdmProcess.delta === delta && methodId === 'mdm')

  return <div className={styles.workbook} data-process-picker={process ? true : undefined}>
    {card && <section aria-labelledby="workbook-settings-title" className={styles.settings}>
      <h2 id="workbook-settings-title" className={styles.settingsTitle}>{process ? '适用范围结果' : '参数设置'}</h2>
      <div className={styles.controls}>
      <div className={styles.parameters} aria-label="分布参数">
      {card.truth.length === 3 && ['形状 β', '尺度 η', '位置 γ'].map((label, i) => <div className={styles.control} key={label}><ChoiceSelect label={['β', 'η', 'γ'][i]} displayLabel={label} value={card.truth[i]} options={parameterOptions(i)} onChange={v => chooseParameter(i, v)} /></div>)}
      {methodId === 'mdm' && <div className={styles.control}><ChoiceSelect label="δ" displayLabel="偏移量 δ" value={delta} options={card.offsets.map(v => ({ value: v, label: v.toFixed(2) }))} onChange={v => navigate({ delta: v })} /></div>}
      </div>
      <div className={styles.sampleControl}><ChoiceSelect tone="sample" label="样本量" displayLabel="样本量 n" value={n} options={Array.from(new Set(cards.flatMap(c => c.ns))).sort((a, b) => a - b).map(value => ({ value, disabled: !card.ns.includes(value) }))} onChange={v => navigate({ n: v, sample: null })} /></div>
    </div>
      {process && <button type="button" className={styles.showProcess} disabled={!processAvailable || process.loading}
        onClick={() => process.show({ id: card.id, n, delta })}>
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
    <div id="workbook-content" role="tabpanel" aria-labelledby={`workbook-tab-${view}`} aria-busy={loading}>
      {loading ? <p className={styles.empty}>正在读取数据…</p> : noData ? <p className={styles.empty}>{requestedId ? '该批次未登记，请检查批次地址。' : '此方法暂无完整样本工作簿。'}</p> : currentBook && group && block ? <>
          {view === 'samples' && <div ref={gridRef} className={styles.grid} aria-label="完整样本数据表"><table><thead><tr>{currentBook.sheets.find(s => s.name === group.sampleSheet)?.rows[0].map((v, i) => <th key={i}>{String(v)}</th>)}</tr></thead><tbody>{group.samples.map((row, i) => <tr key={i} data-selected={selection === String(row[0])}><th><button onClick={() => openDetail(row[0])} aria-label={`查看样本${row[0]}对照`}>{String(row[0])}</button></th>{row.slice(1).map((v, j) => <td key={j} data-value={String(v)}>{fmt(v, currentBook.sheets.find(s => s.name === group.sampleSheet)?.formats[i + 1][j + 1])}</td>)}</tr>)}</tbody></table></div>}
          {view === 'results' && <div ref={gridRef} className={styles.grid} aria-label="逐次参数估计表"><table className={styles.estimates}><thead><tr><th rowSpan={2}>样本</th>{['形状 β', '尺度 η', '位置 γ'].map((label, j) => <th key={label} colSpan={2}>{label}<span className={styles.truth}>真值 {currentBook.truth?.[j] ?? '未标注'}</span></th>)}</tr><tr>{[0, 1, 2].flatMap(j => [<th key={`${j}-value`}>估计值</th>, <th key={`${j}-diff`} title="估计值减真值">差值</th>])}</tr></thead><tbody>{resultRows.map((row, i) => {
            const errors = currentBook.truth ? paramAbsoluteErrors(...row.values.map(v => numeric(v) ? v : NaN) as [number, number, number], ...currentBook.truth as [number, number, number]) : null
            const differences = errors ? [errors.beta, errors.eta, errors.gamma] : []
            return <tr key={i} data-selected={selection === String(row.id)}><th><button onClick={() => openDetail(row.id)} aria-label={`查看样本${row.id}对照`}>{String(row.id)}</button></th>{row.values.flatMap((v, j) => {
              const diff = differences[j], tone = diff > 0 ? styles.high : diff < 0 ? styles.low : styles.equal
              return [<td key={`${j}-value`} data-value={String(v)}>{fmt(v, currentBook.sheets.find(s => s.name === group.resultSheet)?.formats[i + 2][block.column + j])}</td>, <td key={`${j}-diff`} className={tone} data-difference={Number.isFinite(diff) ? diff : ''}>{Number.isFinite(diff) ? signed(diff) : '—'}</td>]
            })}</tr>
          })}</tbody></table></div>}
          <footer className={styles.sheetFooter}>
            <div className={styles.tabs} role="tablist" aria-label="数据视图">{views.map(v =>
              <button type="button" key={v.id} role="tab" id={`workbook-tab-${v.id}`} aria-selected={view === v.id} aria-controls="workbook-content" onClick={() => navigate({ view: v.id })}>{v.label}</button>)}</div>
            {!process && <div className={styles.footerMeta}>
              <span className={styles.filename}>{card?.filename}</span>
              <a className={styles.download} href={`/api/monte-carlo/${currentBook.id}/export`} download={currentBook.filename}
                aria-label={`下载 Excel，当前参数组合完整${currentBook.sheets.length}张表`} title={`下载 Excel（完整${currentBook.sheets.length}张表）`}><Download size={18} aria-hidden="true" /></a>
            </div>}
          </footer>
          {!process && <section className={styles.statisticsBelow} aria-label="统计"><h2>统计</h2><WorkbookStatistics rows={resultRows} truth={currentBook.truth} /></section>}
        </> : !error && <p className={styles.empty}>该工作簿没有当前方法的估计列。</p>}
    </div>
    <dialog ref={dialogRef} className={styles.dialog}><header><h2>样本 {String(detailId)} · n={n}</h2><button onClick={() => dialogRef.current?.close()} aria-label="关闭样本对照">×</button></header>
      <div className={styles.dialogBody}><div className={styles.observations}>{selectedSample?.slice(1).map((v, i) => <div key={i}><span>x₍{i + 1}₎</span>{String(v)}</div>)}</div>
        <div className={styles.detailTable}><table><thead><tr><th>方法</th><th>形状 β̂</th><th>尺度 η̂</th><th>位置 γ̂</th></tr></thead><tbody>{group?.blocks.map(b => <tr key={b.column}><th>{b.label}</th>{selectedResults?.slice(b.column, b.column + 3).map((v, i) => <td key={i}>{fmt(v)}</td>)}</tr>)}</tbody></table></div>
      </div></dialog>
  </div>
}

function WorkbookStatistics({ rows, truth }: { rows: { id: WorkbookCell; values: WorkbookCell[] }[]; truth: number[] | null }) {
  const valid = rows.filter(r => r.values.every(numeric))
  return <div className={styles.statistics}><p>完整估计 {valid.length} / {rows.length}</p><div className={styles.detailTable}><table><thead><tr>{['参数', '真值', '均值', 'Bias', 'SD', 'RMSE', 'MAE'].map(t => <th key={t}>{t}</th>)}</tr></thead><tbody>{['形状 β', '尺度 η', '位置 γ'].map((label, j) => {
    const target = truth?.[j], summary = summarizeStandardErrors(valid.map(r => Number(r.values[j]) - (target ?? 0)))
    return <tr key={label}><th>{label}</th>{[target, summary.bias === null ? null : summary.bias + (target ?? 0), target === undefined ? null : summary.bias, summary.sd, target === undefined ? null : summary.rmse, target === undefined ? null : summary.mae].map((v, i) => <td key={i}>{v === null || v === undefined ? '—' : fmt(v)}</td>)}</tr>
  })}</tbody></table></div>{truth && <div className={styles.distributions}>{['β', 'η', 'γ'].map((symbol, j) => <div key={symbol} className={styles.distribution} role="img" aria-label={`${symbol}估计差值分布，${valid.length}份完整估计`}><h3>{symbol} 估计差值分布</h3><Histogram values={valid.map(r => Number(r.values[j]) - truth[j])} xLabel={`${symbol}̂ − ${symbol}`} yLabel="频数" color="#b58a45" axisFontSize={14} /></div>)}</div>}</div>
}

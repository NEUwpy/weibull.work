'use client'

import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Download } from 'lucide-react'
import {
  formatWorkbookCell as fmt, type WorkbookBlock, type WorkbookCell, type WorkbookGroup,
  type WorkbookRun, type WorkbookView,
} from '@/lib/monte-carlo'
import { paramAbsoluteErrors, summarizeStandardErrors } from '@/lib/metrics'
import { Histogram } from '@/components/ai/charts/Histogram'
import styles from './Workbook.module.css'

const views = { samples: '样本数据', results: '估计结果' }
const parameters = [
  { id: 'beta', label: '形状 β', symbol: 'β' },
  { id: 'eta', label: '尺度 η', symbol: 'η' },
  { id: 'gamma', label: '位置 γ', symbol: 'γ' },
] as const
const runLabels = { success: '有效', failure: '失败', pending: '待估计' }
const signed = (v: number) => v === 0 ? '0.000000' : (v > 0 ? '+' : '−') + (Math.abs(v) < .0000005 ? Math.abs(v).toExponential(2) : Math.abs(v).toFixed(6))
const numeric = (v: WorkbookCell): v is number => typeof v === 'number' && Number.isFinite(v)

interface ResultRow {
  id: WorkbookCell
  values: WorkbookCell[]
  run?: WorkbookRun
}

interface Props {
  group: WorkbookGroup
  block: WorkbookBlock
  truth: number[] | null
  n: number
  view: WorkbookView
  onViewChange: (view: WorkbookView) => void
  selection?: string | null
  onSelect?: (id: WorkbookCell) => boolean | void
  sampleHeaders?: WorkbookCell[]
  sampleFormats?: string[][]
  resultFormats?: string[][]
  runs?: ReadonlyMap<WorkbookCell, WorkbookRun>
  download?: ReactNode
  showStatistics?: boolean
}

export function workbookDownload(filename: string, href: string | (() => void), label: string) {
  return <div className={styles.footerMeta}>
    <span className={styles.filename}>{filename}</span>
    {typeof href === 'string'
      ? <a className={styles.download} href={href} download={filename} aria-label={label} title={label}><Download size={18} aria-hidden="true" /></a>
      : <button type="button" className={styles.download} onClick={href} aria-label={label} title={label}><Download size={18} aria-hidden="true" /></button>}
  </div>
}

export default function WorkbookResults({
  group, block, truth, n, view, onViewChange, selection, onSelect, sampleHeaders,
  sampleFormats, resultFormats, runs, download, showStatistics = true,
}: Props) {
  const id = useId()
  const grid = useRef<HTMLDivElement>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const positions = useRef<Partial<Record<WorkbookView, { top: number; left: number }>>>({})
  const [detailId, setDetailId] = useState<WorkbookCell>(null)
  const [page, setPage] = useState(0)
  const samplePageSize = runs ? Math.max(1, Math.floor(12000 / n)) : group.samples.length || 1
  const pages = Math.ceil(group.samples.length / samplePageSize)
  const rows: ResultRow[] = group.resultRows.map(row => ({
    id: row[0], values: row.slice(block.column, block.column + 3), run: runs?.get(row[0]),
  }))
  const selectedSample = group.samples.find(row => row[0] === detailId)
  const selectedResults = group.resultRows.find(row => row[0] === detailId)
  const selectedRun = runs?.get(detailId)

  useEffect(() => {
    if (!grid.current) return
    const position = positions.current[view]
    grid.current.scrollTop = position?.top ?? 0
    grid.current.scrollLeft = position?.left ?? 0
  }, [view])

  function openDetail(rowId: WorkbookCell) {
    if (onSelect?.(rowId)) return
    setDetailId(rowId)
    dialog.current?.showModal()
  }

  function changeView(nextView: WorkbookView) {
    if (grid.current) positions.current[view] = { top: grid.current.scrollTop, left: grid.current.scrollLeft }
    onViewChange(nextView)
  }

  function changePage(nextPage: number) {
    setPage(nextPage)
    if (grid.current) grid.current.scrollTop = 0
  }

  function rowButton(rowId: WorkbookCell) {
    return <th><button type="button" onClick={() => openDetail(rowId)} aria-label={`查看样本${rowId}对照`}>{String(rowId)}</button></th>
  }

  return <div id={`${id}-content`} role="tabpanel" aria-labelledby={`${id}-${view}`}>
    {view === 'samples' ? (
      <div ref={grid} className={styles.grid} aria-label="完整样本数据表">
        <table><thead><tr>
          {(sampleHeaders ?? ['样本', ...Array.from({ length: n }, (_, index) => `x${index + 1}`)])
            .map((value, i) => {
              const label = String(value)
              const observation = /^x(\d+)$/.exec(label)
              return <th key={i}>{observation ? <>x<sub>{observation[1]}</sub></> : label}</th>
            })}
        </tr></thead><tbody>
          {group.samples.slice(page * samplePageSize, (page + 1) * samplePageSize).map((row, i) => (
            <tr key={String(row[0])} data-selected={selection === String(row[0])}>
              {rowButton(row[0])}
              {row.slice(1).map((v, j) => <td key={j} data-value={String(v)}>{fmt(v, sampleFormats?.[page * samplePageSize + i + 1]?.[j + 1])}</td>)}
            </tr>
          ))}
        </tbody></table>
      </div>
    ) : (
      <div ref={grid} className={styles.grid} aria-label="逐次参数估计表">
        <table className={styles.estimates}><thead>
          <tr><th rowSpan={2}>样本</th>{parameters.map(({ label }, j) => <th key={label} colSpan={2}>
            {label}<span className={styles.truth}>真值 {truth?.[j] ?? '未标注'}</span>
          </th>)}{runs && <th rowSpan={2}>状态</th>}</tr>
          <tr>{parameters.flatMap(({ id }) => [<th key={`${id}-value`}>估计值</th>, <th key={`${id}-diff`} title="估计值减真值">差值</th>])}</tr>
        </thead><tbody>
          {rows.map((row, i) => {
            const errors = truth && (!row.run || row.run.status === 'success')
              ? paramAbsoluteErrors(...row.values.map(v => numeric(v) ? v : NaN) as [number, number, number],
                ...truth as [number, number, number])
              : null
            return <tr key={String(row.id)} data-selected={selection === String(row.id)}>
              {rowButton(row.id)}
              {row.values.flatMap((v, j) => {
                const diff = errors?.[parameters[j].id]
                const tone = diff === undefined || diff === 0 ? styles.equal : diff > 0 ? styles.high : styles.low
                return [
                  <td key={`${j}-value`} data-value={String(v)}>{fmt(v, resultFormats?.[i + 2]?.[block.column + j]) || (runs ? '—' : '')}</td>,
                  <td key={`${j}-diff`} className={tone} data-difference={Number.isFinite(diff) ? diff : ''}>{diff !== undefined && Number.isFinite(diff) ? signed(diff) : '—'}</td>,
                ]
              })}
              {runs && <td data-run-status={row.run?.status} title={row.run?.error || undefined}>{row.run && runLabels[row.run.status]}</td>}
            </tr>
          })}
        </tbody></table>
      </div>
    )}
    <footer className={styles.sheetFooter}>
      <div className={styles.tabs} role="tablist" aria-label="数据视图">
        {(Object.keys(views) as WorkbookView[]).map(tab => (
          <button type="button" key={tab} role="tab" id={`${id}-${tab}`} aria-selected={view === tab} aria-controls={`${id}-content`}
            onClick={() => changeView(tab)}>{views[tab]}</button>
        ))}
      </div>
      {view === 'samples' && pages > 1 && <div className={styles.pageControls} aria-label="样本表分页">
        <button type="button" aria-label="样本表上一页" disabled={page === 0} onClick={() => changePage(page - 1)}>‹</button>
        <span>{page + 1} / {pages}</span>
        <button type="button" aria-label="样本表下一页" disabled={page + 1 >= pages} onClick={() => changePage(page + 1)}>›</button>
      </div>}
      {download}
    </footer>
    {showStatistics && <section className={styles.statisticsBelow} aria-label="统计">
      <h2>统计</h2>
      <WorkbookStatistics rows={rows} truth={truth} showStatus={!!runs} />
    </section>}
    <dialog ref={dialog} className={styles.dialog}>
        <header><h2>样本 {String(detailId)} · n={n}</h2><button type="button" onClick={() => dialog.current?.close()} aria-label="关闭样本对照">×</button></header>
        <div className={styles.dialogBody}>
          {selectedRun && <p className={styles.runDetail} data-run-status={selectedRun.status}>{runLabels[selectedRun.status]}{selectedRun.error && ` · ${selectedRun.error}`}</p>}
          <div className={styles.observations}>{selectedSample?.slice(1).map((v, i) => (
            <div key={i}><span>x<sub>{/^第\d+顺序统计量$/.test(String(sampleHeaders?.[i + 1])) ? `(${i + 1})` : i + 1}</sub></span>{String(v)}</div>
          ))}</div>
          <div className={styles.detailTable}><table><thead><tr><th>方法</th><th>形状 β̂</th><th>尺度 η̂</th><th>位置 γ̂</th></tr></thead><tbody>
            {group.blocks.map(b => <tr key={b.column}><th>{b.label}</th>
              {selectedResults?.slice(b.column, b.column + 3).map((v, i) => <td key={i}>{fmt(v) || '—'}</td>)}
            </tr>)}
          </tbody></table></div>
        </div>
    </dialog>
  </div>
}

function WorkbookStatistics({ rows, truth, showStatus }: {
  rows: ResultRow[]; truth: number[] | null; showStatus: boolean
}) {
  const valid = rows.filter(row => (!row.run || row.run.status === 'success') && row.values.every(numeric))
  const failures = rows.filter(row => row.run?.status === 'failure').length
  const pending = rows.filter(row => row.run?.status === 'pending').length
  return <div className={styles.statistics}>
    <p>{showStatus ? '有效估计' : '完整估计'} {valid.length} / {rows.length}
      {showStatus && ` · 失败 ${failures}`}{pending > 0 && ` · 待估计 ${pending}`}</p>
    <div className={styles.detailTable}><table>
      <thead><tr>{['参数', '真值', '均值', 'Bias', 'SD', 'RMSE', 'MAE'].map(label => <th key={label}>{label}</th>)}</tr></thead>
      <tbody>{parameters.map(({ id, label }, j) => {
        const target = truth?.[j]
        const summary = summarizeStandardErrors(valid.map(row => Number(row.values[j]) - (target ?? 0)))
        const mean = summary?.bias == null ? null : summary.bias + (target ?? 0)
        const values = [target, mean, target === undefined ? null : summary?.bias, summary?.sd,
          target === undefined ? null : summary?.rmse, target === undefined ? null : summary?.mae]
        return <tr key={id}><th>{label}</th>{values.map((value, i) => <td key={i}>{value == null ? '—' : fmt(value)}</td>)}</tr>
      })}</tbody>
    </table></div>
    {truth && valid.length > 0 && <div className={styles.distributions}>{parameters.map(({ id, symbol }, j) => (
      <div key={id} className={styles.distribution} role="img" aria-label={`${symbol}估计差值分布，${valid.length}份估计`}>
        <h3>{symbol} 估计差值分布</h3>
        <Histogram values={valid.map(row => Number(row.values[j]) - truth[j])} xLabel={`${symbol}̂ − ${symbol}`} yLabel="频数" color="#b58a45" axisFontSize={14} />
      </div>
    ))}</div>}
  </div>
}

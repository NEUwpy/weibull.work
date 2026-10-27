"use client"

import React, { useEffect, useRef, useState } from 'react'
import { Loader2, Play, Square } from 'lucide-react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { DensityChart } from '@/components/shared/charts/DensityChart'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import { requestSimulation, simulationRange, type AnalysisMode, type SimulationBatch, type AnalysisParameter } from '@/lib/simulation-analysis'

interface Props { methodId: string; trueBeta: number; trueEta: number; trueGamma: number }
const parameters: { id: AnalysisParameter; label: string; color: string; hex: string }[] = [
  { id: 'beta', label: 'β', color: 'blue', hex: '#3b82f6' },
  { id: 'eta', label: 'η', color: 'indigo', hex: '#6366f1' },
  { id: 'gamma', label: 'γ', color: 'purple', hex: '#a855f7' },
]
const format = (v: number | undefined) => v !== undefined && Number.isFinite(v) ? v.toFixed(4) : '—'

export default function ResultAnalysisLab({ methodId, trueBeta, trueEta, trueGamma }: Props) {
  const [mode, setMode] = useState<AnalysisMode>('single')
  const [settings, setSettings] = useState({ n: 50, nMin: 10, nMax: 100, nStep: 10, dMin: 0, dMax: 0.5, dStep: 0.02, rep: 100 })
  const [batches, setBatches] = useState<SimulationBatch[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const request = useRef<AbortController | null>(null)
  const identity = JSON.stringify([methodId, trueBeta, trueEta, trueGamma])
  const [resultIdentity, setResultIdentity] = useState(identity)
  const mdm = methodId.toLowerCase() === 'mdm'

  useEffect(() => {
    if (!mdm) setMode(previous => previous === 'offset' ? 'single' : previous)
  }, [mdm])

  useEffect(() => {
    request.current?.abort()
    setRunning(false)
    setBatches([])
    setError('')
    setProgress({ done: 0, total: 0 })
    return () => request.current?.abort()
  }, [identity])

  const clearResults = () => {
    setBatches([]); setError(''); setSelectedIndex(0); setProgress({ done: 0, total: 0 })
  }
  const run = async () => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    clearResults()
    setRunning(true)
    setResultIdentity(identity)
    try {
      const sizes = mode === 'range' ? simulationRange(settings.nMin, settings.nMax, settings.nStep, 50) : [settings.n]
      const offsets = mode === 'offset' && mdm ? simulationRange(settings.dMin, settings.dMax, settings.dStep, 50) : [undefined]
      if (sizes.some(n => !Number.isInteger(n) || n < 3 || n > 500) ||
          !Number.isInteger(settings.rep) || settings.rep < 1 || settings.rep > 1000 ||
          offsets.some(d => d !== undefined && (d < 0 || d > 0.5))) {
        throw new Error('样本量须为 3–500 的整数，重复次数为 1–1000 的整数，偏移量为 0–0.5')
      }
      const cells = sizes.flatMap(n => offsets.map(offset => ({ n, offset })))
      if (cells.length * settings.rep > 10000) throw new Error('本轮最多执行 10000 次估计，请减少组合或重复次数')
      setProgress({ done: 0, total: cells.length })
      const complete: SimulationBatch[] = []
      for (const cell of cells) {
        const batch = await requestSimulation({
          methodId, beta: trueBeta, eta: trueEta, gamma: trueGamma,
          n: cell.n, rep: settings.rep, seed: 42, offset: cell.offset,
        }, controller.signal)
        if (controller.signal.aborted) return
        complete.push(batch)
        setBatches([...complete])
        setProgress({ done: complete.length, total: cells.length })
      }
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '模拟失败')
    } finally {
      if (request.current === controller) setRunning(false)
    }
  }
  const stop = () => {
    request.current?.abort()
    setRunning(false)
    setError('已停止；下方仅显示已完成的组合，未完成部分不计入结果。')
  }
  const visible = resultIdentity === identity ? batches : []
  const selected = visible[Math.min(selectedIndex, Math.max(visible.length - 1, 0))]
  const validRows = (selected?.rows ?? []).filter(row => row.status === 'success').map(row => ({
    est_beta: row.est_beta, est_eta: row.est_eta, est_gamma: row.est_gamma, sample_size: row.sample_size,
  }))
  const truth = { beta: trueBeta, eta: trueEta, gamma: trueGamma }
  const xLabel = mode === 'offset' ? '偏移量 δ' : '样本量 n'
  const numberInput = (key: keyof typeof settings, label: string, min: number, max: number, step = 1) => (
    <label className="grid gap-1">{label}<input aria-label={label} type="number" min={min} max={max} step={step}
      value={settings[key]} onChange={e => setSettings(previous => ({ ...previous, [key]: Number(e.target.value) }))}
      className="w-24 rounded border border-slate-300 bg-white px-2 py-1" /></label>
  )

  return <section className="space-y-5" aria-label="结果分析实验">
    <div>
      <h3 className="text-lg font-bold text-slate-800">{methodId.toUpperCase()} 结果分析</h3>
      <p className="mt-1 text-sm text-slate-500">以当前参数 β={format(trueBeta)}、η={format(trueEta)}、γ={format(trueGamma)} 生成模拟样本，评估该设定下的估计误差；不代表当前样本的真实误差。</p>
    </div>
    <fieldset disabled={running} onChange={clearResults} className="flex flex-wrap items-end gap-4 text-sm disabled:opacity-60">
      <label className="grid gap-1">分析方式<select aria-label="分析方式" value={mode} onChange={e => setMode(e.target.value as AnalysisMode)} className="rounded border border-slate-300 p-1.5">
        <option value="single">单一样本量</option><option value="range">样本量范围</option>{mdm && <option value="offset">偏移量对比</option>}
      </select></label>
      {mode === 'range' ? <>
        {numberInput('nMin', '最小样本量', 3, 500)}{numberInput('nMax', '最大样本量', 3, 500)}{numberInput('nStep', '样本量步长', 1, 500)}
      </> : numberInput('n', '样本量', 3, 500)}
      {mode === 'offset' && <>{numberInput('dMin', '最小偏移量', 0, 0.5, 0.02)}{numberInput('dMax', '最大偏移量', 0, 0.5, 0.02)}{numberInput('dStep', '偏移量步长', 0.001, 0.5, 0.01)}</>}
      {numberInput('rep', '每组合重复次数', 1, 1000)}
    </fieldset>
    <div className="flex items-center gap-4">
      <button onClick={running ? stop : run} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">
        {running ? <Square size={16} /> : <Play size={16} />}{running ? '停止' : '开始模拟'}
      </button>
      <span role="status" className="flex items-center gap-2 text-sm text-slate-500">{running && <Loader2 size={16} className="animate-spin" />}{progress.total > 0 && '已完成 ' + progress.done + '/' + progress.total + ' 个组合'}</span>
    </div>
    {error && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{error}</p>}
    {visible.length > 0 && <>
      <p className="text-sm text-slate-500">Bias、SD、RMSE、MAE 均使用有效估计的原始尺度；失败记录保留并单列计数。各参数分别展示，不混合不同量纲的误差。</p>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-right text-sm"><thead className="bg-slate-100 text-slate-600"><tr>
          {['n', 'δ', '参数', '有效 / 总数', '失败', 'Bias', 'SD', 'RMSE', 'MAE'].map(label => <th key={label} className="px-3 py-2">{label}</th>)}
        </tr></thead><tbody>{visible.flatMap((batch, i) => parameters.map(parameter => {
          const metrics = batch.metrics.param_standard?.[parameter.id]?.absolute
          return <tr key={i + '-' + parameter.id} className="border-t border-slate-100">
            <td className="px-3 py-2">{batch.sampleSize}</td><td className="px-3 py-2">{mdm ? format(batch.offset ?? 0.1) : '—'}</td><td className="px-3 py-2">{parameter.label}</td>
            <td className="px-3 py-2">{batch.metrics.n_valid} / {batch.metrics.n_total}</td><td className="px-3 py-2">{batch.metrics.n_failure}</td>
            {(['bias', 'sd', 'rmse', 'mae'] as const).map(metric => <td key={metric} className="px-3 py-2">{format(metrics?.[metric])}</td>)}
          </tr>
        }))}</tbody></table>
      </div>
      {visible.length > 1 && <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">{parameters.map(parameter =>
        <ChartCard key={parameter.id} title={parameter.label + ' RMSE 随' + xLabel + '变化'}>
          <AIChartLine data={visible.flatMap(batch => {
            const y = batch.metrics.param_standard?.[parameter.id]?.absolute.rmse
            return y === undefined ? [] : [{ x: mode === 'offset' ? batch.offset! : batch.sampleSize, y }]
          })} xLabel={xLabel} yLabel={parameter.label + ' RMSE'} color={parameter.hex}
            xTickFormatter={value => Number(value.toPrecision(4)).toString()}
            yTickFormatter={value => Number(value.toPrecision(4)).toString()} showDots />
        </ChartCard>)}</div>}
      <label className="flex items-center gap-3 text-sm font-medium">查看估计分布
        <select aria-label="查看估计分布" value={Math.min(selectedIndex, visible.length - 1)} onChange={e => setSelectedIndex(Number(e.target.value))} className="rounded border border-slate-300 p-2">
          {visible.map((batch, i) => <option key={i} value={i}>{'n=' + batch.sampleSize + (mdm ? '，δ=' + format(batch.offset ?? 0.1) : '')}</option>)}
        </select>
      </label>
      {validRows.length === 0 ? <p className="text-sm text-amber-800">该组合没有有效估计，图表及误差指标为空。</p> :
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">{parameters.map(parameter => <ChartCard key={parameter.id} title={parameter.label + ' 有效估计分布'}>
          <DensityChart rawData={validRows} paramId={parameter.id} displayDimension={{ id: 'sampleSize', name: '样本量', symbol: 'n' }} trueValue={truth[parameter.id]} color={parameter.color} />
        </ChartCard>)}</div>}
    </>}
  </section>
}

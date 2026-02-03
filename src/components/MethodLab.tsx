"use client"

import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Microscope, PlayCircle, AlertCircle } from 'lucide-react'
import MLEVisualizer from '@/components/visualizers/MLEVisualizer'
import WMLEVisualizer from '@/components/visualizers/WMLEVisualizer'
import MDMVisualizer from '@/components/visualizers/MDMVisualizer'
import { WeibullResult, calculateMedianRanks } from '@/lib/weibull'

interface MethodLabProps {
  methodId: string
  onCalculationComplete?: (result: WeibullResult) => void
}

export default function MethodLab({ methodId, onCalculationComplete }: MethodLabProps) {
  const searchParams = useSearchParams()
  const [data, setData] = useState<number[]>([])
  const [traceResult, setTraceResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 1. Parse data from URL
  useEffect(() => {
    const dataParam = searchParams.get('data')
    if (dataParam) {
      try {
        // Assume comma separated values for simplicity
        // e.g. ?data=100,120,150
        const parsedData = dataParam.split(',').map(Number).filter(n => !isNaN(n))
        if (parsedData.length > 0) {
          setData(parsedData)
        }
      } catch (e) {
        console.error("Failed to parse data from URL", e)
      }
    }
  }, [searchParams])

  // 2. Auto-run calculation when data is present
  useEffect(() => {
    if (data.length < 2) return

    async function runLab() {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch('http://localhost:8001/calculate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            method: methodId,
            data: data,
            trace: true // Request process trace
          })
        })

        if (!response.ok) {
          throw new Error('Calculation failed')
        }

        const result = await response.json()
        setTraceResult(result)

        if (onCalculationComplete) {
           // Reconstruct DataPoints to calculate ranks for the chart
           const dataPoints = data.map((v, i) => ({ id: i, value: v, status: 'F' as const }))
           const points = calculateMedianRanks(dataPoints, result.gamma)
           
           onCalculationComplete({
             beta: result.beta,
             eta: result.eta,
             gamma: result.gamma,
             rSquared: result.rSquared,
             points: points
           })
        }
      } catch (err: any) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    runLab()
  }, [data, methodId])

  // If no data, show nothing (or empty state)
  if (data.length === 0) return null

  return (
    <div className="mt-8">
      <div className="bg-slate-50 rounded-3xl p-8 border border-slate-200">
        {loading && (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400">
            <PlayCircle size={48} className="mb-4 animate-pulse text-indigo-400" />
            <p>正在后端运行逐得迭代计算...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 text-red-600 p-4 rounded-xl flex items-center gap-2">
            <AlertCircle size={18} />
            计算出错: {error}
          </div>
        )}

        {traceResult && (
          <div className="space-y-8">
            {/* Stats Bar */}
            <div className="grid grid-cols-4 gap-4">
               <StatBox label="估计 β" value={traceResult.beta.toFixed(4)} />
               <StatBox label="估计 η" value={traceResult.eta.toFixed(2)} />
               <StatBox label="估计 γ" value={traceResult.gamma.toFixed(2)} />
               <StatBox label="R²" value={traceResult.rSquared.toFixed(4)} />
            </div>

            {/* Visualizers */}
            {methodId.toLowerCase() === 'mle' && (
              <MLEVisualizer traceData={traceResult.trace_data} />
            )}
            {methodId.toLowerCase() === 'wmle' && (
              <WMLEVisualizer traceData={traceResult.trace_data} />
            )}
            {methodId.toLowerCase() === 'mdm' && (
              <MDMVisualizer traceData={traceResult.trace_data} />
            )}
            
            {/* Fallback for others */}
            {!['mle', 'wmle', 'mdm'].includes(methodId.toLowerCase()) && (
              <div className="text-center py-12 text-slate-400">
                此算法暂未适配可视化组件。
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function StatBox({ label, value }: { label: string, value: string }) {
  return (
    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
      <div className="text-xs font-bold text-slate-400">{label}</div>
      <div className="text-lg font-black text-slate-800 mt-1">{value}</div>
    </div>
  )
}

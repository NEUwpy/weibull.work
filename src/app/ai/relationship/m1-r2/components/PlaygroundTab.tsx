/**
 * M1-R2 在线使用 Tab
 *
 * 路线 2：样本 → δ₀=0.5 → MDM → M1-R2 → δ₁ → ... → 收敛
 */
"use client"

import React, { useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { getApiBaseUrl, API_ENDPOINTS } from '@/lib/config'
import { Loader2, AlertCircle, CheckCircle2, RotateCcw } from 'lucide-react'

interface IterateStep {
  step: number
  delta: number
  beta?: number
  eta?: number
  gamma?: number
  mdm_status: string
}

interface Route2Result {
  final_delta: number
  final_params: { beta: number; eta: number; gamma: number } | null
  iterations: IterateStep[]
  converged: boolean
  convergence_reason: string
}

export function PlaygroundTab() {
  const [sampleInput, setSampleInput] = useState('')
  const [result, setResult] = useState<Route2Result | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const parseInput = useCallback(() => {
    const values = sampleInput
      .split(/[\n,\s]+/)
      .map(s => s.trim())
      .filter(s => s.length > 0)
      .map(Number)

    if (values.some(isNaN)) {
      setError('输入包含非数值，请检查')
      return null
    }
    if (values.length < 3) {
      setError('样本量至少为 3')
      return null
    }
    return values
  }, [sampleInput])

  const handlePredict = useCallback(async () => {
    setError('')
    setResult(null)

    const values = parseInput()
    if (!values) return

    setLoading(true)
    try {
      const baseUrl = getApiBaseUrl()
      const res = await fetch(`${baseUrl}${API_ENDPOINTS.aiPredictDeltaIterate}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: values }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '请求失败' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }, [parseInput])

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">
        M1-R2 迭代逼近：从 δ₀=0.5 开始，MDM 估计参数，网络预测新 δ，迭代直到收敛。
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 输入区 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-slate-800">输入样本数据</h3>
          <p className="text-xs text-slate-400">
            输入排序后的失效时间，每行一个或用逗号/空格分隔。
          </p>
          <textarea
            value={sampleInput}
            onChange={(e) => setSampleInput(e.target.value)}
            placeholder={"例如 (n=5):\n398.3\n520.3\n814.4\n921.3\n2344.0"}
            className="w-full h-40 p-3 border border-slate-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handlePredict}
            disabled={loading}
            className={cn(
              "w-full py-2.5 rounded-lg text-sm font-bold text-white transition-all",
              loading
                ? "bg-blue-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 active:bg-blue-800"
            )}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                迭代逼近中...
              </span>
            ) : (
              '迭代逼近预测 δ'
            )}
          </button>
        </div>

        {/* 输出区 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-slate-800">预测结果</h3>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {result && (
            <div className="space-y-3">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="text-xs text-blue-500 mb-1">迭代逼近的最终偏移量</div>
                <div className="text-3xl font-black text-blue-700 font-mono">
                  δ = {result.final_delta}
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <span className={cn(
                    "px-2 py-0.5 rounded text-xs font-bold",
                    result.converged ? "text-green-600 bg-green-50" : "text-yellow-600 bg-yellow-50"
                  )}>
                    {result.converged ? '已收敛' : '未收敛'}
                  </span>
                  <span className="text-xs text-blue-500">{result.convergence_reason}</span>
                </div>
              </div>

              {/* 最终参数 */}
              {result.final_params && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                    <div className="text-xs text-slate-400 mb-1">β̂</div>
                    <div className="text-sm font-bold text-slate-700 font-mono">{result.final_params.beta}</div>
                  </div>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                    <div className="text-xs text-slate-400 mb-1">η̂</div>
                    <div className="text-sm font-bold text-slate-700 font-mono">{result.final_params.eta}</div>
                  </div>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                    <div className="text-xs text-slate-400 mb-1">γ̂</div>
                    <div className="text-sm font-bold text-slate-700 font-mono">{result.final_params.gamma}</div>
                  </div>
                </div>
              )}

              {/* 迭代历史 */}
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                <h4 className="text-xs font-bold text-slate-600 mb-2">迭代历史</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-100">
                        <th className="border border-slate-200 px-2 py-1 text-left font-bold text-slate-500">步骤</th>
                        <th className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500">δ</th>
                        <th className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500">β̂</th>
                        <th className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500">η̂</th>
                        <th className="border border-slate-200 px-2 py-1 text-right font-bold text-slate-500">γ̂</th>
                        <th className="border border-slate-200 px-2 py-1 text-center font-bold text-slate-500">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.iterations.map((step, i) => (
                        <tr key={i}>
                          <td className="border border-slate-200 px-2 py-1 font-mono">{step.step}</td>
                          <td className="border border-slate-200 px-2 py-1 text-right font-mono">{step.delta}</td>
                          <td className="border border-slate-200 px-2 py-1 text-right font-mono">{step.beta ?? '—'}</td>
                          <td className="border border-slate-200 px-2 py-1 text-right font-mono">{step.eta ?? '—'}</td>
                          <td className="border border-slate-200 px-2 py-1 text-right font-mono">{step.gamma ?? '—'}</td>
                          <td className={cn(
                            "border border-slate-200 px-2 py-1 text-center font-mono",
                            step.mdm_status === 'ok' ? 'text-green-600' :
                            step.mdm_status === 'converged' ? 'text-blue-600' : 'text-red-600'
                          )}>
                            {step.mdm_status}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {!result && !error && (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
              <RotateCcw size={32} className="mx-auto text-slate-300 mb-3" />
              <p className="text-sm text-slate-400">
                输入样本数据后点击&quot;迭代逼近预测 δ&quot;
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

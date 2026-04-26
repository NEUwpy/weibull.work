/**
 * 在线使用 Tab — 路线 1 + 路线 2
 *
 * 路线 1：样本 → N₂ → δ（直接预测）
 * 路线 2：样本 → δ₀=0.5 → MDM → N₁ → δ₁ → ... → 收敛（迭代逼近）
 */
"use client"

import React, { useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { getApiBaseUrl, API_ENDPOINTS } from '@/lib/config'
import { Loader2, AlertCircle, CheckCircle2, GitBranch, RotateCcw } from 'lucide-react'

// 路线 1 结果
interface Route1Result {
  optimal_delta: number
  model_n: number
  confidence: string
}

// 路线 2 结果
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

const confidenceMap: Record<string, { label: string; color: string }> = {
  high: { label: '高', color: 'text-green-600 bg-green-50' },
  medium: { label: '中', color: 'text-yellow-600 bg-yellow-50' },
  low: { label: '低', color: 'text-red-600 bg-red-50' },
}

export function PlaygroundTab() {
  const [sampleInput, setSampleInput] = useState('')
  const [route, setRoute] = useState<1 | 2>(1)
  const [result1, setResult1] = useState<Route1Result | null>(null)
  const [result2, setResult2] = useState<Route2Result | null>(null)
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

  const handlePredictRoute1 = useCallback(async () => {
    setError('')
    setResult1(null)
    setResult2(null)

    const values = parseInput()
    if (!values) return

    setLoading(true)
    try {
      const baseUrl = getApiBaseUrl()
      const res = await fetch(`${baseUrl}${API_ENDPOINTS.aiPredictDelta}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: values }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '请求失败' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setResult1(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }, [parseInput])

  const handlePredictRoute2 = useCallback(async () => {
    setError('')
    setResult1(null)
    setResult2(null)

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
      setResult2(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }, [parseInput])

  return (
    <div className="space-y-6">
      {/* 路线切换 */}
      <div className="flex gap-2">
        <button
          onClick={() => setRoute(1)}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
            route === 1
              ? "bg-purple-600 text-white"
              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
          )}
        >
          <GitBranch size={14} />
          路线 1：直接学习
        </button>
        <button
          onClick={() => setRoute(2)}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all",
            route === 2
              ? "bg-blue-600 text-white"
              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
          )}
        >
          <RotateCcw size={14} />
          路线 2：迭代逼近
        </button>
      </div>

      {/* 路线说明 */}
      <div className={cn(
        "rounded-lg p-3 text-sm",
        route === 1 ? "bg-purple-50 border border-purple-200 text-purple-700" : "bg-blue-50 border border-blue-200 text-blue-700"
      )}>
        {route === 1
          ? "路线 1：神经网络 N₂ 直接从样本预测最优 δ，一步到位。"
          : "路线 2：从 δ₀=0.5 开始，用 MDM 估计参数，再用 N₁ 预测新 δ，迭代直到收敛（|δ_new-δ_old|<0.001 或最大 10 步）。"
        }
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 输入区 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-slate-800">输入样本数据</h3>
          <p className="text-xs text-slate-400">
            输入排序后的失效时间，每行一个或用逗号/空格分隔。当前支持 n=5, 7, 15。
          </p>
          <textarea
            value={sampleInput}
            onChange={(e) => setSampleInput(e.target.value)}
            placeholder={"例如 (n=5):\n398.3\n520.3\n814.4\n921.3\n2344.0"}
            className="w-full h-40 p-3 border border-slate-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
          <button
            onClick={route === 1 ? handlePredictRoute1 : handlePredictRoute2}
            disabled={loading}
            className={cn(
              "w-full py-2.5 rounded-lg text-sm font-bold text-white transition-all",
              loading
                ? "bg-purple-400 cursor-not-allowed"
                : route === 1
                  ? "bg-purple-600 hover:bg-purple-700 active:bg-purple-800"
                  : "bg-blue-600 hover:bg-blue-700 active:bg-blue-800"
            )}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                {route === 1 ? 'AI 预测中...' : '迭代逼近中...'}
              </span>
            ) : (
              route === 1 ? 'AI 预测最优 δ' : '迭代逼近预测 δ'
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

          {/* 路线 1 结果 */}
          {result1 && route === 1 && (
            <div className="space-y-3">
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <div className="text-xs text-purple-500 mb-1">AI 预测的最优偏移量</div>
                <div className="text-3xl font-black text-purple-700 font-mono">
                  δ = {result1.optimal_delta}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-1">使用模型</div>
                  <div className="text-sm font-bold text-slate-700">n={result1.model_n}</div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-1">置信度</div>
                  <span className={cn("px-2 py-0.5 rounded text-xs font-bold", confidenceMap[result1.confidence]?.color)}>
                    {confidenceMap[result1.confidence]?.label || result1.confidence}
                  </span>
                </div>
              </div>
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
                <CheckCircle2 size={16} className="text-green-500 mt-0.5 shrink-0" />
                <p className="text-xs text-green-700">
                  将此 δ 值输入 MDM 方法的偏移量参数，即可运行参数估计。
                </p>
              </div>
            </div>
          )}

          {/* 路线 2 结果 */}
          {result2 && route === 2 && (
            <div className="space-y-3">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="text-xs text-blue-500 mb-1">迭代逼近的最终偏移量</div>
                <div className="text-3xl font-black text-blue-700 font-mono">
                  δ = {result2.final_delta}
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <span className={cn(
                    "px-2 py-0.5 rounded text-xs font-bold",
                    result2.converged ? "text-green-600 bg-green-50" : "text-yellow-600 bg-yellow-50"
                  )}>
                    {result2.converged ? '已收敛' : '未收敛'}
                  </span>
                  <span className="text-xs text-blue-500">{result2.convergence_reason}</span>
                </div>
              </div>

              {/* 最终参数 */}
              {result2.final_params && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                    <div className="text-xs text-slate-400 mb-1">β̂</div>
                    <div className="text-sm font-bold text-slate-700 font-mono">{result2.final_params.beta}</div>
                  </div>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                    <div className="text-xs text-slate-400 mb-1">η̂</div>
                    <div className="text-sm font-bold text-slate-700 font-mono">{result2.final_params.eta}</div>
                  </div>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                    <div className="text-xs text-slate-400 mb-1">γ̂</div>
                    <div className="text-sm font-bold text-slate-700 font-mono">{result2.final_params.gamma}</div>
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
                      {result2.iterations.map((step, i) => (
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

          {/* 无结果 */}
          {!result1 && !result2 && !error && (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
              <GitBranch size={32} className="mx-auto text-slate-300 mb-3" />
              <p className="text-sm text-slate-400">
                输入样本数据后点击"{route === 1 ? 'AI 预测最优 δ' : '迭代逼近预测 δ'}"
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * M1-R1 在线使用 Tab
 *
 * 路线 1：样本 → M1-R1 → δ（直接预测）
 */
"use client"

import React, { useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { getApiBaseUrl, API_ENDPOINTS } from '@/lib/config'
import { Loader2, AlertCircle, CheckCircle2, Zap } from 'lucide-react'

interface Route1Result {
  optimal_delta: number
  model_n: number
  confidence: string
}

const confidenceMap: Record<string, { label: string; color: string }> = {
  high: { label: '高', color: 'text-green-600 bg-green-50' },
  medium: { label: '中', color: 'text-yellow-600 bg-yellow-50' },
  low: { label: '低', color: 'text-red-600 bg-red-50' },
}

export function PlaygroundTab() {
  const [sampleInput, setSampleInput] = useState('')
  const [result, setResult] = useState<Route1Result | null>(null)
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
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-sm text-purple-700">
        M1-R1 直接学习：神经网络直接从样本预测最优 δ，一步到位。当前支持 n=5, 7, 10, 15, 20。
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 输入区 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-slate-800">输入样本数据</h3>
          <p className="text-xs text-slate-400">
            输入排序后的失效时间，每行一个或用逗号/空格分隔。当前支持 n=5, 7, 10, 15, 20。
          </p>
          <textarea
            value={sampleInput}
            onChange={(e) => setSampleInput(e.target.value)}
            placeholder={"例如 (n=5):\n398.3\n520.3\n814.4\n921.3\n2344.0"}
            className="w-full h-40 p-3 border border-slate-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
          <button
            onClick={handlePredict}
            disabled={loading}
            className={cn(
              "w-full py-2.5 rounded-lg text-sm font-bold text-white transition-all",
              loading
                ? "bg-purple-400 cursor-not-allowed"
                : "bg-purple-600 hover:bg-purple-700 active:bg-purple-800"
            )}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                AI 预测中...
              </span>
            ) : (
              'AI 预测最优 δ'
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
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <div className="text-xs text-purple-500 mb-1">AI 预测的最优偏移量</div>
                <div className="text-3xl font-black text-purple-700 font-mono">
                  δ = {result.optimal_delta}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-1">使用模型</div>
                  <div className="text-sm font-bold text-slate-700">n={result.model_n}</div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-1">置信度</div>
                  <span className={cn("px-2 py-0.5 rounded text-xs font-bold", confidenceMap[result.confidence]?.color)}>
                    {confidenceMap[result.confidence]?.label || result.confidence}
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

          {!result && !error && (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
              <Zap size={32} className="mx-auto text-slate-300 mb-3" />
              <p className="text-sm text-slate-400">
                输入样本数据后点击&quot;AI 预测最优 δ&quot;
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

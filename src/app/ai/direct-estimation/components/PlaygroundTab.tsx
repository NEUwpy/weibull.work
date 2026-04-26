/**
 * 在线使用 Tab — 直接估计
 *
 * 输入样本 → 输出 β, η, γ
 */
"use client"

import React, { useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { getApiBaseUrl, API_ENDPOINTS } from '@/lib/config'
import { Loader2, AlertCircle, CheckCircle2, Target } from 'lucide-react'

interface PredictionResult {
  beta: number
  eta: number
  gamma: number
  model_n: number
}

export function PlaygroundTab({ scheme: defaultScheme = 'a-1' }: { scheme?: string }) {
  const [sampleInput, setSampleInput] = useState('')
  const [scheme, setScheme] = useState(defaultScheme.replace('-', ''))
  const [result, setResult] = useState<PredictionResult | null>(null)
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
      const res = await fetch(`${baseUrl}${API_ENDPOINTS.aiDirectEstimation}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: values, scheme }),
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
      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3 text-sm text-cyan-700">
        输入一组排序后的失效时间样本，AI 直接输出 β（形状参数）、η（尺度参数）、γ（位置参数）。
        当前支持 n=5、7、10、15。
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 输入区 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-slate-800">输入样本数据</h3>
          <p className="text-xs text-slate-400">
            输入排序后的失效时间，每行一个或用逗号/空格分隔。
          </p>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">预处理方案</label>
            <select
              value={scheme}
              onChange={(e) => setScheme(e.target.value)}
              className="w-full p-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
            >
              <option value="a1">A-1 原始样本（按 n 独立模型）</option>
              <option value="a2">A-2 除以均值（按 n 独立模型）</option>
              <option value="a3">A-3 去位置（按 n 独立模型）</option>
              <option value="b1">B-1 填充+掩码（统一模型）</option>
              <option value="b2">B-2 除以均值+掩码（统一模型）</option>
              <option value="c1">C-1 基础统计量（4 特征）</option>
              <option value="c2">C-2 扩展统计量（7 特征）</option>
              <option value="c3">C-3 最大化统计量（11 特征）</option>
            </select>
          </div>
          <textarea
            value={sampleInput}
            onChange={(e) => setSampleInput(e.target.value)}
            placeholder={"例如 (n=5):\n234.5\n567.8\n890.1\n1234.5\n1567.8"}
            className="w-full h-40 p-3 border border-slate-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
          />
          <button
            onClick={handlePredict}
            disabled={loading}
            className={cn(
              "w-full py-2.5 rounded-lg text-sm font-bold text-white transition-all",
              loading
                ? "bg-cyan-400 cursor-not-allowed"
                : "bg-cyan-600 hover:bg-cyan-700 active:bg-cyan-800"
            )}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                AI 预测中...
              </span>
            ) : 'AI 直接估计参数'}
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
              <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
                <div className="text-xs text-cyan-500 mb-3">AI 预测的 Weibull 参数</div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <div className="text-xs text-cyan-400 mb-1">β（形状）</div>
                    <div className="text-2xl font-black text-cyan-700 font-mono">{result.beta}</div>
                  </div>
                  <div>
                    <div className="text-xs text-cyan-400 mb-1">η（尺度）</div>
                    <div className="text-2xl font-black text-cyan-700 font-mono">{result.eta}</div>
                  </div>
                  <div>
                    <div className="text-xs text-cyan-400 mb-1">γ（位置）</div>
                    <div className="text-2xl font-black text-cyan-700 font-mono">{result.gamma}</div>
                  </div>
                </div>
              </div>

              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-1">使用模型</div>
                <div className="text-sm font-bold text-slate-700">n={result.model_n}</div>
              </div>

              <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
                <CheckCircle2 size={16} className="text-green-500 mt-0.5 shrink-0" />
                <p className="text-xs text-green-700">
                  预测完成。可将结果与传统方法（MLE、MDM）进行对比。
                </p>
              </div>
            </div>
          )}

          {!result && !error && (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
              <Target size={32} className="mx-auto text-slate-300 mb-3" />
              <p className="text-sm text-slate-400">
                输入样本数据后点击"AI 直接估计参数"
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

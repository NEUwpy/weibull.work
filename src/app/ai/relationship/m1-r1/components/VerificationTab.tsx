/**
 * M1-R1 可信性验证 Tab
 *
 * 图表：V1(验证案例表), V3(边界测试)
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { ScatterPlot } from '@/components/ai/charts/ScatterPlot'
import { loadCSV } from '@/lib/ai-data'

interface VerificationRow {
  [key: string]: number | string
}

interface BoundaryRow {
  [key: string]: number | string
}

export function VerificationTab() {
  const [verificationData, setVerificationData] = useState<VerificationRow[]>([])
  const [boundaryData, setBoundaryData] = useState<BoundaryRow[]>([])
  const [loading, setLoading] = useState(true)

  const toNum = (v: number | string): number => typeof v === 'number' ? v : parseFloat(v) || 0

  useEffect(() => {
    async function load() {
      try {
        const [ver, bnd] = await Promise.all([
          loadCSV<VerificationRow>('/ai/data/verification_cases.csv').catch(() => []),
          loadCSV<BoundaryRow>('/ai/data/boundary_tests.csv').catch(() => []),
        ])
        setVerificationData(ver)
        setBoundaryData(bnd)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载验证数据中...</div>
  }

  const hasData = verificationData.length > 0 || boundaryData.length > 0

  if (!hasData) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p>验证数据未找到</p>
        <p className="text-xs mt-1">请先运行 generate_comparison_data.py</p>
      </div>
    )
  }

  // Compute summary stats
  const validCases = verificationData.filter(r => r.est_beta !== '' && r.est_beta !== undefined)
  const betaErrors = validCases.map(r => Math.abs(toNum(r.beta_error)))
  const etaErrors = validCases.map(r => Math.abs(toNum(r.eta_error)))
  const gammaErrors = validCases.map(r => Math.abs(toNum(r.gamma_error)))

  const avgBetaErr = betaErrors.length > 0 ? betaErrors.reduce((s, v) => s + v, 0) / betaErrors.length : 0
  const avgEtaErr = etaErrors.length > 0 ? etaErrors.reduce((s, v) => s + v, 0) / etaErrors.length : 0
  const avgGammaErr = gammaErrors.length > 0 ? gammaErrors.reduce((s, v) => s + v, 0) / gammaErrors.length : 0

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-green-700 mb-2">验证方法</h4>
        <ul className="text-xs text-green-600 space-y-1">
          <li>• 已知参数验证：用已知 (β,η,γ) 生成样本，检查 AI 预测的 δ 是否使 MDM 估计接近真值</li>
          <li>• 边界条件测试：极端 β/η/n 组合下的鲁棒性</li>
        </ul>
      </div>

      {/* 指标卡片 */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <div className="text-xs text-purple-500">验证案例数</div>
          <div className="text-lg font-black text-purple-700 font-mono">{verificationData.length}</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500">MDM 成功</div>
          <div className="text-lg font-black text-blue-700 font-mono">{validCases.length} / {verificationData.length}</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="text-xs text-green-500">平均 |β 误差|</div>
          <div className="text-lg font-black text-green-700 font-mono">{avgBetaErr.toFixed(4)}</div>
        </div>
      </div>

      {/* V1: 验证案例表 */}
      <ChartCard title="V1: 已知参数验证案例">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-100">
                <th className="border border-slate-200 px-2 py-1.5 text-left font-bold text-slate-600">β</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">η</th>
                <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">n</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">AI δ</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">est β</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">est η</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">est γ</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">β err</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">η err</th>
                <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">γ err</th>
              </tr>
            </thead>
            <tbody>
              {verificationData.map((r, i) => {
                const betaErr = toNum(r.beta_error)
                const etaErr = toNum(r.eta_error)
                const gammaErr = toNum(r.gamma_error)
                const errColor = (v: number) => Math.abs(v) < 0.5 ? 'text-green-600' : Math.abs(v) < 2 ? 'text-yellow-600' : 'text-red-600'

                return (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="border border-slate-200 px-2 py-1 font-mono">{r.beta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.eta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-center font-mono">{r.n}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.ai_delta).toFixed(4)}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.est_beta ? toNum(r.est_beta).toFixed(4) : '-'}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.est_eta ? toNum(r.est_eta).toFixed(2) : '-'}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.est_gamma ? toNum(r.est_gamma).toFixed(2) : '-'}</td>
                    <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${r.est_beta ? errColor(betaErr) : 'text-slate-400'}`}>
                      {r.est_beta ? betaErr.toFixed(4) : '-'}
                    </td>
                    <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${r.est_eta ? errColor(etaErr) : 'text-slate-400'}`}>
                      {r.est_eta ? etaErr.toFixed(2) : '-'}
                    </td>
                    <td className={`border border-slate-200 px-2 py-1 text-right font-mono ${r.est_gamma ? errColor(gammaErr) : 'text-slate-400'}`}>
                      {r.est_gamma ? gammaErr.toFixed(2) : '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </ChartCard>

      {/* V2: 验证案例散点图 — 真实 vs 估计 */}
      {validCases.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <ChartCard title="V2: 真实 β vs 估计 β">
            <ScatterPlot
              data={validCases.map(r => ({ x: toNum(r.beta), y: toNum(r.est_beta) }))}
              xLabel="真实 β"
              yLabel="估计 β"
              color="#8b5cf6"
              showDiagonal={true}
            />
          </ChartCard>
          <ChartCard title="V2: 真实 η vs 估计 η">
            <ScatterPlot
              data={validCases.map(r => ({ x: toNum(r.eta), y: toNum(r.est_eta) }))}
              xLabel="真实 η"
              yLabel="估计 η"
              color="#3b82f6"
              showDiagonal={true}
            />
          </ChartCard>
          <ChartCard title="V2: 真实 γ vs 估计 γ">
            <ScatterPlot
              data={validCases.map(r => ({ x: toNum(r.gamma), y: toNum(r.est_gamma) }))}
              xLabel="真实 γ"
              yLabel="估计 γ"
              color="#10b981"
              showDiagonal={true}
            />
          </ChartCard>
        </div>
      )}

      {/* V3: 边界测试 */}
      {boundaryData.length > 0 && (
        <ChartCard title="V3: 边界条件测试">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-2 py-1.5 text-left font-bold text-slate-600">场景</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">β</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">η</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">n</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">AI δ</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">est β</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">est η</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-slate-600">est γ</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-center font-bold text-slate-600">状态</th>
                </tr>
              </thead>
              <tbody>
                {boundaryData.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="border border-slate-200 px-2 py-1 font-mono">{r.label}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.beta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.eta}</td>
                    <td className="border border-slate-200 px-2 py-1 text-center font-mono">{r.n}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{toNum(r.ai_delta).toFixed(4)}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.est_beta ? toNum(r.est_beta).toFixed(4) : '-'}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.est_eta ? toNum(r.est_eta).toFixed(2) : '-'}</td>
                    <td className="border border-slate-200 px-2 py-1 text-right font-mono">{r.est_gamma ? toNum(r.est_gamma).toFixed(2) : '-'}</td>
                    <td className={`border border-slate-200 px-2 py-1 text-center font-mono ${
                      r.status === 'ok' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {r.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      )}
    </div>
  )
}

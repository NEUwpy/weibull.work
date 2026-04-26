/**
 * 训练算法可视化 Tab
 *
 * 图表：T1(损失收敛曲线), T2(学习率变化曲线)
 * 说明：网络结构、数据预处理、训练策略
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import { loadJSON, metricsPath } from '@/lib/ai-data'

interface MetricsData {
  model_type: string
  metrics: Record<string, number>
  history: {
    train_loss: number[]
    val_loss: number[]
    lr: number[]
  }
  config: Record<string, number>
  trained_at: string
}

const SAMPLE_SIZES = [5, 7, 15]

export function TrainingTab() {
  const [n2Metrics, setN2Metrics] = useState<Map<number, MetricsData>>(new Map())
  const [n1Metrics, setN1Metrics] = useState<MetricsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const map = new Map<number, MetricsData>()
        for (const n of SAMPLE_SIZES) {
          try {
            const data = await loadJSON<MetricsData>(metricsPath(n))
            map.set(n, data)
          } catch {}
        }
        setN2Metrics(map)

        try {
          const n1 = await loadJSON<MetricsData>('n1' as any)
          setN1Metrics(n1)
        } catch {}
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载训练指标中...</div>
  }

  return (
    <div className="space-y-6">
      {/* 网络结构说明 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* N₂ 架构 */}
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-purple-700 mb-2">N₂ 模型（路线 1：样本 → δ）</h4>
          <div className="text-xs font-mono text-purple-600 space-y-1">
            <p>Linear(n, 128) → ReLU → BatchNorm</p>
            <p>Linear(128, 64) → ReLU → BatchNorm</p>
            <p>Linear(64, 1) → Sigmoid</p>
          </div>
          <p className="text-xs text-purple-500 mt-2">按样本量 n 分别训练独立模型</p>
        </div>

        {/* N₁ 架构 */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-blue-700 mb-2">N₁ 模型（路线 2：真值 → δ）</h4>
          <div className="text-xs font-mono text-blue-600 space-y-1">
            <p>Linear(3, 32) → ReLU</p>
            <p>Linear(32, 16) → ReLU</p>
            <p>Linear(16, 1) → Sigmoid</p>
          </div>
          <p className="text-xs text-blue-500 mt-2">输入 (β,η,γ) 真值，训练一个公共模型</p>
        </div>
      </div>

      {/* 训练超参数 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-400">优化器</div>
          <div className="text-sm font-bold text-slate-700">Adam</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-400">初始学习率</div>
          <div className="text-sm font-bold text-slate-700">0.001</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-400">批次大小</div>
          <div className="text-sm font-bold text-slate-700">64</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-400">早停耐心</div>
          <div className="text-sm font-bold text-slate-700">30</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-400">学习率调度</div>
          <div className="text-sm font-bold text-slate-700">ReduceLROnPlateau</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-400">调度参数</div>
          <div className="text-sm font-bold text-slate-700">patience=10, factor=0.5</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-400">最大轮数</div>
          <div className="text-sm font-bold text-slate-700">300</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-xs text-slate-400">验证比例</div>
          <div className="text-sm font-bold text-slate-700">20%</div>
        </div>
      </div>

      {/* T1: 损失收敛曲线 */}
      {n2Metrics.size > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {SAMPLE_SIZES.filter(n => n2Metrics.has(n)).map(n => {
            const m = n2Metrics.get(n)!
            const trainData = m.history.train_loss.map((v, i) => ({ x: i + 1, y: v }))
            const valData = m.history.val_loss.map((v, i) => ({ x: i + 1, y: v }))

            return (
              <ChartCard key={n} title={`T1: n=${n} 损失收敛曲线`}>
                <AIChartLine
                  lines={[
                    { id: 'train', label: '训练损失', data: trainData, color: '#3b82f6' },
                    { id: 'val', label: '验证损失', data: valData, color: '#ef4444' },
                  ]}
                  xLabel="Epoch"
                  yLabel="MSE 损失"
                />
                <div className="flex justify-center gap-6 mt-2 text-xs text-slate-500">
                  <span>最佳 epoch: {m.metrics.best_epoch}</span>
                  <span>验证 MSE: {m.metrics.mse?.toFixed(6)}</span>
                  <span>MAE: {m.metrics.mae?.toFixed(6)}</span>
                </div>
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* T2: 学习率变化曲线 */}
      {n2Metrics.size > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {SAMPLE_SIZES.filter(n => n2Metrics.has(n)).map(n => {
            const m = n2Metrics.get(n)!
            const lrData = m.history.lr.map((v, i) => ({ x: i + 1, y: v }))

            return (
              <ChartCard key={n} title={`T2: n=${n} 学习率变化`}>
                <AIChartLine
                  data={lrData}
                  xLabel="Epoch"
                  yLabel="学习率"
                  color="#10b981"
                />
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 无数据提示 */}
      {n2Metrics.size === 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
          <p className="text-sm text-slate-400">训练指标未找到</p>
          <p className="text-xs text-slate-300 mt-1">请先运行 train_model.py 生成训练指标</p>
        </div>
      )}

      {/* 指标汇总 */}
      {n2Metrics.size > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-slate-700 mb-3">N₂ 模型验证指标汇总</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">模型</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MSE</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">RMSE</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">最佳 Epoch</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">训练样本</th>
                </tr>
              </thead>
              <tbody>
                {SAMPLE_SIZES.filter(n => n2Metrics.has(n)).map(n => {
                  const m = n2Metrics.get(n)!
                  return (
                    <tr key={n}>
                      <td className="border border-slate-200 px-3 py-2 font-mono font-bold">n={n}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.mse?.toFixed(6)}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.mae?.toFixed(6)}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.rmse?.toFixed(6)}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.best_epoch}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.train_samples}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

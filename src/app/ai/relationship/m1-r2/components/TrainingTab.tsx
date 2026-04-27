/**
 * M1-R2 训练算法可视化 Tab
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

export function TrainingTab() {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const data = await loadJSON<MetricsData>(metricsPath('n1'))
        setMetrics(data)
      } catch {} finally {
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
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 模型架构（公共模型）</h4>
        <div className="text-xs font-mono text-blue-600 space-y-1">
          <p>Linear(3, 32) → ReLU</p>
          <p>Linear(32, 16) → ReLU</p>
          <p>Linear(16, 1) → Sigmoid</p>
        </div>
        <p className="text-xs text-blue-500 mt-2">
          输入：(β, η, γ) 参数估计值。输出：最优 δ。
          用 β∈&#123;1,2,5&#125; 的数据训练一个公共模型。
        </p>
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
      </div>

      {/* 损失曲线 */}
      {metrics ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ChartCard title="T1: M1-R2 损失收敛曲线">
            <AIChartLine
              lines={[
                { id: 'train', label: '训练损失', data: metrics.history.train_loss.map((v, i) => ({ x: i + 1, y: v })), color: '#3b82f6' },
                { id: 'val', label: '验证损失', data: metrics.history.val_loss.map((v, i) => ({ x: i + 1, y: v })), color: '#ef4444' },
              ]}
              xLabel="Epoch"
              yLabel="MSE 损失"
            />
            <div className="flex justify-center gap-6 mt-2 text-xs text-slate-500">
              <span>最佳 epoch: {metrics.metrics.best_epoch}</span>
              <span>验证 MSE: {metrics.metrics.mse?.toFixed(6)}</span>
            </div>
          </ChartCard>
          <ChartCard title="T2: M1-R2 学习率变化">
            <AIChartLine
              data={metrics.history.lr.map((v, i) => ({ x: i + 1, y: v }))}
              xLabel="Epoch"
              yLabel="学习率"
              color="#10b981"
            />
          </ChartCard>
        </div>
      ) : (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
          <p className="text-sm text-slate-400">训练指标未找到</p>
          <p className="text-xs text-slate-300 mt-1">请先运行 train_model.py 生成训练指标</p>
        </div>
      )}

      {/* 指标汇总 */}
      {metrics && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-slate-700 mb-3">M1-R2 模型验证指标</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">模型</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MSE</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">RMSE</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">最佳 Epoch</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="border border-slate-200 px-3 py-2 font-mono font-bold">M1-R2</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{metrics.metrics.mse?.toFixed(6)}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{metrics.metrics.mae?.toFixed(6)}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{metrics.metrics.rmse?.toFixed(6)}</td>
                  <td className="border border-slate-200 px-3 py-2 text-right font-mono">{metrics.metrics.best_epoch}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 迭代算法说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">迭代算法</h4>
        <div className="text-xs text-blue-600 space-y-1">
          <p>1. 初始 δ₀ = 0.5</p>
          <p>2. MDM(δₖ) → (β̂, η̂, γ̂)</p>
          <p>3. M1-R2(β̂, η̂, γ̂) → δₖ₊₁</p>
          <p>4. 若 |δₖ₊₁ - δₖ| &lt; 0.001 → 收敛</p>
          <p>5. 否则重复，最多 10 步</p>
        </div>
      </div>
    </div>
  )
}

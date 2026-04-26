/**
 * 训练算法可视化 Tab — 直接估计
 *
 * 图表：Loss 曲线（train/val）、学习率变化
 * 说明：网络结构、超参数
 */
"use client"

import React, { useEffect, useState } from 'react'
import { ChartCard } from '@/components/shared/charts/ChartCard'
import { AIChartLine } from '@/components/ai/charts/LineChart'
import { loadJSON, schemeMetricsPath, DirectEstimationMetricsData } from '@/lib/ai-data'

const SAMPLE_SIZES = [5, 7, 10, 15]

const SCHEME_NAMES: Record<string, string> = {
  'a-1': 'A-1 原始样本',
  'a-2': 'A-2 除以均值',
  'a-3': 'A-3 去位置',
  'b-1': 'B-1 填充+掩码',
  'b-2': 'B-2 除以均值+掩码',
  'c-1': 'C-1 基础统计量',
  'c-2': 'C-2 扩展统计量',
  'c-3': 'C-3 最大化统计量',
}

export function TrainingTab({ scheme = 'a-1' }: { scheme?: string }) {
  const [metrics, setMetrics] = useState<Map<number, DirectEstimationMetricsData>>(new Map())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const map = new Map<number, DirectEstimationMetricsData>()

        if (scheme === 'b-1') {
          // B-1 统一模型
          try {
            const data = await loadJSON<DirectEstimationMetricsData>(schemeMetricsPath('b-1'))
            // 为每个 n 创建条目（使用总体指标）
            for (const n of SAMPLE_SIZES) {
              map.set(n, data)
            }
          } catch {}
        } else {
          for (const n of SAMPLE_SIZES) {
            try {
              const data = await loadJSON<DirectEstimationMetricsData>(schemeMetricsPath(scheme, n))
              map.set(n, data)
            } catch {}
          }
        }

        setMetrics(map)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [scheme])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载训练指标中...</div>
  }

  return (
    <div className="space-y-6">
      {/* 网络结构说明 */}
      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-cyan-700 mb-2">网络架构 — {SCHEME_NAMES[scheme] || scheme}</h4>
        <div className="text-xs font-mono text-cyan-600 space-y-1">
          <p>Linear(input_dim, 128) → ReLU</p>
          <p>Linear(128, 64) → ReLU</p>
          <p>Linear(64, 32) → ReLU</p>
          <p>Linear(32, 3)  ← 线性输出，直接输出 β, η, γ</p>
        </div>
        <p className="text-xs text-cyan-500 mt-2">
          {scheme === 'b-1' ? '统一模型，覆盖所有 n（方案 B-1）' : `按样本量 n 分别训练独立模型（方案 ${scheme.toUpperCase()}）`}
        </p>
      </div>

      {/* 损失函数 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-2">损失函数：归一化 MSE</h4>
        <p className="text-xs font-mono text-slate-600">loss = MSE(pred_normalized, y_normalized)</p>
        <p className="text-xs text-slate-500 mt-1">输出 y 归一化为零均值单位方差，推理时反归一化</p>
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
          <div className="text-sm font-bold text-slate-700">32</div>
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

      {/* Loss 曲线 */}
      {metrics.size > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {SAMPLE_SIZES.filter(n => metrics.has(n)).map(n => {
            const m = metrics.get(n)!
            const trainData = m.history.train_loss.map((v, i) => ({ x: i + 1, y: v }))
            const valData = m.history.val_loss.map((v, i) => ({ x: i + 1, y: v }))

            return (
              <ChartCard key={n} title={`n=${n} 损失收敛曲线`}>
                <AIChartLine
                  lines={[
                    { id: 'train', label: '训练损失', data: trainData, color: '#3b82f6' },
                    { id: 'val', label: '验证损失', data: valData, color: '#ef4444' },
                  ]}
                  xLabel="Epoch"
                  yLabel="相对 MSE"
                />
                <div className="flex justify-center gap-6 mt-2 text-xs text-slate-500">
                  <span>最佳 epoch: {m.metrics.best_epoch}</span>
                  <span>验证 loss: {m.metrics.best_val_loss?.toFixed(6)}</span>
                </div>
              </ChartCard>
            )
          })}
        </div>
      )}

      {/* 学习率曲线 */}
      {metrics.size > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {SAMPLE_SIZES.filter(n => metrics.has(n)).map(n => {
            const m = metrics.get(n)!
            const lrData = m.history.lr.map((v, i) => ({ x: i + 1, y: v }))

            return (
              <ChartCard key={n} title={`n=${n} 学习率变化`}>
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
      {metrics.size === 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
          <p className="text-sm text-slate-400">训练指标未找到</p>
          <p className="text-xs text-slate-300 mt-1">请先运行 train_model.py 生成训练指标，并将结果复制到 public/ai/data/</p>
        </div>
      )}

      {/* 指标汇总 */}
      {metrics.size > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-slate-700 mb-3">验证指标汇总</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">模型</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(β)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(η)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">MAE(γ)</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">相对 MSE</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">最佳 Epoch</th>
                  <th className="border border-slate-200 px-3 py-2 text-right font-bold text-slate-600">训练样本</th>
                </tr>
              </thead>
              <tbody>
                {SAMPLE_SIZES.filter(n => metrics.has(n)).map(n => {
                  const m = metrics.get(n)!
                  return (
                    <tr key={n}>
                      <td className="border border-slate-200 px-3 py-2 font-mono font-bold">n={n}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.mae_beta?.toFixed(4)}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.mae_eta?.toFixed(2)}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.mae_gamma?.toFixed(2)}</td>
                      <td className="border border-slate-200 px-3 py-2 text-right font-mono">{m.metrics.total_relative_mse?.toFixed(6)}</td>
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

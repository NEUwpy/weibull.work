/**
 * 概率密度分布图组件 - 使用高斯核密度估计 (KDE)
 *
 * 显示：参数估计值的概率密度曲线
 * 用途：单变量分析时，展示各分组下参数估计的分布情况
 *
 * 设计：只输出图表，外框由 ChartCard 提供
 */
import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

// 参数配置类型
interface ParamConfig {
  id: string
  name: string
  symbol: string
}

// 原始数据行类型
interface RawDataRow {
  [key: string]: number | string | null
}

// 分组数据
interface GroupData {
  key: string
  label: string
  values: number[]
  color: string
}

interface DensityChartProps {
  rawData: RawDataRow[]
  paramId: 'beta' | 'eta' | 'gamma'  // 要显示的参数
  displayDimension: ParamConfig       // 分组维度
  trueValue: number                   // 真实值（用于参考线）
  color: string                       // 主色调
}

// 高斯核密度估计
function computeKDE(values: number[], bandwidth?: number, minX?: number) {
  const n = values.length
  if (n === 0) return { points: [], bandwidth: 0 }

  const mean = values.reduce((a, b) => a + b, 0) / n
  const std = Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / n)
  const iqr = (() => {
    const sorted = [...values].sort((a, b) => a - b)
    const q1 = sorted[Math.floor(n * 0.25)]
    const q3 = sorted[Math.floor(n * 0.75)]
    return q3 - q1
  })()
  const defaultBandwidth = 0.9 * Math.min(std, iqr / 1.34) / Math.pow(n, 0.2)
  const h = bandwidth ?? Math.max(defaultBandwidth, 0.001) // 防止 bandwidth 为 0

  const dataMin = Math.min(...values)
  const dataMax = Math.max(...values)
  const range = dataMax - dataMin || 1 // 防止 range 为 0
  const numPoints = 200

  // 如果指定了 minX，确保不从 minX 以下开始绘制
  const plotMin = minX !== undefined ? Math.max(dataMin - range * 0.1, minX) : dataMin - range * 0.1

  const points = Array.from({ length: numPoints }, (_, i) => {
    const x = plotMin + (i / (numPoints - 1)) * (dataMax - plotMin + range * 0.1)
    let density = 0
    for (const v of values) {
      const u = (x - v) / h
      density += Math.exp(-0.5 * u * u)
    }
    density /= (n * h * Math.sqrt(2 * Math.PI))
    return { x, y: density }
  })

  return { points, bandwidth: h }
}

// 获取分组键名
function getGroupKey(dim: ParamConfig): string {
  if (dim.id === 'beta') return 'beta_true'
  if (dim.id === 'eta') return 'eta'
  if (dim.id === 'gamma') return 'gamma'
  if (dim.id === 'sampleSize') return 'sample_size'
  if (dim.id === 'process') return 'offset_value'
  return dim.id
}

// 颜色梯度生成（按分组数量）
function generateColors(count: number, baseColor: string): string[] {
  // 预定义的颜色序列
  const colorScales: Record<string, string[]> = {
    blue: ['#dbeafe', '#93c5fd', '#60a5fa', '#3b82f6', '#1d4ed8', '#1e40af'],
    emerald: ['#d1fae5', '#6ee7b7', '#34d399', '#10b981', '#059669', '#047857'],
    amber: ['#fef3c7', '#fcd34d', '#fbbf24', '#f59e0b', '#d97706', '#b45309'],
    purple: ['#ede9fe', '#c4b5fd', '#a78bfa', '#8b5cf6', '#7c3aed', '#6d28d9'],
    rose: ['#ffe4e6', '#fda4af', '#fb7185', '#f43f5e', '#e11d48', '#be123c'],
  }

  const scale = colorScales[baseColor] || colorScales.blue
  const result: string[] = []

  for (let i = 0; i < count; i++) {
    const idx = Math.floor((i / Math.max(count - 1, 1)) * (scale.length - 1))
    result.push(scale[idx])
  }

  return result
}

export function DensityChart({
  rawData,
  paramId,
  displayDimension,
  trueValue,
  color
}: DensityChartProps) {
  // 获取估计值字段名
  const estKey = `est_${paramId}`

  // 获取分组键名
  const groupKey = getGroupKey(displayDimension)

  // 按显示维度分组
  const groups: GroupData[] = []
  const groupMap = new Map<string, number[]>()

  for (const row of rawData) {
    const estValue = row[estKey]
    const groupValue = row[groupKey]

    if (estValue !== null && estValue !== undefined && typeof estValue === 'number' && groupValue !== undefined) {
      const key = String(groupValue)
      if (!groupMap.has(key)) {
        groupMap.set(key, [])
      }
      groupMap.get(key)!.push(estValue)
    }
  }

  // 排序分组
  const sortedKeys = Array.from(groupMap.keys()).sort((a, b) => {
    const numA = parseFloat(a)
    const numB = parseFloat(b)
    if (!isNaN(numA) && !isNaN(numB)) return numA - numB
    return a.localeCompare(b)
  })

  // 生成颜色
  const colors = generateColors(sortedKeys.length, color)

  // 构建分组数据
  for (let i = 0; i < sortedKeys.length; i++) {
    const key = sortedKeys[i]
    const values = groupMap.get(key)!
    if (values.length > 0) {
      groups.push({
        key,
        label: `${displayDimension.symbol}=${key}`,
        values,
        color: colors[i]
      })
    }
  }

  // 如果没有数据，返回空
  if (groups.length === 0) {
    return (
      <div className="h-[280px] flex items-center justify-center text-slate-400">
        无有效数据
      </div>
    )
  }

  // 计算每组的 KDE
  const kdeData = groups.map(g => ({
    ...g,
    kde: computeKDE(g.values, undefined, paramId === 'gamma' ? 0 : undefined).points
  }))

  // 格式化值
  const formatX = (val: number) => {
    if (paramId === 'beta') return val.toFixed(2)
    return val.toFixed(0)
  }

  return (
    <>
      {/* 图例 */}
      <div className="flex flex-wrap gap-3 mb-3 text-xs justify-center">
        {groups.map(g => (
          <span key={g.key} className="flex items-center gap-1">
            <span
              className="w-4 h-0.5 inline-block"
              style={{ backgroundColor: g.color }}
            ></span>
            <span className="text-slate-600">{g.label}</span>
          </span>
        ))}
        <span className="flex items-center gap-1 ml-2">
          <span className="w-4 h-0.5 bg-red-500 inline-block" style={{ borderStyle: 'dashed' }}></span>
          <span className="text-slate-600">真实值</span>
        </span>
      </div>

      {/* 图表 */}
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart margin={{ top: 10, right: 15, bottom: 30, left: 45 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis
              dataKey="x"
              tick={{ fontSize: 10 }}
              type="number"
              domain={['auto', 'auto']}
              tickFormatter={formatX}
            />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip
              contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
              formatter={(v: number) => v.toFixed(4)}
              labelFormatter={(l) => `${paramId}: ${Number(l).toFixed(paramId === 'beta' ? 3 : 1)}`}
            />
            <ReferenceLine
              x={trueValue}
              stroke="#ef4444"
              strokeDasharray="5 5"
              strokeWidth={2}
            />
            {kdeData.map(g => (
              <Line
                key={g.key}
                type="monotone"
                dataKey="y"
                data={g.kde}
                stroke={g.color}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 说明 */}
      <p className="text-center text-xs text-slate-500 mt-2">
        使用高斯核密度估计 (KDE)。
        <span className="text-red-500 font-medium ml-1">红色虚线</span>为真实参数值 ({trueValue})。
      </p>
    </>
  )
}

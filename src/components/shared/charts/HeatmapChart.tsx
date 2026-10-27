/**
 * 热力图组件 - 用于展示双变量参数偏差
 *
 * 显示：二维表格形式，颜色表示偏差方向和程度
 * - 低估（蓝色）到高估（红色）
 * - 偏差越大颜色越深
 *
 * 设计：只输出热力图表格，外框由 ChartCard 提供
 */
import React from 'react'

// 参数配置类型
interface ParamConfig {
  id: string
  name: string
  symbol: string
}

// 通用数据类型
interface HeatmapDataRow {
  [key: string]: number | string | null | undefined
}

interface HeatmapChartProps {
  stats: HeatmapDataRow[]
  displayDimensions: ParamConfig[]
  dataKey: string
  maxAbs: number
}

export function HeatmapChart({
  stats,
  displayDimensions,
  dataKey,
  maxAbs
}: HeatmapChartProps) {
  // 获取颜色
  const getColorForValue = (value: number | null) => {
    if (value === null) return '#f3f4f6'
    const ratio = maxAbs > 0 ? value / maxAbs : 0
    const intensity = Math.abs(ratio)

    if (ratio >= 0) {
      const r = 254 - Math.round(intensity * 38)
      const g = 202 - Math.round(intensity * 164)
      const b = 202 - Math.round(intensity * 164)
      return `rgb(${r}, ${g}, ${b})`
    } else {
      const r = 191 - Math.round(intensity * 154)
      const g = 219 - Math.round(intensity * 118)
      const b = 254 - Math.round(intensity * 12)
      return `rgb(${r}, ${g}, ${b})`
    }
  }

  // 获取维度键名
  const getVarKey = (dim: ParamConfig) => {
    if (dim.id === 'beta') return 'beta_true'
    if (dim.id === 'eta') return 'eta_true'
    if (dim.id === 'sampleSize') return 'sample_size'
    if (dim.id === 'process') return 'offset_value'
    if (dim.id === 'rep') return 'rep'
    if (dim.id === 'step') return 'step'
    return dim.id
  }

  const var1Key = getVarKey(displayDimensions[0])
  const var2Key = getVarKey(displayDimensions[1])

  const firstDimValues = Array.from(new Set(stats.map(s => s[var1Key])))
    .filter((v): v is number => v !== null && v !== undefined && typeof v === 'number')
    .sort((a, b) => a - b)

  const secondDimValues = Array.from(new Set(stats.map(s => s[var2Key])))
    .filter((v): v is number => v !== null && v !== undefined && typeof v === 'number')
    .sort((a, b) => a - b)

  // 格式化值
  const formatValue = (val: number, paramId: string) => {
    if (paramId === 'process' || (val < 1 && val !== 0)) return val.toFixed(2)
    return val.toString()
  }

  // 构建数据矩阵
  const heatmapData = secondDimValues.map(yVal =>
    firstDimValues.map(xVal => {
      const item = stats.find(s => s[var1Key] === xVal && s[var2Key] === yVal)
      const value = item ? (item[dataKey] as number | null) : null
      return { value, hasData: !!item && value !== null }
    })
  )

  return (
    <>
      {/* 图例 */}
      <div className="flex items-center justify-center gap-2 mb-2">
        <span className="text-xs font-medium text-slate-600">低估</span>
        <div className="flex items-center">
          <div className="w-8 h-2.5 rounded-l" style={{ backgroundColor: getColorForValue(-maxAbs) }}></div>
          <div className="w-8 h-2.5 bg-slate-100"></div>
          <div className="w-8 h-2.5 rounded-r" style={{ backgroundColor: getColorForValue(maxAbs) }}></div>
        </div>
        <span className="text-xs font-medium text-slate-600">高估</span>
        <span className="text-xs text-slate-400 ml-2 font-mono">[{(-maxAbs).toFixed(3)}, {maxAbs.toFixed(3)}]</span>
      </div>

      {/* 热力图表格 */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse" style={{ tableLayout: 'auto' }}>
          <thead>
            <tr>
              <th className="bg-slate-50 border border-slate-300" style={{ width: '50px', padding: '0' }}>
                <div style={{
                  position: 'relative',
                  width: '50px',
                  height: '40px',
                  background: 'linear-gradient(to top right, transparent calc(50% - 0.5px), #64748b calc(50% - 0.5px), #64748b calc(50% + 0.5px), transparent calc(50% + 0.5px))'
                }}>
                  <span style={{ position: 'absolute', top: '2px', right: displayDimensions[0].id === 'sampleSize' ? '1px' : displayDimensions[0].id === 'beta' ? '6px' : '3px', fontSize: '13px', fontWeight: 600, color: '#374151' }}>{displayDimensions[0].symbol}</span>
                  <span style={{ position: 'absolute', bottom: '2px', left: displayDimensions[1].id === 'sampleSize' ? '1px' : displayDimensions[1].id === 'beta' ? '6px' : '3px', fontSize: '13px', fontWeight: 600, color: '#374151' }}>{displayDimensions[1].symbol}</span>
                </div>
              </th>
              {firstDimValues.map(val => (
                <th key={val} className="px-1.5 py-1 bg-slate-50 border border-slate-300 text-sm font-bold text-slate-700">{formatValue(val, displayDimensions[0].id)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {secondDimValues.map((yVal, yIdx) => (
              <tr key={yVal}>
                <td className="px-1.5 py-1 bg-slate-50 border border-slate-300 text-sm font-bold text-slate-700 text-center" style={{ width: '50px' }}>{formatValue(yVal, displayDimensions[1].id)}</td>
                {heatmapData[yIdx].map((cell, xIdx) => (
                  <td key={xIdx} className="px-1.5 py-1 text-center border border-slate-200" style={{ backgroundColor: cell.hasData ? getColorForValue(cell.value) : '#f3f4f6' }}>
                    <span className="font-mono text-xs font-medium" style={{ color: cell.hasData ? '#000000' : '#9ca3af' }}>
                      {cell.hasData ? cell.value!.toFixed(3) : '—'}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

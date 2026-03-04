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
    if (dim.id === 'sampleSize') return 'sample_size'
    return 'offset_value'
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
      <div className="flex items-center justify-center gap-3 mb-3">
        <span className="text-sm font-semibold text-slate-700">低估</span>
        <div className="flex items-center">
          <div className="w-10 h-3 rounded-l" style={{ backgroundColor: getColorForValue(-maxAbs) }}></div>
          <div className="w-10 h-3 bg-slate-100"></div>
          <div className="w-10 h-3 rounded-r" style={{ backgroundColor: getColorForValue(maxAbs) }}></div>
        </div>
        <span className="text-sm font-semibold text-slate-700">高估</span>
        <span className="text-sm text-slate-500 ml-3 font-mono">[{(-maxAbs).toFixed(3)}, {maxAbs.toFixed(3)}]</span>
      </div>

      {/* 热力图表格 */}
      <div className="overflow-x-auto">
        <table className="w-full text-base border-collapse" style={{ tableLayout: 'auto' }}>
          <thead>
            <tr>
              <th className="bg-slate-50 border border-slate-300" style={{ width: '80px', padding: '0' }}>
                <div style={{
                  position: 'relative',
                  width: '80px',
                  height: '60px',
                  background: 'linear-gradient(to top right, transparent calc(50% - 0.5px), #64748b calc(50% - 0.5px), #64748b calc(50% + 0.5px), transparent calc(50% + 0.5px))'
                }}>
                  <span style={{ position: 'absolute', top: '4px', right: displayDimensions[0].id === 'sampleSize' ? '1px' : displayDimensions[0].id === 'beta' ? '11px' : '6px', fontSize: '19px', fontWeight: 600, color: '#374151' }}>{displayDimensions[0].symbol}</span>
                  <span style={{ position: 'absolute', bottom: '4px', left: displayDimensions[1].id === 'sampleSize' ? '1px' : displayDimensions[1].id === 'beta' ? '11px' : '6px', fontSize: '19px', fontWeight: 600, color: '#374151' }}>{displayDimensions[1].symbol}</span>
                </div>
              </th>
              {firstDimValues.map(val => (
                <th key={val} className="p-2.5 bg-slate-50 border border-slate-300 text-xl font-bold text-slate-800">{formatValue(val, displayDimensions[0].id)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {secondDimValues.map((yVal, yIdx) => (
              <tr key={yVal}>
                <td className="p-2.5 bg-slate-50 border border-slate-300 text-xl font-bold text-slate-800 text-center" style={{ width: '80px' }}>{formatValue(yVal, displayDimensions[1].id)}</td>
                {heatmapData[yIdx].map((cell, xIdx) => (
                  <td key={xIdx} className="p-2.5 text-center border border-slate-200" style={{ backgroundColor: cell.hasData ? getColorForValue(cell.value) : '#f3f4f6' }}>
                    <span className="font-mono text-xl font-semibold" style={{ color: cell.hasData ? '#000000' : '#9ca3af' }}>
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

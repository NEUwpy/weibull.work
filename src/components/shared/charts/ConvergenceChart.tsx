/**
 * 收敛图组件 - 用于展示统计量随仿真次数的收敛趋势
 *
 * 显示：以重复次数为横坐标，统计量（均值/中位数/标准差）为纵坐标
 * 用途：示例2中使用，展示 MDM 估计随蒙特卡洛仿真次数增加时的收敛特性
 *
 * 设计：只输出图表，外框由 ChartCard 提供
 */
import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

// 数据点类型
interface DataPoint {
  mcRuns: number    // x 轴: 重复次数
  value: number      // y 轴: 统计量值
}

// 单条曲线数据
export interface CurveData {
  id: string            // 样本量标识，如 "n=3"
  label: string          // 显示标签
  data: DataPoint[]
  color: string
}

interface ConvergenceChartProps {
  curves: CurveData[]                    // 多条曲线（每个样本量一条）
  statType: 'mean' | 'median' | 'std'  // 统计类型
  trueValue: number                      // 真实值（参考线）
  yLabel: string                        // y 轴标签
  title?: string                        // 图表标题
}

// 生成颜色梯度（按样本量数量）
function generateColors(count: number): string[] {
  const palette = [
    '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444',
    '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1'
  ]
  const result: string[] = []
  for (let i = 0; i < count; i++) {
    result.push(palette[i % palette.length])
  }
  return result
}

export function ConvergenceChart({
  curves,
  statType,
  trueValue,
  yLabel,
  title
}: ConvergenceChartProps) {
  // 状态标签映射
  const statLabels: Record<string, string> = {
    mean: '均值',
    median: '中位数',
    std: '标准差'
  }

  // 如果没有数据
  if (!curves || curves.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-slate-400">
        无有效数据
      </div>
    )
  }

  // 为曲线分配颜色
  const colors = generateColors(curves.length)
  const coloredCurves = curves.map((c, i) => ({ ...c, color: c.color || colors[i] }))

  // 合并所有曲线的数据点用于 X 轴域计算
  const allPoints = coloredCurves.flatMap(c => c.data)
  const xDomain = [
    Math.min(...allPoints.map(p => p.mcRuns)),
    Math.max(...allPoints.map(p => p.mcRuns))
  ]

  // 格式化函数
  const formatX = (val: number) => val.toLocaleString()
  const formatY = (val: number) => {
    if (Math.abs(val) >= 1000) return val.toFixed(0)
    if (Math.abs(val) >= 1) return val.toFixed(2)
    return val.toFixed(4)
  }

  return (
    <>
      {title && (
        <p className="text-center text-sm font-semibold text-slate-700 mb-2">{title}</p>
      )}

      {/* 图例 */}
      <div className="flex flex-wrap gap-3 mb-3 text-xs justify-center">
        {coloredCurves.map(curve => (
          <span key={curve.id} className="flex items-center gap-1">
            <span
              className="w-4 h-0.5 inline-block rounded"
              style={{ backgroundColor: curve.color }}
            ></span>
            <span className="text-slate-600">{curve.label}</span>
          </span>
        ))}
        {trueValue !== undefined && (
          <span className="flex items-center gap-1 ml-2">
            <span className="w-4 h-0.5 bg-red-500 inline-block" style={{ borderStyle: 'dashed' }}></span>
            <span className="text-slate-600">真实值</span>
          </span>
        )}
      </div>

      {/* 图表 */}
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            margin={{ top: 10, right: 20, bottom: 30, left: 50 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis
              dataKey="mcRuns"
              type="number"
              domain={xDomain}
              tick={{ fontSize: 10 }}
              tickFormatter={formatX}
              label={{ value: '重复次数', position: 'bottom', offset: 0, fontSize: 11 }}
            />
            <YAxis
              tick={{ fontSize: 10 }}
              tickFormatter={formatY}
              label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{ borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '11px' }}
              formatter={(value: number) => [formatY(value), yLabel]}
              labelFormatter={(label: number) => `MC: ${formatX(label)}`}
            />
            {trueValue !== undefined && (
              <ReferenceLine
                y={trueValue}
                stroke="#ef4444"
                strokeDasharray="5 5"
                strokeWidth={2}
              />
            )}
            {coloredCurves.map((curve) => (
              <Line
                key={curve.id}
                type="monotone"
                dataKey="value"
                data={curve.data}
                stroke={curve.color}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="text-center text-xs text-slate-500 mt-2">
        横轴为蒙特卡洛重复次数，纵轴为参数估计{statLabels[statType]}。
        {trueValue !== undefined && (
          <><span className="text-red-500 font-medium ml-1">红色虚线</span>为真实值 ({trueValue})。</>
        )}
      </p>
    </>
  )
}

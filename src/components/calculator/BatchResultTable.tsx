'use client'

import type { DataSource } from '@/lib/weibull'
import { formatCalculationNumber as number } from '@/lib/calculation-trace'

export function BatchResultTable({ sources, activeIndex, onSelect }: {
  sources: DataSource[]; activeIndex: number; onSelect: (index: number) => void
}) {
  return <div className="flex h-full min-h-0 flex-col px-4 py-3" aria-label="整组结果表">
    <h3 className="mb-2 shrink-0 text-base font-semibold text-slate-700">整组结果</h3>
    <div className="min-h-0 flex-1 overflow-auto">
      <table className="w-full text-right text-sm tabular-nums text-slate-700">
        <thead className="sticky top-0 bg-white text-slate-500"><tr>
          {['组号', '样本数', 'β', 'η', 'γ', 'R²', '状态'].map(label =>
            <th key={label} className="whitespace-nowrap border-b border-slate-200 px-4 py-2 font-medium">{label}</th>)}
        </tr></thead>
        <tbody>{sources.map((source, index) => <tr key={source.id} data-batch-result={index + 1}
          className={activeIndex === index ? 'bg-indigo-50/70' : ''}>
          <th scope="row" className="border-b border-slate-100 px-4 py-2 font-medium">
            <button type="button" onClick={() => onSelect(index)} className="text-indigo-600 hover:underline"
              aria-label={'查看第 ' + (index + 1) + ' 组'}>{index + 1}</button>
          </th>
          {[source.data.length, number(source.result?.beta), number(source.result?.eta), number(source.result?.gamma),
            number(source.result?.rSquared)].map((value, column) =>
            <td key={column} className="whitespace-nowrap border-b border-slate-100 px-4 py-2">{value}</td>)}
          <td className="whitespace-nowrap border-b border-slate-100 px-4 py-2" title={source.calculationError}>
            {source.result ? '已估计' : source.calculationError ? '失败' : '未估计'}
          </td>
        </tr>)}</tbody>
      </table>
    </div>
  </div>
}

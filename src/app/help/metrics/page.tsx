"use client"

/**
 * 统一评价指标规范页面
 *
 * 本页面是规范源 `metrics-spec.ts` 的渲染视图，不拥有指标事实。
 * 可执行实现见 `src/lib/metrics.ts` 与 `python/studies/common/metrics.py`。
 *
 * 修改指标口径时：改 metrics-spec.ts → 同步 metrics.ts / metrics.py。
 * 修改页面布局/交互时：只改本文件。
 */

import React from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { cn } from '@/lib/utils'
import {
  METRICS,
  PERSPECTIVES,
  STATUS_DEFINITIONS,
  DEPRECATED_METRICS,
  DEV_NORMS,
  PAGE_DESCRIPTION,
  IMPLEMENTATION_PATHS,
  type MetricDef,
} from './metrics-spec'

const CATEGORY_LABELS: Record<MetricDef['category'], string> = {
  primary: '主指标',
  supplementary: '补充指标',
  diagnostic: '诊断指标',
}

function Latex({ math, block = false }: { math: string; block?: boolean }) {
  try {
    const html = katex.renderToString(math, {
      throwOnError: false,
      displayMode: block,
      trust: true,
      strict: false,
    })
    return (
      <span
        className={cn(block && 'block py-1')}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    )
  } catch {
    return <span className="text-red-500 font-mono text-xs">{math}</span>
  }
}

function VariableList({ variables }: { variables: Record<string, string> }) {
  return (
    <dl className="mt-3 grid grid-cols-1 gap-1 text-xs text-slate-500">
      {Object.entries(variables).map(([symbol, meaning]) => (
        <div key={symbol} className="flex gap-2">
          <dt className="min-w-16 font-mono font-bold text-slate-700">{symbol}</dt>
          <dd>{meaning}</dd>
        </div>
      ))}
    </dl>
  )
}

function MetricCard({ metric }: { metric: MetricDef }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex flex-wrap items-baseline gap-2">
        <span className="font-mono text-sm font-black text-slate-900">{metric.name}</span>
        <span className="text-sm text-slate-500">{metric.nameCn}</span>
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-500">{metric.role}</span>
        <span className="rounded-md bg-blue-50 px-2 py-0.5 text-xs font-bold text-blue-600">{CATEGORY_LABELS[metric.category]}</span>
      </div>
      <div className="mb-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-center">
        <Latex math={metric.latex} block />
      </div>
      <p className="text-sm leading-relaxed text-slate-600">{metric.description}</p>
      <VariableList variables={metric.variables} />
      <div className="mt-3 flex flex-wrap gap-1">
        {metric.perspectives.map(perspective => (
          <span key={perspective} className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{perspective}</span>
        ))}
      </div>
      <div className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-xs text-slate-500">
        <div>TS: <code className="rounded bg-slate-100 px-1">{metric.implementation.ts}</code></div>
        <div>PY: <code className="rounded bg-slate-100 px-1">{metric.implementation.py}</code></div>
      </div>
    </div>
  )
}

export default function MetricsPage() {
  return (
    <div className="space-y-8 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <div>
        <div className="mb-2 text-xs font-black uppercase tracking-wider text-blue-600">Evaluation Metrics</div>
        <h1 className="mb-2 text-2xl font-black text-slate-900">指标规范</h1>
        <p className="max-w-4xl text-sm leading-relaxed text-slate-500">
          {PAGE_DESCRIPTION}
          <code className="mx-1 rounded bg-slate-100 px-1 text-xs">{IMPLEMENTATION_PATHS.ts}</code>
          和
          <code className="mx-1 rounded bg-slate-100 px-1 text-xs">{IMPLEMENTATION_PATHS.py}</code>。
        </p>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-900">核心指标族</h2>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {METRICS.map(metric => <MetricCard key={metric.id} metric={metric} />)}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-900">三种视角</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {PERSPECTIVES.map(item => (
            <div key={item.id} className={cn('rounded-lg border p-4', item.bg, item.border)}>
              <h3 className={cn('mb-2 text-sm font-black', item.accent)}>{item.title}</h3>
              <div className="mb-3 rounded-lg border border-white/70 bg-white px-3 py-2 text-center">
                <Latex math={item.formula} block />
              </div>
              <p className="text-sm leading-relaxed text-slate-600">{item.body}</p>
              <VariableList variables={item.variables} />
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
        <h2 className="mb-3 text-sm font-black text-amber-900">状态判定口径</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {STATUS_DEFINITIONS.map(def => (
            <div key={def.id} className={cn('rounded-lg border bg-white p-3', def.borderColor)}>
              <div className={cn('mb-1 font-mono text-sm font-bold', def.color)}>{def.label}</div>
              <p className="text-xs leading-relaxed text-slate-600">{def.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-slate-50 p-5">
        <h2 className="mb-3 text-sm font-black text-slate-900">已废止旧指标</h2>
        <p className="text-sm leading-relaxed text-slate-600">{DEPRECATED_METRICS}</p>
      </section>

      <section className="rounded-lg border border-blue-100 bg-blue-50 p-5">
        <h2 className="mb-3 text-sm font-black text-blue-900">开发规范</h2>
        <ul className="space-y-2 text-sm leading-relaxed text-blue-800">
          {DEV_NORMS.map(norm => (
            <li key={norm.id}>• {norm.content}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}

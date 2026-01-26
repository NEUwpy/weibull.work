import React from 'react'
import { Sigma, Info } from 'lucide-react'
import katex from 'katex'
import { cn } from '@/lib/utils'
import { MethodNode } from '@/lib/methods'

// KaTeX Renderer Component
const LatexRenderer = ({ math, block = false }: { math: string, block?: boolean }) => {
  try {
    const html = katex.renderToString(math, {
      throwOnError: false,
      displayMode: block,
      trust: true,
      strict: false
    })
    return <div className={cn("overflow-x-auto", block ? "py-2" : "inline")} dangerouslySetInnerHTML={{ __html: html }} />
  } catch (e) {
    return <span className="text-red-500 font-mono text-xs">LaTeX Error</span>
  }
}

interface MethodDetailContentProps {
  method: MethodNode
  category?: {
    shortName: string
    name: string
  }
}

/**
 * 方法详情内容组件
 * 用于展示方法的核心公式和描述
 * 在计算器弹窗和方法详情页中共享使用
 */
export function MethodDetailContent({ method, category }: MethodDetailContentProps) {
  return (
    <div className="space-y-8">
      {/* Formula Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-slate-900 font-bold text-sm uppercase tracking-wider">
          <Sigma size={16} className="text-blue-500" />
          核心公式 (Formula)
        </div>
        <div className="bg-slate-900 rounded-2xl p-6 shadow-inner overflow-x-auto border border-slate-800">
          <div className="text-white">
            <LatexRenderer math={method.formula} block />
          </div>
        </div>
      </div>

      {/* Description Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-slate-900 font-bold text-sm uppercase tracking-wider">
          <Info size={16} className="text-blue-500" />
          算法描述 (Description)
        </div>
        <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100 text-slate-600 leading-relaxed text-sm">
          {method.description}
        </div>
      </div>
    </div>
  )
}

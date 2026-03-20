/**
 * MDM 案例组件注册表
 *
 * 添加新案例的步骤：
 * 1. 在下方 CASE_COMPONENTS 对象中添加新条目
 * 2. 创建对应的 CaseXXViewer.tsx 组件文件
 *
 * API 会自动扫描目录，无需修改
 */

import dynamic from 'next/dynamic'
import React from 'react'

// 统一的加载组件
const LoadingSpinner = ({ name }: { name: string }) => (
  <div className="bg-white rounded-2xl border border-slate-200 p-12">
    <div className="flex flex-col items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200 border-t-blue-600 mb-4"></div>
      <p className="text-slate-600 font-bold">加载{name}分析中...</p>
    </div>
  </div>
)

// 案例组件类型
interface CaseComponentProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

type CaseComponent = React.ComponentType<CaseComponentProps>

// 案例组件注册表
// 添加新案例时，在这里添加一行即可
const CASE_COMPONENTS_REGISTRY: Record<string, React.ComponentType<CaseComponentProps>> = {
  // 特殊架构案例
  'case3': dynamic(() => import('./case3/Case3Viewer'), { ssr: false, loading: () => <LoadingSpinner name="案例3" /> }),
  'case5': dynamic(() => import('./case5/Case5Viewer'), { ssr: false, loading: () => <LoadingSpinner name="案例5" /> }),
  'case14': dynamic(() => import('./case14/Case14Viewer'), { ssr: false, loading: () => <LoadingSpinner name="案例14" /> }),
  // 添加新案例时，在这里添加：
  // 'case17': dynamic(() => import('./case17/Case17Viewer'), { ssr: false, loading: () => <LoadingSpinner name="案例17" /> }),
}

/**
 * 获取案例组件
 * @param architecture 案例架构类型
 * @returns 组件或 null
 */
export function getCaseComponent(architecture: string): React.ComponentType<CaseComponentProps> | null {
  return CASE_COMPONENTS_REGISTRY[architecture] || null
}

/**
 * 检查是否有特殊架构组件
 */
export function hasSpecialArchitecture(architecture: string): boolean {
  return architecture in CASE_COMPONENTS_REGISTRY
}

export { LoadingSpinner }

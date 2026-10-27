/**
 * MDM 可信性验证组件注册表
 *
 * 新架构：所有验证项通过配置文件动态加载
 * 此文件保留作为扩展入口
 */

import React from 'react'

// 验证组件类型
interface VerificationComponentProps {
  verificationId: string
  onVerificationChange?: (verificationId: string) => void
}

// 特殊验证组件注册表（如需自定义渲染时使用）
const VERIFICATION_COMPONENTS_REGISTRY: Record<string, React.ComponentType<VerificationComponentProps>> = {
  // 添加需要自定义渲染的验证项：
  // 'special-case': dynamic(() => import('./special/SpecialViewer'), { ssr: false }),
}

/**
 * 获取验证组件
 */
export function getVerificationComponent(verificationId: string): React.ComponentType<VerificationComponentProps> | null {
  return VERIFICATION_COMPONENTS_REGISTRY[verificationId] || null
}

/**
 * 检查是否有特殊验证组件
 */
export function hasSpecialVerification(verificationId: string): boolean {
  return verificationId in VERIFICATION_COMPONENTS_REGISTRY
}


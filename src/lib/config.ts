/**
 * API 配置
 * 根据环境自动选择正确的 API 基础 URL
 *
 * 生产环境：使用 api.weibull.work 子域名
 * 开发环境：使用 127.0.0.1:8001，避免 localhost 在 Windows 上被解析到
 * 另一个 IPv4/IPv6 监听进程。
 */

// 获取 API 基础 URL
export const getApiBaseUrl = (): string => {
  // 开发环境使用明确的 IPv4 回环地址
  if (process.env.NODE_ENV === 'development') {
    return 'http://127.0.0.1:8001'
  }

  // 生产环境使用 api 子域名
  return 'https://api.weibull.work'
}

// 应用版本号 —— 由 next.config.js 从 08-更新日志.md 头部提取，构建时注入
export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || 'v0.00-000000'

// API 端点
export const API_ENDPOINTS = {
  calculate: '/calculate',
  calculate3DSurface: '/calculate_3d_surface',
  aiOptimizeMdmOffset: '/ai/process-optimization/mdm',
  aiDirectEstimation: '/ai/direct-estimation',
} as const

/**
 * API 配置
 * 根据环境自动选择正确的 API 基础 URL
 *
 * 生产环境：使用同域名的 /api 路径 (https://weibull.work/api)
 * 开发环境：使用 localhost:8001
 */

// 检测是否在浏览器端运行
const isBrowser = typeof window !== 'undefined'

// 获取 API 基础 URL
export const getApiBaseUrl = (): string => {
  // 开发环境使用 localhost
  if (process.env.NODE_ENV === 'development') {
    return 'http://localhost:8001'
  }

  // 生产环境使用同域名的 /api 路径
  // 浏览器端使用相对路径
  if (isBrowser) {
    return '/api'
  }

  // 服务端渲染时使用完整 URL
  return 'https://weibull.work/api'
}

// API 端点
export const API_ENDPOINTS = {
  calculate: '/calculate',
  calculate3DSurface: '/calculate_3d_surface',
} as const

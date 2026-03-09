/**
 * API 配置
 * 根据环境自动选择正确的 API 基础 URL
 */

// 检测是否在浏览器端运行
const isBrowser = typeof window !== 'undefined'

// 获取 API 基础 URL
export const getApiBaseUrl = (): string => {
  // 优先使用环境变量
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL
  }

  // 开发环境使用 localhost
  if (process.env.NODE_ENV === 'development') {
    return 'http://localhost:8001'
  }

  // 生产环境使用 api.weibull.work
  // 浏览器端使用相对协议
  if (isBrowser) {
    return `${window.location.protocol}//api.${window.location.host}`
  }

  // 服务端渲染时使用 https
  return 'https://api.weibull.work'
}

// API 端点
export const API_ENDPOINTS = {
  calculate: '/calculate',
  calculate3DSurface: '/calculate_3d_surface',
} as const

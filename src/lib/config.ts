/**
 * API 配置
 * 根据环境自动选择正确的 API 基础 URL
 *
 * 生产环境：使用 api.weibull.work 子域名
 * 开发环境：使用 localhost:8001
 */

// 获取 API 基础 URL
export const getApiBaseUrl = (): string => {
  // 开发环境使用 localhost
  if (process.env.NODE_ENV === 'development') {
    return 'http://localhost:8001'
  }

  // 生产环境使用 api 子域名
  return 'https://api.weibull.work'
}

// API 端点
export const API_ENDPOINTS = {
  calculate: '/calculate',
  calculate3DSurface: '/calculate_3d_surface',
} as const

const fs = require('fs')
const path = require('path')
const { PHASE_DEVELOPMENT_SERVER } = require('next/constants')

// 从 08-更新日志.md 头部提取版本号
let appVersion = 'v0.0.0-000000'
try {
  const content = fs.readFileSync(path.join(__dirname, '08-更新日志.md'), 'utf-8')
  const match = content.match(/^## (v\S+)/m)
  if (match) appVersion = match[1]
} catch {}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    instrumentationHook: true,
    outputFileTracingIncludes: {
      '/api/method-flow/*': [
        './src/data/method_flows/*.json',
        './src/content/algorithms/*.md',
        './python/base.py',
        './python/methods/*.py',
        './python/methods/j3_weights.tsv',
      ],
      '/api/monte-carlo/*/process': ['./python/methods/mdm.py'],
    },
  },
  env: {
    NEXT_PUBLIC_APP_VERSION: appVersion,
  },
}

// Keep hot-reload artifacts separate so a local preview never conflicts with next build/start.
module.exports = phase => ({
  ...nextConfig,
  distDir: phase === PHASE_DEVELOPMENT_SERVER ? '.next-dev' : '.next',
})

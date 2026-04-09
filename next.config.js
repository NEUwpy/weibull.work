const fs = require('fs')
const path = require('path')

// 从 08-更新日志.md 头部提取版本号
let appVersion = 'v0.00-000000'
try {
  const content = fs.readFileSync(path.join(__dirname, '08-更新日志.md'), 'utf-8')
  const match = content.match(/^## (v\S+)/m)
  if (match) appVersion = match[1]
} catch {}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  env: {
    NEXT_PUBLIC_APP_VERSION: appVersion,
  },
}

module.exports = nextConfig

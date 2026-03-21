# 待办事项

## 2026-03-10: 前后端统一域名部署

### 任务目标
将 API 访问从 `https://api.weibull.work/` 改为 `https://weibull.work/api/`

### 已完成事项
- [x] 修改前端代码
  - [x] 修改 `src/lib/config.ts` - 生产环境使用 `/api` 路径
  - [x] 修改 `.env.production` - 更新 API URL 配置
  - [x] 修复硬编码的 localhost:8001 (page.tsx, methods/[methodId]/page.tsx)
- [x] 更新 Cloudflare Tunnel 配置
  - [x] 在 Cloudflare Dashboard 中配置路由：
  - [x] 重新部署并测试
- - [x] 更新部署文档
- - [x] 更新本地代码中的 Dockerfile.backend（添加清华镜像源）

  - [x] 更新凭证文档（用户名、项目路径)

### 待办
无

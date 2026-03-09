# 待办事项

## 2026-03-10: 前后端统一域名部署

### 任务目标
将 API 访问从 `https://api.weibull.work/` 改为 `https://weibull.work/api/`，实现前后端使用同一域名。

### 待办列表

- [ ] **1. 修改前端代码**
  - [ ] 修改 `src/lib/config.ts` - 生产环境使用 `/api` 路径
  - [ ] 修改 `src/app/page.tsx` - 移除硬编码的 localhost:8001
  - [ ] 修改 `src/app/methods/[methodId]/page.tsx` - 使用统一的 API 配置

- [ ] **2. 修改配置文件**
  - [ ] 修改 `.env.production` - 更新 API URL

- [ ] **3. 本地提交代码**
  - [ ] git add & commit

- [ ] **4. 推送到 GitHub**
  - [ ] git push

- [ ] **5. 更新 NAS 服务器**
  - [ ] SSH 到 NAS
  - [ ] 重新拉取代码
  - [ ] 重新构建部署

- [ ] **6. 配置 Cloudflare Tunnel**
  - [ ] 添加路径路由: `/api/*` -> `http://localhost:8001`

- [ ] **7. 测试验证**
  - [ ] 测试前端访问 https://weibull.work/
  - [ ] 测试后端 API https://weibull.work/api/calculate

- [ ] **8. 更新部署文档**
  - [ ] 记录完整部署流程

### 当前状态
- Docker 容器已部署成功 (frontend:3000, backend:8001, cloudflared)
- 前端 https://weibull.work/ 正常访问
- 后端 API 需要统一域名配置

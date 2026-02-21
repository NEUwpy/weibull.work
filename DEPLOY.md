# 部署指南

## 前置条件

1. 域名已托管到 Cloudflare（NS 已修改）
2. 绿联 NAS 已安装 Docker
3. 项目代码已上传到 NAS

---

## 第一步：Cloudflare Tunnel 设置

### 1.1 创建 Tunnel

1. 登录 https://one.dash.cloudflare.com
2. 左侧菜单 → **Networks** → **Tunnels**
3. 点击 **Create a tunnel**
4. 选择 **Cloudflared**，点击 Next
5. 输入 Tunnel 名称，如 `weibull`，点击 Save

### 1.2 获取 Token

创建后会显示安装命令，找到 `--token` 后面的那串字符，复制下来。

类似：
```
--token eyJhIjoixxxx...长串字符...
```

### 1.3 配置路由（Public Hostname）

在 Tunnel 设置页面，点击 **Public Hostname** 标签，添加：

| Subdomain | Domain | Type | URL |
|-----------|--------|------|-----|
| (留空) | weibull.work | HTTP | frontend:3000 |
| api | weibull.work | HTTP | backend:8001 |

---

## 第二步：上传项目到 NAS

### 方法 A：SMB 共享（推荐）

1. NAS 开启 SMB 服务
2. 电脑访问 `\\你的NAS IP\共享文件夹`
3. 创建目录如 `docker/weibull`
4. 把整个项目文件夹复制进去

### 方法 B：SSH 上传

```bash
scp -r C:/Web/Weibull 用户名@NAS_IP:/volume1/docker/
```

---

## 第三步：启动容器

### 3.1 SSH 登录 NAS

```bash
ssh 用户名@NAS_IP
```

### 3.2 进入项目目录

```bash
cd /volume1/docker/weibull  # 路径根据实际情况调整
```

### 3.3 启动服务

**方式一：使用环境变量（推荐）**

```bash
# 设置 Tunnel Token
export CLOUDFLARE_TUNNEL_TOKEN="你的token"

# 启动
docker-compose up -d --build
```

**方式二：直接写在配置里**

编辑 `docker-compose.yml`，把 `${CLOUDFLARE_TUNNEL_TOKEN}` 替换成你的实际 token。

然后：
```bash
docker-compose up -d --build
```

### 3.4 检查状态

```bash
docker-compose ps
docker-compose logs -f
```

---

## 第四步：验证

访问 https://weibull.work，应该能看到网站了。

---

## 更新维护指南

### 日常更新流程

```
1. 本地修改代码
2. 重新上传项目到 NAS
3. SSH 登录 NAS，执行更新命令
```

### 更新命令

```bash
# SSH 登录 NAS 后
cd /volume1/docker/weibull

# 拉取新代码（如果用 git）
git pull

# 重新构建并启动
docker-compose up -d --build

# 查看日志确认
docker-compose logs -f
```

### 只更新前端

```bash
docker-compose up -d --build frontend
```

### 只更新后端

```bash
docker-compose up -d --build backend
```

### 查看运行状态

```bash
docker-compose ps
docker stats
```

### 查看日志

```bash
# 所有服务日志
docker-compose logs -f

# 只看前端
docker-compose logs -f frontend

# 只看后端
docker-compose logs -f backend
```

### 停止服务

```bash
docker-compose down
```

### 完全重新部署

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 常见问题

### Q: 前端无法连接后端？

检查后端是否正常运行：
```bash
curl http://localhost:8001/calculate -X POST -H "Content-Type: application/json" -d '{"method":"mle","data":[1,2,3]}'
```

### Q: Cloudflare Tunnel 连不上？

检查 cloudflared 容器日志：
```bash
docker-compose logs cloudflared
```

### Q: 构建失败？

检查磁盘空间：
```bash
df -h
```

清理 Docker 缓存：
```bash
docker system prune -a
```

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `Dockerfile.frontend` | Next.js 前端镜像 |
| `Dockerfile.backend` | Python 后端镜像 |
| `docker-compose.yml` | 容器编排配置 |
| `next.config.js` | Next.js 配置（standalone 模式） |
| `.dockerignore` | 构建时忽略的文件 |

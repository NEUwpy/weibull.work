# 绿联 NAS 部署指南

## 当前状态

- [x] 域名已购买：weibull.work
- [x] Cloudflare Tunnel 已配置
- [x] Docker 配置文件已创建
- [ ] 项目已上传到 NAS
- [ ] 容器已启动

---

## 第一步：上传项目到 NAS

### 方法 A：SMB 共享（在局域网下）

1. Windows 按 `Win + R`，输入 `\\192.168.31.148`
2. 输入 NAS 用户名密码
3. 创建文件夹 `docker/weibull`
4. 把整个 `C:\Web\Weibull` 文件夹内容复制进去

### 方法 B：NAS Web 界面上传

1. 登录 NAS 管理界面
2. 找到文件管理功能
3. 上传整个项目文件夹

---

## 第二步：SSH 登录 NAS

### 确保在同一局域网

电脑需要连接到和 NAS 相同的 WiFi/路由器。

### 登录命令

打开 PowerShell 或 CMD：

```bash
ssh WPY@192.168.31.148
```

如果端口不是 22，尝试：

```bash
ssh WPY@192.168.31.148 -p 端口号
```

### 可能遇到的问题

| 问题 | 解决方法 |
|------|---------|
| Connection timed out | 不在同一局域网，或 SSH 未开启 |
| Connection refused | 端口不对，检查 NAS SSH 设置 |
| Permission denied | 用户名或密码错误 |

---

## 第三步：找到项目目录

SSH 登录后，执行：

```bash
# 查看共享目录
ls /share/

# 查看卷
ls /volume1/

# 查找 docker-compose.yml 位置
find / -name "docker-compose.yml" 2>/dev/null
```

绿联 NAS 常见路径：
- `/share/`
- `/volume1/`
- `/mnt/`

找到后记住路径，比如 `/share/docker/weibull`

---

## 第四步：启动容器

```bash
# 进入项目目录（替换成实际路径）
cd /share/docker/weibull

# 启动所有服务（首次需要构建，可能需要几分钟）
docker-compose up -d --build

# 查看容器状态
docker-compose ps

# 查看日志（确认是否正常启动）
docker-compose logs -f
```

### 预期输出

```
NAME                  STATUS    PORTS
weibull-frontend      running   0.0.0.0:3000->3000/tcp
weibull-backend       running   0.0.0.0:8001->8001/tcp
weibull-cloudflared   running
```

按 `Ctrl + C` 退出日志查看。

---

## 第五步：验证部署

在浏览器访问：

- **前端**：https://weibull.work
- **后端 API**：https://api.weibull.work

如果能正常访问，部署成功！

---

## 日常更新维护

### 更新流程

```
1. 在本地电脑修改代码
2. 把更新后的文件上传到 NAS（覆盖）
3. SSH 登录 NAS
4. 重启容器
```

### 更新命令

```bash
# SSH 登录后
cd /share/docker/weibull

# 重新构建并启动
docker-compose up -d --build
```

### 只更新前端

```bash
docker-compose up -d --build frontend
```

### 只更新后端

```bash
docker-compose up -d --build backend
```

---

## 常用命令速查

| 命令 | 作用 |
|------|------|
| `docker-compose up -d --build` | 构建并启动所有服务 |
| `docker-compose ps` | 查看容器状态 |
| `docker-compose logs -f` | 查看实时日志 |
| `docker-compose logs -f frontend` | 只看前端日志 |
| `docker-compose logs -f backend` | 只看后端日志 |
| `docker-compose logs -f cloudflared` | 只看 Tunnel 日志 |
| `docker-compose restart` | 重启所有服务 |
| `docker-compose down` | 停止所有服务 |
| `docker-compose down && docker-compose up -d --build` | 完全重启 |

---

## 常见问题

### Q: 前端访问不了？

检查前端容器是否正常运行：
```bash
docker-compose logs frontend
```

### Q: 后端 API 报错？

检查后端容器：
```bash
docker-compose logs backend
```

手动测试后端：
```bash
curl http://localhost:8001/docs
```

### Q: Cloudflare Tunnel 连不上？

检查 cloudflared 日志：
```bash
docker-compose logs cloudflared
```

常见原因：
- Token 失效：重新获取 token 并更新 docker-compose.yml
- 网络问题：NAS 需要能访问外网

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

## 文件结构说明

上传到 NAS 的项目应该包含这些文件：

```
weibull/
├── docker-compose.yml      # 容器编排配置
├── Dockerfile.frontend     # 前端镜像
├── Dockerfile.backend      # 后端镜像
├── next.config.js          # Next.js 配置
├── .dockerignore           # 构建忽略文件
├── package.json            # 前端依赖
├── src/                    # 前端源码
├── public/                 # 静态资源
├── python/                 # 后端代码
│   ├── main.py
│   ├── requirements.txt
│   └── methods/
└── ...
```

---

## 联系方式

如有问题，检查：
1. Cloudflare Zero Trust 控制台：https://one.dash.cloudflare.com
2. NAS 管理界面：http://192.168.31.148

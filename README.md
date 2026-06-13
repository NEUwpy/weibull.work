# Weibull Analysis Platform

**威布尔参数估计方法的研究与实践平台**

集计算、对比、验证、优化于一体，并以案例数据库和学术文献库作为数据支撑与理论依据，为可靠性工程师和研究者提供从方法选型到结果验证的完整工作流。

**线上地址**: [weibull.work](https://weibull.work)

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 后端 | Python + FastAPI + SciPy/NumPy |
| 部署 | Docker + Cloudflare Tunnel |
| 托管 | 绿联 NAS（无公网 IP） |

## 架构

```
用户 → Cloudflare CDN → Tunnel → NAS Docker
                                    ├── frontend:3000 (Next.js)
                                    └── backend:8001 (FastAPI)
```

## 核心模块

1. **Calculator (计算器)** - 交互式参数估计，支持多方法对比
2. **Methods (方法系统)** - 25+ 种参数估计方法的详细文档与可视化
3. **Case Database (案例库)** - 科研文献中的标准失效数据集
4. **Library (图书馆)** - Markdown 文献阅读

## 快速开始

### 启动后端 (Python API)
```bash
cd python
pip install -r requirements.txt
python main.py
# http://localhost:8001
```

### 启动前端 (Next.js)
```bash
npm install
npm run dev
# http://localhost:3000
```

## 代码位置

| 模块 | 路径 |
|------|------|
| 核心算法 | `python/methods/*.py` |
| API 接口 | `python/main.py` |
| 前端页面 | `src/app/` |
| UI 组件 | `src/components/` |

---

AI 助手请先阅读 `AGENTS.md`。

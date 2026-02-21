# Weibull Analysis Platform (威布尔分析平台) v7.0

一个集计算工具、数据管理与科研文献于一体的现代化可靠性工程平台。

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

## 🌟 核心模块

1.  **Calculator (计算器)**: 
    *   交互式卡片流设计，支持多维度对比分析。
    *   **后端计算**: 基于 Python (SciPy/NumPy) 的高精度参数估计。
    *   **前端可视化**: 基于 D3/Recharts 的实时交互图表。
2.  **Methods (方法系统)**:
    *   25+ 种参数估计方法的详细文档。
    *   **透明化视图**: 独创的代码执行流程可视化，逐行展示算法逻辑。
3.  **Case Database (案例库)**:
    *   从科研文献中提取的标准失效数据集。
    *   一键导入计算器进行验证与对比。
4.  **Library (图书馆)**:
    *   基于 Markdown 的沉浸式文献阅读体验。

## 🚀 快速开始

### 1. 启动后端 (Python API)
负责核心算法计算。
```bash
cd python
pip install -r requirements.txt
python main.py
# 服务启动在 http://localhost:8001
```

### 2. 启动前端 (Next.js)
负责界面展示与交互。
```bash
npm install
npm run dev
# 访问 http://localhost:3000
```

## 📚 文档导航

- **[部署与维护指南 (docs/部署与维护指南.md)](docs/部署与维护指南.md)**: NAS + Cloudflare Tunnel 部署流程及日常维护。
- **[架构与实现 (ARCHITECTURE.md)](ARCHITECTURE.md)**: 技术架构、数据流向、目录规范。（**开发者必读**）
- **[需求与规划 (REQUIREMENTS.md)](REQUIREMENTS.md)**: 项目路线图、待办事项。

---

## 🤖 For AI Assistants (AI 助手指南)

如果你是维护本项目的 AI 助手，请务必遵循以下索引进行上下文加载：

1.  **核心架构**: 必须优先读取 **[`ARCHITECTURE.md`](ARCHITECTURE.md)**，这是理解本项目“前后端分离”与“Markdown 数据源”规则的唯一真理来源。
2.  **代码索引**: 
    - **核心算法**: `python/methods/*.py` (所有统计计算逻辑)
    - **API 接口**: `python/main.py`
    - **前端页面**: `src/app/`
    - **通用组件**: `src/components/`
3.  **禁区**: 
    - 严禁读取 `_archive/` 目录下的任何内容（包含废弃脚本与旧数据）。
    - 严禁将重型计算逻辑写入前端 TypeScript 文件。

## ⚖️ License
MIT License

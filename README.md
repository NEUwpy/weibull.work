# Weibull Analysis Platform (威布尔分析平台) v7.0

一个集计算工具、数据管理与科研文献于一体的现代化可靠性工程平台。

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

- **[架构与实现 (ARCHITECTURE.md)](ARCHITECTURE.md)**: 了解系统的技术架构、数据流向、目录规范及开发规则。（**开发者必读**）
- **[需求与规划 (REQUIREMENTS.md)](REQUIREMENTS.md)**: 查看项目路线图、待办事项及功能需求。

## ⚖️ License
MIT License
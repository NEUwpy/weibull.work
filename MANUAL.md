# 威布尔分析平台 (Weibull Analysis Platform) - 开发者手册

> **文档状态**: 2026-01-20 归档 (v0.2.0 Stable)
> **适用对象**: 维护本项目的开发者或 AI 助手。

---

## 1. 项目概况 (Overview)
- **定位**: 博士级可靠性工程科研平台。
- **架构**: 
    - **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind.
    - **Backend**: Python FastAPI + NumPy + SciPy (采用模块化解耦架构).
- **三大核心模块**:
    1. **计算工具 (Calculator)**: 主页路由 `/`。
    2. **案例数据库 (Case Database)**: 路由 `/cases`，JSON 驱动。
    3. **电子图书馆 (Library)**: 路由 `/library`，Markdown 驱动。

---

## 2. 内容管理 (Content Management)

本项目采用 **“文件即数据库”** 的设计理念，所有业务数据均由静态文件驱动：

- **算法定义**: `src/data/methods.json`
    - 定义算法的名称、描述、LaTeX 公式、关联文献 slug。
- **案例数据**: `src/data/cases.json`
    - 存储结构化的失效数据、行业、标签及关联文献。
- **文献内容**: `src/content/*.md`
    - 存放 Markdown 格式的文献笔记，系统自动扫描并渲染。

---

## 3. 技术实现细节 (Implementation Details)

### 3.1 后端模块化架构 (Python)
后端代码位于 `python/` 目录，已实现高度解耦：
- **`main.py`**: 入口调度器，负责 API 路由和算法映射。
- **`base.py`**: 基类 `WeibullBase`，提供数据初始化、中位秩计算、R方计算等通用数学工具。
- **`methods/`**: 算法库目录。每个算法独立为一个文件（如 `mle.py`, `lre.py`），通过继承 `WeibullBase` 并实现 `run()` 方法来工作。

### 3.2 界面规范 (Styling)
- **字号体系**: 以 16px/14px/12px 为阶梯。
- **对齐逻辑**: 所有卡片容器宽度通过 `max-w-[95%] xl:max-w-[1800px]` 配合 `pl-[4.5rem] pr-[4rem]` 强制与 Header 边缘对齐。
- **渲染引擎**: 
    - 使用 `react-markdown` + `rehype-katex` 解析公式。
    - 增加了 `normalizedContent` 预处理逻辑，自动修复 LaTeX 换行符问题。

---

## 4. 如何添加新算法 (Adding New Methods)

1. **前端显示**: 在 `src/data/methods.json` 中添加一个条目，分配唯一的 `id`。
2. **后端逻辑**: 
    - 在 `python/methods/` 下新建 `your_id.py`。
    - 继承 `WeibullBase` 并重写 `run()`。
3. **注册连接**: 在 `python/main.py` 的 `method_map` 字典中注册该 `id` 对应的类。

---

**运行口令**:
1. 启动前端: `npm run dev`
2. 启动后端: `cd python && python main.py`
3. 查阅规范: `src/data/README.md` (案例) 和 `src/content/README.md` (文献)。

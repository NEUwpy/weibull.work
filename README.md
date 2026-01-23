# 威布尔分析平台 (Weibull Analysis Platform)

一个集计算工具、数据管理与科研文献于一体的现代化可靠性工程平台。

## 🚀 核心模块 (Core Modules)

### 1. 计算工具 (Calculator)
- **功能**: 参数估计、分布拟合、蒙特卡洛模拟。
- **算法**: 支持 MLE, LRE, EM 等多种估计算法。
- **交互**: 基于卡片流 (Card Flow) 的对比分析界面。

### 2. 案例数据库 (Case Database)
- **功能**: 标准失效数据的存储与检索。
- **特点**: 支持行业筛选、样本大小分类，并可一键导入计算器进行分析。
- **数据源**: `src/data/cases.json` (JSON 文件驱动，易于扩展)。

### 3. 电子图书馆 (Electronic Library)
- **功能**: 可靠性工程文献的沉浸式阅读。
- **特点**: 支持 LaTeX 公式渲染、双向引用链接、侧边目录导航。
- **数据源**: `src/content/*.md` (Markdown 文件驱动)。

---

## 🛠️ 内容管理指南 (Content Management)

本平台采用“文件即数据库”的设计理念，无需操作复杂的数据库即可更新内容。

### 添加案��数据
1. 打开 `src/data/cases.json`。
2. 按照现有格式添加新的 JSON 对象。
3. 保存文件，网页自动更新。
*详细规范请查阅: [`src/data/README.md`](src/data/README.md)*

### 添加文献文章
1. 将 Markdown (`.md`) 文件放入 `src/content/` 目录。
2. 确保文件头部包含标准 Frontmatter (标题、作者等)。
3. 如有图片，存入 `public/assets/` 并在文中引用。
*详细规范请查阅: [`src/content/README.md`](src/content/README.md)*

---

## 💻 开发与部署

### 本地运行
```bash
npm install
npm run dev
```
访问 `http://localhost:3000`

### 构建生产版本
```bash
npm run build
npm start
```

### 技术栈
- **框架**: Next.js 14 (App Router)
- **语言**: TypeScript
- **样式**: Tailwind CSS
- **渲染**: React Markdown, KaTeX (公式), Rehype (HTML处理)
- **图标**: Lucide React

---

## 📄 许可证
MIT License

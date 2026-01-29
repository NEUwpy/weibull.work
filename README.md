# 威布尔分析平台 (Weibull Analysis Platform)

一个集计算工具、数据管理与科研文献于一体的现代化可靠性工程平台。

## 🚀 核心模块 (Core Modules)

### 1. 计算工具 (Calculator)
- **功能**: 参数估计、分布拟合、蒙特卡洛模拟。
- **算法**: 支持 MLE, LRE, EM 等多种估计算法。
- **交互**: 基于卡片流 (Card Flow) 的对比分析界面。

### 2. 参数估计方法系统 (Parameter Estimation Methods)
- **功能**: 8 大类别，25+ 算法的详细介绍与文档。
- **亮点算法**:
  - **WMLE (加权极大似然)**: 解决小样本下 MLE 的偏差问题。
  - **MDM (最小偏差法)**: *[New]* 基于统计最小差异原理和梯度偏移判据，显著提高工程小样本估计的稳健性。
- **特点**:
  - 基于 Markdown + Frontmatter 的标准化文档架构
  - 支持 Mermaid 流程图、LaTeX 公式、变量说明表格
  - 适用场景、相关文献一键查看
- **数据源**: `src/content/algorithms/*.md` (MD 文件驱动) + `src/data/methods.json`

### 3. 案例数据库 (Case Database)
- **功能**: 标准失效数据的存储与检索。
- **特点**: 支持行业筛选、样本大小分类，并可一键导入计算器进行分析。
- **数据源**: `src/data/cases.json` (JSON 文件驱动，易于扩展)。

### 4. 电子图书馆 (Electronic Library)
- **功能**: 可靠性工程文献的沉浸式阅读。
- **特点**: 支持 LaTeX 公式渲染、双向引用链接、侧边目录导航。
- **数据源**: `src/content/*.md` (Markdown 文件驱动)。

---

## 🛠️ 内容管理指南 (Content Management)

本平台采用"文件即数据库"的设计理念，无需操作复杂的数据库即可更新内容。

### 添加算法文档
1. 复制 `src/content/algorithms/_template.md` 创建新的算法文档。
2. 填写 Frontmatter（公式、描述、变量、流程图、适用场景、文献）。
3. 在 `src/data/methods.json` 中添加 `slug` 和 `hasDetail: true`。
4. （可选）在 `python/` 目录下创建对应的 Python 实现文件。
*详细规范请查阅: [`REQUIREMENTS.md`](REQUIREMENTS.md)*

### 添加案例数据
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
- **渲染**: React Markdown, KaTeX (公式), Rehype (HTML处理), Mermaid (流程图)
- **图标**: Lucide React

---

## 📋 后续计划 (Roadmap)

- [ ] 为所有 25+ 算法创建完整的 MD 文档和 Python 实现
- [ ] 集成 Python 算法到计算器后端
- [ ] 添加文献图片放大功能 (Lightbox)
- [ ] 扩展案例数据库详情页

*完整开发计划请查阅: [`REQUIREMENTS.md`](REQUIREMENTS.md)*

---

## 📄 许可证
MIT License

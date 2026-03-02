# Architecture & Technical Specifications (架构与技术规格)

本文档定义了 Weibull Analysis Platform 的技术架构、模块边界及开发规范。

---

## 1. 核心架构与职责边界 (System Boundaries)

系统采用 **Python (Backend) + Next.js (Frontend)** 的分离架构。

### 1.1 后端 (Python / FastAPI)
*   **职责**: 承担所有统计学核心计算。
    *   参数估计 (MLE, LRE, MDM, etc.)
    *   拟合优度计算 (R², Log-Likelihood)
    *   数值优化 (Hessian 矩阵, Nelder-Mead 迭代)
*   **入口**: `python/main.py` (Port: 8001)
*   **规范**: 任何涉及统计推断的逻辑严禁在前端实现。

### 1.2 前端 (TypeScript / Next.js)
*   **职责**: UI 交互、数据展示、图表渲染。
    *   **绘图**: 接收后端返回的分布参数 (β, η, γ)，生成 PDF/CDF 曲线坐标点。
    *   **交互**: 管理用户输入的原始数据，调用后端 API。
*   **入口**: `src/app/page.tsx` (Port: 3000)
*   **例外**: `src/lib/weibull.ts` 仅保留用于绘图平滑处理的数学函数（如 `generatePDFPoints`），不作为计算依据。

---

## 2. 数据层架构 (Data Persistence)

系统不使用传统关系型数据库，采用 **Git-Based Flat File** 存储策略。

### 2.1 数据源映射
| 数据类型 | 存储格式 | 存储路径 | 读取方式 |
| :--- | :--- | :--- | :--- |
| **案例配置 (Cases)** | Markdown + YAML | `public/cases/[methodId]_caseX.md` | API: `/api/cases/[methodId]` 解析 front matter |
| **案例数据 (CSV)** | CSV | `public/cases/[methodId]_caseX_full.csv` | 前端直接 fetch 读取 |
| **算法文档 (Algorithms)** | Markdown | `src/content/algorithms/*.md` | 标准 Markdown 渲染 |
| **算法流程 (Flows)** | JSON | `src/data/method_flows/*.json` | 精确映射 UI 步骤与 Python 代码行 |
| **文献 (Library)** | Markdown | `src/content/*.md` | 解析引用关系与 LaTeX 公式 |

### 2.2 索引机制
*   目前算法的分类层级（树状结构）仍依赖 `src/data/methods.json` 作为静态索引。
*   案例列表通过遍历文件名动态生成。

---

## 3. 系统交互链路 (Interaction Flow)

### 3.1 计算请求 (Calculation Request)
1.  **Frontend**: 用户在 UI 输入数据，点击计算。
2.  **API Call**: `POST http://localhost:8001/calculate`
    ```json
    { "method": "mle", "data": [100, 120, ...], "trace": true }
    ```
3.  **Backend Dispatch**: `python/main.py` 根据 `method` 字符串（如 "mle"）映射到 `methods/mle.py` 类。
4.  **Computation**: 执行 `run()` 方法进行数值迭代。
5.  **Response**:
    ```json
    { "beta": 2.5, "eta": 100, "gamma": 0, "rSquared": 0.98, "converged": true }
    ```

---

## 4. 目录结构规范 (Directory Manifest)

```text
/
├── _archive/             # [忽略] 归档的废弃文件与脚本
├── python/               # [后端]
│   ├── main.py           # API 路由入口
│   └── methods/          # 算法的具体实现类 (继承自 BaseMethod)
├── src/                  # [前端]
│   ├── app/              # Next.js 页面逻辑
│   ├── components/       # UI 组件 (AnalysisCard, Visualizers)
│   ├── content/          # [数据源] Markdown 内容库
│   │   ├── algorithms/   # 算法原理
│   │   └── cases/        # 案例数据
│   ├── data/             # [配置] 结构化配置 (methods.json, flows)
│   └── lib/              # 工具函数 (weibull.ts: 绘图用; cases_md.ts: IO用)
└── ARCHITECTURE.md       # [文档] 架构说明
```

---

## 5. 扩展开发指南 (Extension Guide)

### 5.1 添加新算法
1.  **实现类**: 在 `python/methods/` 创建 `.py` 文件，实现参数估计逻辑。
2.  **注册**: 在 `python/main.py` 的 `method_map` 字典中添加映射。
3.  **文档**: 在 `src/content/algorithms/` 添加对应的 `.md` 说明文件。

### 5.2 添加新案例
1.  在 `src/content/cases/` 新建 `.md` 文件。
2.  必须包含 `data_raw` (换行分隔的数据) 和基础元数据 (title, industry)。

### 5.3 案例展示 (Case Study) 功能

案例展示是将预计算的参数研究/模拟实验数据进行可视化的功能，避免用户每次访问都需要重新计算。

**位置**: 方法详情页 → 第5个标签页 "案例展示"

#### 架构说明

```
/methods/mdm
  → Tab: 概述 | 流程 | 实验室 | 分析 | 案例展示
                                      ↓
                              CaseStudyViewer 组件
                                      ↓
                   ┌─────────────────────────────────┐
                   │  useCaseList() Hook             │
                   │  → GET /api/case-studies/mdm    │
                   │  → 自动扫描 case* 目录           │
                   │  → 返回案例列表                  │
                   └─────────────────────────────────┘
                                      ↓
                              下拉框动态渲染
```

**关键文件**:

| 文件 | 作用 |
|------|------|
| `src/hooks/useCaseList.ts` | 共享 Hook，获取案例列表 |
| `src/app/api/case-studies/mdm/route.ts` | API 路由，自动扫描目录 |
| `src/components/CaseStudyViewer.tsx` | 主组件，架构分发 |
| `src/components/case-studies/mdm/caseX/CaseXViewer.tsx` | 各案例专用组件 |

**数据位置**: `public/case-studies/mdm/caseX/`
- `config.md` - YAML 配置 + Markdown 描述（必需）
- `data.json` - 模拟数据

#### 案例自动发现机制

**API 自动扫描** - 无需手动维护案例列表：
- 扫描 `public/case-studies/mdm/` 下所有 `case*` 目录
- 读取每个目录的 `config.md` 获取案例信息
- 按案例编号排序返回

**下拉列表自动更新** - 所有案例组件使用共享 Hook：
```tsx
import { useCaseList } from '@/hooks/useCaseList'

// 在组件中
const { cases: caseList } = useCaseList()

// 渲染下拉列表
{caseList.map(c => (
  <option key={c.id} value={c.id}>{c.name}</option>
))}
```

#### 案例分类

| 类型 | architecture | 渲染方式 |
|------|-------------|----------|
| 常规案例 | `normal` | CaseStudyViewer 内置渲染 |
| Markdown | `markdown` | 纯文档展示 |
| 特殊案例 | `case5`, `case6`, ... | 专用组件 |

#### 添加新案例（3步）

**1. 创建目录和配置**
```bash
mkdir public/case-studies/mdm/case17
```

创建 `config.md`:
```yaml
---
id: "case-17"
name: "案例17: 标题"
description: "案例描述"
architecture: "case17"  # 特殊架构用 caseN，常规用 normal
csvFile: "/case-studies/mdm/case17/data.json"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
true_params:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSizes: [3, 5, 7, 10]
params:
  - id: "sample_size"
    name: "样本量"
    symbol: "n"
    state: "discrete"
    discreteValues: [3, 5, 7, 10]
    isVariable: true
    isDisplayDimension: true
---

## 案例17: 标题

### 研究目的
...
```

**2. 创建数据文件**
- Python 脚本: `python/mdm/case_studies/case17/generate_data.py`
- 输出数据: `public/case-studies/mdm/case17/data.json`

**3. 注册组件（仅特殊架构需要）**

在 `CaseStudyViewer.tsx` 中：
```tsx
// 1. 添加 dynamic import
const Case17Viewer = dynamic(() => import('./case-studies/mdm/case17/Case17Viewer'), {
  ssr: false,
  loading: () => <LoadingSpinner name="案例17" />
})

// 2. 在 componentMap 中添加
'17': Case17Viewer,

// 3. 在 architecture 类型中添加 'case17'
```

**注意**: 常规架构 (`normal`) 只需步骤 1-2，API 会自动发现，下拉列表会自动更新。

#### 现有案例列表

| 案例 | 名称 | 架构 |
|------|------|------|
| case3 | 无交点梯度曲线 | no_intersection |
| case4 | 新MDM算法多维度研究 | normal |
| case5 | 30组实际样本分析 | case5 |
| case6-9 | 步长/搜索方式研究 | case6-9 |
| case13 | 中位秩方法对比 | case13 |
| case14 | MDM vs WMLE 对比 | case14 |
| case15 | WMLE 权重 MC 验证 | case15 |
| case16 | WMLE 极小样本失效 | case16 |

### 5.4 维护注意事项
*   **禁止硬编码**: 不要将数据直接写在 TS/JS 文件中。
*   **双重验证**: 修改 Python 算法后，需同时检查前端可视化组件（`visualizers/`）是否兼容返回的数据结构。

### 5.5 方法示例系统 (UniversalStudyViewer)

**位置**: 方法详情页 → "方法示例" Tab

**设计理念**: 插槽模式 - 框架 + 可复用图表组件

```
src/components/studies/
├── UniversalStudyViewer.tsx    # 框架（布局 + 表格 + 组合逻辑）
└── charts/                     # 可复用图表组件
    ├── ChartCard.tsx           # 统一卡片容器
    ├── BoxPlotChart.tsx        # 箱型图
    └── HeatmapChart.tsx        # 热力图
```

**核心原则**:

| 原则 | 说明 |
|------|------|
| 统一复用 | 相同结构不差异化（布局、样式、标题格式） |
| 配置驱动 | 图题、图表类型从 config.md 加载 |
| 插槽组合 | ChartCard(容器) + 图表组件(children) |
| 职责分离 | 框架=布局，图表=内容，容器=样式 |

**添加新图表**:
1. 在 `charts/` 创建组件（只输出图表内容，不包含外框）
2. 用 `ChartCard` 包裹使用:
   ```tsx
   <ChartCard title="图 N: 标题">
     <NewChart data={...} />
   </ChartCard>
   ```

详见: `docs/方法示例系统重构方案.md`

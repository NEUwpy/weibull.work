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
| **案例数据 (Cases)** | Markdown | `src/content/cases/*.md` | 解析 Frontmatter 中的 `data_raw` 字段 |
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

### 5.3 维护注意事项
*   **禁止硬编码**: 不要将数据直接写在 TS/JS 文件中。
*   **双重验证**: 修改 Python 算法后，需同时检查前端可视化组件（`visualizers/`）是否兼容返回的数据结构。

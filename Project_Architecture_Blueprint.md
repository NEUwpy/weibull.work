# Weibull Analysis Platform - 项目架构蓝图

> 生成时间: 2026-04-01 | 版本: v7.0

---

## 1. 架构概览

### 1.1 系统定位

威布尔参数估计方法的研究与实践平台，面向可靠性工程师和研究者。集计算、对比、验证、优化于一体，以案例数据库和学术文献库作为数据支撑。

### 1.2 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端框架 | Next.js (App Router) | 14.1.0 |
| UI 语言 | TypeScript + React | TS 5.3 / React 18 |
| 样式方案 | Tailwind CSS + clsx + tailwind-merge | 3.4 |
| 图表渲染 | Plotly.js + Recharts | - |
| 数学公式 | KaTeX (LaTeX 渲染) | 0.16 |
| 内容渲染 | react-markdown + remark/rehype 插件链 | - |
| 后端框架 | Python + FastAPI + Uvicorn | - |
| 数值计算 | SciPy + NumPy | - |
| 部署方案 | Docker Compose + Cloudflare Tunnel → 绿联 NAS | - |
| 数据存储 | Git-Based Flat File (Markdown / CSV / JSON) | 无数据库 |

### 1.3 架构模式

**前后端分离 + 静态文件数据层**：
- 前端：Next.js App Router（SSR + CSR 混合）
- 后端：FastAPI 单体服务，专注统计计算
- 数据层：无数据库，所有数据以文件形式存储在 Git 仓库中

### 1.4 部署架构

```
用户浏览器
    ↓ HTTPS
Cloudflare CDN
    ↓ Tunnel
绿联 NAS (Docker Compose)
    ├── frontend:3000  (Next.js production build)
    ├── backend:8001   (FastAPI + Uvicorn)
    └── cloudflared    (Cloudflare Tunnel agent)
```

---

## 2. 核心模块

### 2.1 Calculator（威布尔计算器）

**目的**：交互式参数估计，支持多方法对比。

**入口**：`src/app/page.tsx`

**架构特征**：
- **卡片式布局**：每个计算实例是一张 `AnalysisCard`，支持叠加对比
- **多方法选择**：通过 `MethodSelector` 弹窗选择 25+ 种方法
- **数据输入**：`DataEditor` 支持手动输入和从案例库调用
- **多曲线模式**：`DataSource` 类型支持同一图表上叠加多条分布曲线

**数据流**：
```
用户输入数据 → DataEditor → page.tsx (state管理)
    ↓ POST /calculate
后端 FastAPI → 方法类实例.run() → 返回 β, η, γ, R²
    ↓
前端绘制 PDF/CDF 曲线 (Plotly.js)
```

**关键组件**：
| 组件 | 路径 | 职责 |
|------|------|------|
| `AnalysisCard` | `src/components/calculator/AnalysisCard.tsx` | 单个计算卡片，集成图表+参数+控制 |
| `MethodSelector` | `src/components/calculator/MethodSelector.tsx` | 方法选择弹窗 |
| `DataEditor` | `src/components/calculator/DataEditor.tsx` | 数据编辑器 |

### 2.2 Methods（方法系统）

**目的**：展示参数估计方法的原理与实现，验证方法的正确性与适用范围。

**入口**：`src/app/methods/page.tsx`（列表页）→ `src/app/methods/[methodId]/page.tsx`（详情页）

**方法分类**（8大类，25+方法）：
```
methods.json 树状结构
├── 极大化适配法 (MaxAdq)  → MLE, MMLE, MPS, WMLE
├── 极小化适配法 (MinAdq)  → LSE, WLSE, MDM, EIV
├── 线性回归法 (LRE)       → LRE, BLRE
├── 矩方法 (Moments)       → MM, PWM, LM, TLM
├── 灰色估计法 (Grey)      → GM(1,1)
├── 构造统计量法 (ConstStat) → MVE, LSF
├── 贝叶斯方法 (Bayes)     → Gibbs, MAP
└── 人工智能方法 (AI)      → PSO, SVR, ANN
```

**方法详情页 Tab 结构**：

| Tab | 组件 | 数据来源 | 计算时机 |
|-----|------|---------|---------|
| 原理文档 | `AlgorithmDetail` | `src/content/algorithms/*.md` | 静态 |
| 程序流程 | `VariableFlowViewer` | `src/data/method_flows/*.json` | 静态 |
| 计算过程 | `{Method}Visualizer` | 后端 API trace_data | 现场计算 |
| 结果分析 | `ResultAnalysisLab` | 后端 API | 现场计算 |
| 适用范围 | `GenericStudyViewer` | `public/studies/{method}/chunks/*.csv` | 预计算 |
| 可信性验证 | `CaseStudyViewer` / `VerificationItem` | 定制组件 | 预计算 |
| 方法对比 | `MethodCompareViewer` | 后端 API | 现场计算 |

**方法组件目录规范**：
```
src/components/methods/{method}/
├── index.ts                 # 导出
├── visualizers/             # 计算过程可视化
│   └── {Method}Visualizer.tsx
├── charts/                  # 方法专用图表
└── case-studies/            # 可信性验证
    └── caseRegistry.tsx
```

**共享组件**（`src/components/methods/shared/`）：
- `studies/GenericStudyViewer`：统一的适用范围分析组件，所有方法共用
- `compare/MethodCompareViewer`：方法横向对比
- `verification/`：可信性验证统一类型和组件

### 2.3 Cases（案例数据库）

**目的**：存储标准失效数据集。

**入口**：`src/app/cases/page.tsx`

**数据结构**：
- 案例配置：`public/cases/{methodId}_caseX.md`（Markdown + YAML front matter）
- 案例数据：`public/cases/{methodId}_caseX_full.csv`
- 案例组：支持多案例分组展示

**API 路由**：
```
/api/cases          → 获取所有案例列表
/api/cases/[id]     → 获取单个案例详情
/api/cases/tree     → 获取案例树形结构
/api/cases/groups   → 获取案例分组
```

### 2.4 Library（可靠性图书馆）

**目的**：管理与阅读学术文献。

**入口**：`src/app/library/page.tsx` → `src/app/library/[slug]/page.tsx`

**功能**：
- Markdown 文献阅读（`src/content/*.md`）
- 双语切换（原文/翻译）
- 参考文献跳转
- 与方法/案例的双向链接

---

## 3. 数据架构

### 3.1 存储策略

无数据库，全部使用 Git 管理的静态文件：

| 数据类型 | 格式 | 路径 | 读取方式 |
|----------|------|------|---------|
| 方法分类索引 | JSON | `src/data/methods.json` | 前端 import |
| 方法流程定义 | JSON | `src/data/method_flows/*.json` | API route 读取 |
| 算法原理文档 | Markdown | `src/content/algorithms/*.md` | API route 读取 |
| 案例配置 | MD + YAML | `public/cases/*.md` | API route 解析 front matter |
| 案例数据 | CSV | `public/cases/*_full.csv` | 前端 fetch |
| 模拟分片数据 | CSV | `public/studies/{method}/chunks/*.csv` | 前端 fetch |
| 文献 | Markdown | `src/content/*.md` | API route 读取 |
| 文献图片 | 图片文件 | `public/{ID}-图片/` | 静态资源 |

### 3.2 分片文件命名规范

适用范围的蒙特卡洛模拟数据采用分片存储：

```
通用格式: b{beta}_e{eta}_g{gamma}_n{n}_rep{rep}_seed{seed}_step{step}.csv
MDM格式: b{beta}_e{eta}_g{gamma}_n{n}_d{d}_rep{rep}_seed{seed}_step{step}.csv
```

### 3.3 索引机制

- 方法分类层级：`src/data/methods.json` 静态索引（树状结构）
- 案例列表：通过文件名遍历动态生成（API route 解析）
- 文献列表：类似案例，动态扫描

---

## 4. 后端架构

### 4.1 API 入口

**文件**：`python/main.py`，运行在端口 8001。

### 4.2 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/calculate` | POST | 单次参数估计 |
| `/calculate_3d_surface` | POST | MDM 3D 曲面计算 |
| `/batch_simulation` | POST | 批量蒙特卡洛模拟（返回 CSV） |
| `/monte_carlo_simulate` | POST | 蒙特卡洛模拟（返回 JSON） |

### 4.3 算法实现架构

**基类契约**（`python/_template.py`）：
```python
def estimate(data: List[float], **kwargs) -> Dict[str, Any]:
    """返回 {beta, eta, gamma, success, message, iterations}"""
```

**实际实现**（类模式）：
```python
class MDM:
    def __init__(self, data): ...
    def run(self, trace=False, offset=None) -> tuple:
        """返回 (beta, eta, gamma, rSquared, converged)"""
```

**方法注册**（`main.py` method_map）：
```python
method_map = {
    "mle": MLE, "mmle": MMLE, "mdm": MDM, "wmle": WMLE,
    "lre": LRE, "lse": LSE, "mm": MM, "pwm": PWM,
    "grey": GreyGM11, "bayesian": Bayesian, ...
    # 别名映射：rrx→LRE, mde→MDM, gibbs→Bayesian 等
}
```

**已实现的算法**（`python/methods/`）：

| 文件 | 类 | 方法 |
|------|-----|------|
| `mle.py` | `MLE` | 极大似然估计 |
| `mmle.py` | `MMLE` | 修正极大似然估计 |
| `wmle.py` | `WMLE` | 加权极大似然 |
| `mdm.py` | `MDM` | 最小差异法 |
| `lre.py` | `LRE` | 线性回归 |
| `lse.py` | `LSE` | 最小二乘 |
| `mm.py` | `MM` | 矩估计 |
| `pwm.py` | `PWM` | 概率加权矩 |
| `mps.py` | `MPS` | 最大乘积间距 |
| `bayesian.py` | `Bayesian` | 贝叶斯方法 |
| `grey_gm11.py` | `GreyGM11` | 灰色 GM(1,1) |

### 4.4 容错策略

- 计算失败时自动降级到 WMLE（fallback）
- 支持 `converged` 字段返回 `"unbounded"` 等特殊状态
- 双层 try-except 包裹（方法失败 → WMLE 降级 → HTTP 错误）

---

## 5. 前端架构

### 5.1 路由结构

```
src/app/
├── layout.tsx                      # 全局布局（Header + 导航）
├── page.tsx                        # 计算器首页 (/)
├── not-found.tsx                   # 404 页面
├── globals.css                     # 全局样式
├── methods/
│   ├── page.tsx                    # 方法列表 (/methods)
│   └── [methodId]/page.tsx         # 方法详情 (/methods/:id)
├── cases/
│   ├── page.tsx                    # 案例列表 (/cases)
│   ├── [caseId]/page.tsx           # 案例详情 (/cases/:id)
│   └── groups/[groupId]/...        # 案例分组
├── library/
│   ├── page.tsx                    # 文献列表 (/library)
│   └── [slug]/page.tsx             # 文献阅读 (/library/:slug)
└── api/                            # Next.js API Routes (BFF 层)
    ├── algorithms/route.ts         # 算法文档 API
    ├── cases/                      # 案例 API
    ├── case-studies/mdm/           # 可信性验证 API
    ├── chat/route.ts               # AI 对话 API
    ├── content/route.ts            # 内容 API
    ├── method-flow/[methodId]/     # 方法流程 API
    └── studies/                    # 适用范围数据 API
```

### 5.2 组件架构

```
src/components/
├── calculator/                     # 计算器模块
│   ├── AnalysisCard.tsx            # 分析卡片（核心容器组件）
│   ├── DataEditor.tsx              # 数据编辑器
│   └── MethodSelector.tsx          # 方法选择器
├── methods/                        # 方法模块
│   ├── MethodDetailContent.tsx     # 方法详情内容（共享）
│   ├── AlgorithmDetail.tsx         # 算法文档渲染
│   ├── VariableFlowViewer.tsx      # 程序流程可视化
│   ├── ResultAnalysisLab.tsx       # 结果分析实验室
│   ├── CaseStudyViewer.tsx         # 可信性验证容器
│   ├── {method}/                   # 各方法专属组件
│   │   ├── mdm/                    # MDM（最完善的方法）
│   │   │   ├── visualizers/        # 4个可视化组件
│   │   │   ├── charts/             # 专用图表
│   │   │   └── case-studies/       # 验证案例
│   │   ├── mle/
│   │   └── wmle/
│   └── shared/                     # 跨方法共享组件
│       ├── studies/                # GenericStudyViewer（统一适用范围）
│       ├── compare/                # 方法对比
│       └── verification/           # 可信性验证
├── library/                        # 图书馆模块
│   └── LibraryPageClient.tsx
├── shared/                         # 全局共享组件
│   ├── charts/                     # 图表组件库（7种）
│   │   ├── BoxPlotChart.tsx        # 箱型图
│   │   ├── HeatmapChart.tsx        # 热力图
│   │   ├── DensityChart.tsx        # 密度图
│   │   ├── ConvergenceChart.tsx    # 收敛图
│   │   ├── ContourChart.tsx        # 等高线图
│   │   ├── ChartCard.tsx           # 图表卡片容器
│   │   └── ObjectiveSurface3D.tsx  # 3D 目标函数曲面
│   ├── ParamSelector.tsx           # 参数选择器
│   └── SimulationConfigPanel.tsx   # 模拟配置面板
└── chat/                           # AI 对话模块
    └── ChatDialog.tsx
```

### 5.3 状态管理

- **无全局状态库**：不使用 Redux / Zustand / Jotai
- **组件内 useState**：每个页面组件管理自己的状态
- **数据流**：通过 props 传递，回调函数通信
- **URL 参数**：计算器支持 `?caseId=xxx` 从案例跳转

### 5.4 数据获取模式

| 场景 | 方式 | 说明 |
|------|------|------|
| 后端计算 | `fetch POST` → FastAPI | 参数估计、蒙特卡洛模拟 |
| 静态 CSV | `fetch GET` → public 目录 | 预计算的分片数据 |
| 内容文件 | Next.js API Route 读取 | Markdown 文档、方法流程 |
| 配置数据 | 直接 import | `methods.json`、`methods.ts` |

### 5.5 关键设计模式

1. **统一组件模式**：`GenericStudyViewer` 通过参数化配置（`methodId`, `extraParamDefs`）服务所有方法的适用范围分析
2. **Dynamic Import**：重型可视化组件使用 `next/dynamic` 懒加载
3. **卡片组合模式**：计算器通过 `CardData` 类型实现灵活的卡片叠加对比
4. **方法注册表模式**：`method_map` 字典将方法 ID 映射到实现类，支持别名
5. **降级容错**：后端计算失败自动降级到 WMLE

---

## 6. 跨层关注点

### 6.1 数据验证

- **后端**：Pydantic 模型（`CalculationRequest`, `MonteCarloRequest`）
- **前端**：最小数据量检查（< 2 报错），收敛状态检查

### 6.2 错误处理

- 后端：双层 try-except，WMLE fallback
- 前端：try-catch 包裹 API 调用，alert 提示用户

### 6.3 配置管理

- `src/lib/config.ts`：根据 `NODE_ENV` 自动切换 API URL
  - 开发：`http://localhost:8001`
  - 生产：`https://api.weibull.work`

### 6.4 国际化

- 界面语言：中文为主
- 文献内容：支持中英双语切换
- LaTeX 公式：通过 KaTeX 渲染

---

## 7. 三个蒙特卡洛模块的区分

| 维度 | 结果分析 (ResultAnalysisLab) | 适用范围 (GenericStudyViewer) | 可信性验证 (VerificationItem) |
|------|-----|-----|-----|
| **计算时机** | 现场计算 | 预计算 | 预计算 |
| **数据来源** | 用户输入 | 预设参数组合 | 论文/验证目标 |
| **目的** | 验证单次结果可信度 | 展示方法表现规律 | 验证正确性 |
| **页面形式** | 固定模板 | 固定模板 | 灵活定制 |
| **数据格式** | API 返回 JSON | CSV 分片文件 | 定制组件 |

---

## 8. 开发进度概览

| 方法 | 原理 | 流程 | 计算 | 分析 | 范围 | 验证 |
|------|------|------|------|------|------|------|
| **MDM** | ✅ | ✅ | ✅ | ✅ | ✅ | 🔶 |
| **MLE** | ✅ | ✅ | ⬜ | ⬜ | ✅ | ⬜ |
| **MMLE** | ✅ | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| **WMLE** | ✅ | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| 其余 7 种 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

---

## 9. 扩展指南

### 9.1 添加新方法

1. **后端**：在 `python/methods/` 创建新文件，实现 `run()` 方法
2. **注册**：在 `main.py` 的 `method_map` 中添加映射
3. **前端组件**：在 `src/components/methods/{method}/` 创建目录
4. **方法配置**：在 `src/data/methods.json` 添加方法节点
5. **原理文档**：在 `src/content/algorithms/{slug}.md` 创建文档

### 9.2 添加新适用范围分析

- 预计算分片数据放入 `public/studies/{methodId}/chunks/`
- 使用 `GenericStudyViewer` 组件，传入 `methodId` 即可

### 9.3 添加新可信性验证

- 在 `src/components/methods/{method}/case-studies/` 创建验证组件
- 使用 `VerificationItem` 统一类型

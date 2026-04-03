# Weibull Analysis Platform - 项目架构蓝图

> 生成时间: 2026-04-03 | 版本: v7.0 | 基于 main 分支全量分析

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
| 图表渲染 | Plotly.js + Recharts | Plotly 3.3 / Recharts 2.11 |
| 数学公式 | KaTeX (rehype-katex + remark-math) | 0.16 |
| Markdown | react-markdown + remark-gfm + gray-matter | 10.1 |
| 动画 | Framer Motion | 11.0 |
| 后端框架 | FastAPI + Uvicorn | Python 3.11 |
| 科学计算 | SciPy + NumPy + Pandas | - |
| AI 集成 | OpenAI SDK (聊天功能) | 6.17 |
| 部署 | Docker Compose + Cloudflare Tunnel | 3 容器 |
| 托管 | 绿联 NAS (无公网 IP) | - |

### 1.3 架构模式

**分层单体架构 (Layered Monolith)** — 前后端分离，各自内部按职责分层：

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                    Cloudflare CDN
                    (HTTPS + WAF)
                         │
                  Cloudflare Tunnel
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────┴────┐    ┌──────┴──────┐   ┌────┴────┐
   │cloudflared│   │  frontend   │   │ backend │
   │ (Tunnel) │   │  Next.js    │   │ FastAPI │
   │ host net │   │   :3000     │   │  :8001  │
   └─────────┘    └─────────────┘   └─────────┘
                     API: REST/JSON
```

- **前端** — 展示层 (Pages) → 组件层 (Components) → 数据访问层 (Hooks + Lib)
- **后端** — API 路由层 (main.py) → 算法注册层 (registry.py) → 算法实现层 (methods/*.py) → 基础设施层 (base.py)

---

## 2. 架构可视化

### 2.1 系统上下文图

```
                    ┌─────────────┐
                    │   用户/工程师  │
                    └──────┬──────┘
                           │ HTTPS
                    ┌──────┴──────┐
                    │  Cloudflare  │
                    │   CDN/WAF    │
                    └──────┬──────┘
                           │ Tunnel
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │ Frontend   │ │ API   │ │ 静态数据    │
        │ Next.js    │→│FastAPI│←│ (Git-Based)│
        │ :3000      │ │ :8001 │ │ Flat Files │
        └───────────┘ └───┬───┘ └───────────┘
                          │
                   ┌──────┴──────┐
                   │ 算法引擎     │
                   │ SciPy/NumPy │
                   └─────────────┘
```

### 2.2 前端数据流

```
Page (page.tsx)
  │
  ├─ useState: cards/data/result/traceData
  │
  ├─ useWeibullCalculation (hook)
  │    └─ calculateWeibull() ──→ POST /calculate ──→ Backend
  │    └─ 返回 WeibullResult + traceData
  │
  ├─ AnalysisCard (component)
  │    ├─ MethodSelector (选择算法)
  │    ├─ DataEditor (输入/选择数据)
  │    ├─ Plotly Weibull 概率图
  │    └─ 参数面板 (β, η, γ, R²)
  │
  └─ lib/weibull.ts (前端数学工具)
       ├─ calculateMedianRanks() — Bernard 中位秩
       ├─ calculateWeibullParameters() — RRX 线性回归
       ├─ generatePDFPoints() / generateCDFPoints() — 绘图用
       └─ generateLinePoints() — 拟合直线
```

### 2.3 后端请求处理流

```
POST /calculate
  │
  ├─ CalculationRequest (Pydantic)
  │    ├─ method: str
  │    ├─ data: List[float]
  │    ├─ trace: Optional[bool]
  │    └─ offset: Optional[float] (MDM专用)
  │
  ├─ resolve_method(method_id)  ← methods/registry.py
  │    ├─ IMPLEMENTED: {mle: MLE, lre: LRE, ...}
  │    ├─ ALIASES: {rrx→lre, gm11→grey, ...}
  │    └─ NOT_IMPLEMENTED: {construct_stat, mve, ...}
  │
  ├─ _run_with_fallback()
  │    ├─ _run_algorithm() ──→ AlgorithmClass(data).run()
  │    └─ 失败时 fallback → WMLE(data).run()
  │
  └─ _extract_result()
       ├─ MethodResult (新格式, dataclass)
       └─ List [beta, eta, gamma, r2, converged] (旧格式兼容)
```

---

## 3. 核心架构组件

### 3.1 Calculator（计算器）— `/`

**职责**: 交互式威布尔参数估计，支持多方法多卡片叠加对比。

**核心文件**:
- `src/app/page.tsx` — 主页面，管理卡片状态数组
- `src/components/calculator/AnalysisCard.tsx` — 单张分析卡片
- `src/components/calculator/MethodSelector.tsx` — 方法选择弹窗
- `src/components/calculator/DataEditor.tsx` — 数据输入/案例选择编辑器

**数据模型**:
```typescript
CardData {
  id, type, data, result, methodId, color,
  fitMode: 'fit' | 'manual',
  is3P: boolean,
  dataSources?: DataSource[]  // 多案例批量模式
}
```

**状态管理**: 纯 React `useState`，所有状态集中在 `page.tsx` 的 `cards` 数组中。无全局状态管理库。

**特点**:
- 卡片式布局，每张卡片独立选择方法、数据、参数
- 支持从案例库导入数据（单选/多选）
- 多卡片叠加对比：后续卡片可叠加前序卡片的结果图层
- 2 参数/3 参数模式切换

---

### 3.2 Methods（方法系统）— `/methods`

**职责**: 25+ 种参数估计方法的详细展示，含 7 个子 Tab。

**核心文件**:
- `src/app/methods/[methodId]/page.tsx` — 方法详情页（路由 + Tab 切换）
- `src/components/methods/AlgorithmDetail.tsx` — 原理文档渲染
- `src/components/methods/VariableFlowViewer.tsx` — 程序流程可视化
- `src/components/methods/ResultAnalysisLab.tsx` — 结果分析（蒙特卡洛）
- `src/components/methods/shared/studies/GenericStudyViewer.tsx` — 适用范围（统一组件）
- `src/components/methods/CaseStudyViewer.tsx` — 可信性验证
- `src/components/methods/shared/compare/MethodCompareViewer.tsx` — 方法对比

**7 个 Tab 架构**:

| Tab | 组件 | 数据来源 | 计算时机 |
|-----|------|----------|----------|
| 原理文档 | AlgorithmDetail | `src/content/algorithms/*.md` | 静态 |
| 程序流程 | VariableFlowViewer | `src/data/method_flows/*.json` | 静态 |
| 计算过程 | AnalysisCard + MethodVisualizer | 后端 API (trace=true) | 现场计算 |
| 结果分析 | AnalysisCard + ResultAnalysisLab | 后端 API + Monte Carlo | 现场计算 |
| 适用范围 | GenericStudyViewer | `public/studies/{method}/chunks/*.csv` | 预计算 |
| 可信性验证 | CaseStudyViewer | 方法专用组件 | 预计算 |
| 方法对比 | MethodCompareViewer | 后端 Monte Carlo API | 现场计算 |

**方法专用组件结构** (以 MDM 为样板):
```
methods/mdm/
├── index.ts                    # 统一导出
├── visualizers/
│   ├── MDMVisualizer.tsx       # 计算过程可视化
│   ├── MDM3DSurfaceVisualizer.tsx
│   ├── MDMIterationViewer.tsx
│   └── MDMOffsetAnalyzer.tsx
├── charts/
│   ├── SigmaBetaChart.tsx      # σ(β) 曲线
│   └── GradientGammaChart.tsx  # γ 梯度分析
└── case-studies/
    └── caseRegistry.tsx        # 验证项注册
```

---

### 3.3 Cases（案例数据库）— `/cases`

**职责**: 科研文献中的标准失效数据集存储与检索。

**核心文件**:
- `src/app/cases/page.tsx` — 案例总览
- `src/app/cases/[caseId]/page.tsx` — 单案例详情
- `src/app/cases/groups/[groupId]/page.tsx` — 案例组
- `src/app/api/cases/route.ts` — 案例 API
- `src/lib/cases.ts` — 类型定义

**数据架构** — Git-Based Flat File:
```
案例配置: public/cases/[methodId]_caseX.md (Markdown + YAML front matter)
案例数据: public/cases/[methodId]_caseX_full.csv
API路由:  /api/cases → 遍历文件名动态生成
```

**CaseItem 数据模型**:
```typescript
{
  id, title, industry, type, size, tags,
  data_raw: string,          // 换行分隔的失效数据
  parameters?: { beta, eta, gamma },
  related_paper_slug?: string
}
```

---

### 3.4 Library（图书馆）— `/library`

**职责**: Markdown 学术文献阅读，双语切换。

**核心文件**:
- `src/app/library/page.tsx` — 文献列表
- `src/app/library/[slug]/page.tsx` — 文献详情
- `src/components/library/LibraryPageClient.tsx` — 客户端渲染

**文献存储**: `src/content/*.md`，通过 gray-matter 解析 front matter。

---

### 3.5 后端算法引擎

**核心文件**:
- `python/main.py` — FastAPI 入口，4 个 API 端点
- `python/base.py` — WeibullBase 基类 + MethodResult 数据类
- `python/methods/registry.py` — 方法注册表 (resolve/alias/not-implemented)
- `python/methods/{method}.py` — 各算法实现

**算法实现模式**:
```python
class MLE(WeibullBase):          # 继承 WeibullBase
    def run(self, trace=False):  # 统一接口
        # @step 标记注释 (用于流程可视化)
        ...
        return [beta, eta, gamma, r2, converged]  # 或 MethodResult
```

**WeibullBase 基类提供**:
- `self.data` — 排序后的正值数据
- `self.n` — 样本量
- `self.trace_data` — 追踪数据（trace=True 时收集）
- `self._median_ranks()` — Bernard/Exact 中位秩
- `self._calculate_r2()` — R² 拟合优度
- `self._cdf_3p()` — 三参数 CDF
- `self.log_step()` — 追踪记录（自动处理 numpy 类型转换）

**MethodResult 数据类**:
```python
@dataclass
class MethodResult:
    beta: float
    eta: float
    gamma: float
    r_squared: float
    converged: Union[bool, str] = True
    trace_data: Any = None
```

**方法注册表**:
```
IMPLEMENTED (11个): mle, mmle, mps, wmle, lse, mdm, lre, mm, pwm, grey, bayesian
ALIASES (12个):     wlse→lse, rrx→lre, rry→lre, blre→lre, gm11→grey, ...
NOT_IMPLEMENTED (8): construct_stat, mve, lsf, ai, pso, svr, ann, ...
```

**Fallback 策略**: 算法执行失败时自动降级到 WMLE（加权最小似然估计）。

---

### 3.6 API 端点总览

| 端点 | 方法 | 用途 | 请求体 |
|------|------|------|--------|
| `/calculate` | POST | 单次参数估计 | `{method, data, trace?, offset?}` |
| `/calculate_3d_surface` | POST | MDM 3D 曲面 | `{method, data, trace_data?}` |
| `/batch_simulation` | POST | 批量蒙特卡洛 (CSV) | `{method, true_beta, true_eta, ...}` |
| `/monte_carlo_simulate` | POST | 方法对比用蒙特卡洛 | `{method, beta, eta, n, rep, ...}` |

**Next.js API Routes** (BFF 层):

| 路由 | 用途 |
|------|------|
| `/api/algorithms` | 读取算法 Markdown 文档 |
| `/api/cases/*` | 案例数据的 CRUD |
| `/api/method-flow/[methodId]` | 程序流程 JSON |
| `/api/studies/[methodId]/chunks` | 适用范围 chunk 文件列表 |
| `/api/studies/simulate` | 适用范围实时模拟 |
| `/api/content` | 内容服务 |
| `/api/chat` | AI 聊天 (OpenAI) |

---

## 4. 数据架构

### 4.1 存储策略

**Git-Based Flat File** — 无数据库，所有数据以文件形式存储在仓库中。

| 数据类型 | 格式 | 路径 | 读取方式 |
|----------|------|------|----------|
| 案例配置 | Markdown + YAML | `public/cases/` | API 解析 front matter |
| 案例数据 | CSV | `public/cases/` | 前端 fetch |
| 算法文档 | Markdown + LaTeX | `src/content/algorithms/` | API → gray-matter |
| 程序流程 | JSON | `src/data/method_flows/` | 静态 import |
| 方法索引 | JSON | `src/data/methods.json` | 静态 import |
| 适用范围数据 | CSV (chunks) | `public/studies/{method}/chunks/` | 前端 fetch |
| 文献 | Markdown | `src/content/` | API → gray-matter |
| 文献图片 | PNG/JPG | `public/{id}-图片/` | 静态文件服务 |

### 4.2 适用范围数据分片系统

预计算的蒙特卡洛模拟数据，按参数组合分片存储：

**文件命名规则**:
- 通用: `b{beta}_e{eta}_g{gamma}_n{n}_rep{rep}_seed{seed}_step{step}.csv`
- MDM: 额外包含 `_d{offset}` 参数

**CSV 列**: `beta_true, eta_true, gamma_true, sample_size, sim_id, est_beta, est_eta, est_gamma, bias_beta, bias_eta, bias_gamma, r_squared`

**加载策略**: 前端通过 `/api/studies/{methodId}/chunks` 获取文件列表 → 解析可用参数 → 按用户选择加载对应 CSV → 前端统计计算。

### 4.3 核心数据模型

**WeibullResult** (前后端共享概念):
```typescript
{
  beta: number | null      // 形状参数
  eta: number | null       // 尺度参数
  gamma: number            // 位置参数
  rSquared: number | null  // 拟合优度
  points: PlotPoint[]      // 概率图坐标
  converged?: boolean | string
}
```

**DataPoint** (前端数据输入):
```typescript
{
  id: number
  value: number           // 失效时间
  status: 'F' | 'S'       // 失效/截尾
}
```

**DataSource** (多曲线模式):
```typescript
{
  id, name, color, data: DataPoint[],
  result?: WeibullResult,
  sourceType: 'case' | 'group-subcase' | 'custom',
  visible?: boolean
}
```

---

## 5. 前端架构模式

### 5.1 组件层次

```
layout.tsx (全局布局 + 主题色切换)
  └── page.tsx (路由页面)
       ├── 通用组件 (shared/)
       │   ├── charts/ — BoxPlot, Heatmap, Density, Contour, Convergence, ChartCard
       │   ├── ParamSelector.tsx
       │   └── SimulationConfigPanel.tsx
       ├── 计算器组件 (calculator/)
       │   ├── AnalysisCard.tsx — 分析卡片（核心）
       │   ├── MethodSelector.tsx
       │   └── DataEditor.tsx
       ├── 方法组件 (methods/)
       │   ├── AlgorithmDetail.tsx
       │   ├── VariableFlowViewer.tsx
       │   ├── ResultAnalysisLab.tsx
       │   ├── CaseStudyViewer.tsx
       │   ├── shared/
       │   │   ├── studies/GenericStudyViewer.tsx
       │   │   ├── compare/MethodCompareViewer.tsx
       │   │   └── verification/
       │   └── {method}/ — mle/, wmle/, mdm/
       ├── 图书馆组件 (library/)
       └── 聊天组件 (chat/)
```

### 5.2 状态管理

**无全局状态库**，采用以下模式：

| 场景 | 方案 |
|------|------|
| 页面级状态 | `useState` in page.tsx |
| 组件间传递 | Props drilling |
| 服务端数据 | `fetch` in `useEffect` / API Routes |
| URL 状态 | `useSearchParams` |
| 临时 UI 状态 | 组件内 `useState` |

**渲染优化**:
- `dynamic()` 懒加载重组件 (Plotly, Visualizer)
- `useMemo` / `useCallback` 在 GenericStudyViewer 中大量使用
- 无限循环检测 (`renderCountRef`)

### 5.3 数据获取模式

```
前端组件
  ├─ 静态数据: import from '@/data/methods.json'
  ├─ API Route (BFF): fetch('/api/cases')
  ├─ 后端直连: fetch('https://api.weibull.work/calculate')
  └─ 静态文件: fetch('/studies/mle/chunks/b2_e1000_...')
```

**API 配置** (`src/lib/config.ts`):
- 开发: `http://localhost:8001`
- 生产: `https://api.weibull.work`

### 5.4 渲染管线

**Markdown 文档渲染**:
```
.md 文件 → fetch → gray-matter (提取 YAML) → react-markdown
  ├─ remark: gfm, math
  └─ rehype: raw, slug, katex, autolink-headings
```

**数学公式**: KaTeX (同步渲染，带 5s 超时保护)
**流程图**: Mermaid (异步渲染)
**图表**: Plotly.js (3D 曲面/等高线) + Recharts (2D 统计图)

---

## 6. 后端架构模式

### 6.1 分层结构

```
main.py                    ← API 路由层
  │
  ├─ _run_with_fallback()  ← 编排层 (fallback 逻辑)
  │    └─ _run_algorithm()
  │         └─ _extract_result()
  │
  ├─ registry.py           ← 注册层 (方法发现 + 别名)
  │    └─ resolve_method()
  │
  └─ methods/*.py          ← 算法实现层
       └─ WeibullBase (base.py)
            ├─ data 排序与过滤
            ├─ _median_ranks()
            ├─ _calculate_r2()
            └─ log_step()
```

### 6.2 算法实现规范

每个算法类遵循统一接口：

```python
class AlgorithmName(WeibullBase):
    def run(self, trace=False, **kwargs) -> list | MethodResult:
        # @step 标记注释（用于前端程序流程 Tab）
        # @formula, @symbols, @inputs, @outputs
        ...
        return [beta, eta, gamma, r2, converged]
```

**特殊参数**: MDM 支持 `offset` 参数，通过 `**kwargs` 传递。

**结果格式兼容**: `_extract_result()` 同时支持 `MethodResult` (dataclass) 和 `list/tuple` (旧格式)。

### 6.3 错误处理与弹性

```
算法执行 → 异常?
  │
  ├─ 否 → 返回结果
  │
  └─ 是 → Fallback 到 WMLE
            │
            ├─ 成功 → 返回 WMLE 结果
            └─ 失败 → HTTPException 500
```

**前端错误处理**: `calculateWeibull()` 捕获错误，弹出 alert 提示用户检查后端状态。

---

## 7. 部署架构

### 7.1 Docker Compose 拓扑

```yaml
services:
  frontend:                    # 多阶段构建
    - Stage 1: npm ci (deps)
    - Stage 2: npm run build
    - Stage 3: node server.js (standalone)
    - Port: 3000
    - 非root用户: nextjs (uid 1001)

  backend:                     # 单阶段构建
    - Python 3.11-slim
    - pip install (清华镜像)
    - uvicorn main:app
    - Port: 8001

  cloudflared:                 # Cloudflare Tunnel
    - network_mode: host       # 访问 localhost:3000/8001
    - Token 认证
```

**网络**: frontend + backend 在 `weibull-network` bridge 网络；cloudflared 使用 host 模式直接访问 localhost。

### 7.2 域名路由

| 域名 | 目标 | 用途 |
|------|------|------|
| `weibull.work` | `frontend:3000` | 前端应用 |
| `api.weibull.work` | `backend:8001` | API 接口 + Swagger 文档 |

### 7.3 CI/CD 流程

```
本地开发机
  │ git push
  ▼
GitHub (NEUwpy/weibull.work)
  │
  │ SSH 到 NAS
  ▼
绿联 NAS (192.168.31.148)
  ├─ alpine/git pull (NAS 无 git)
  └─ docker compose up -d --build
```

**更新命令**:
```bash
# 一键更新
git push && \
ssh user@nas "docker run --rm -v ... alpine/git pull && \
cd /path && docker compose up -d --build"
```

---

## 8. 跨领域关注点

### 8.1 安全

| 关注点 | 实现方式 |
|--------|----------|
| HTTPS | Cloudflare 自动终止 |
| CORS | 白名单: weibull.work, localhost:3000 |
| DDoS 防护 | Cloudflare WAF |
| 容器安全 | 非root用户运行前端 |
| 凭证管理 | `docs/凭证信息.md` (不提交)，`.env` (不提交) |

### 8.2 前后端数学逻辑分工

| 计算 | 执行位置 | 原因 |
|------|----------|------|
| 参数估计 (MLE, MDM等) | 后端 | 数值优化需要 SciPy |
| 中位秩 (Bernard) | 前端+后端 | 前端用于绘图，后端用于算法 |
| R² 计算 | 后端 | 算法内部需要 |
| PDF/CDF 生成 | 前端 | 仅用于绘图 |
| RRX 线性回归 | 前端 | 快速初始估计/绘图 |
| 蒙特卡洛模拟 | 后端 | 批量数值计算 |

### 8.3 数学公式渲染管线

```
Python 代码中的 @step/@formula 标记
  ↓ (前端读取)
method_flows/*.json (步骤映射)
  ↓
VariableFlowViewer (程序流程 Tab)
  └─ KaTeX 渲染

Markdown 中的 $...$ / $$...$$
  ↓
remark-math → rehype-katex → KaTeX 渲染
```

---

## 9. 扩展指南

### 9.1 添加新方法

**后端**:
1. 创建 `python/methods/{method}.py`，继承 `WeibullBase`，实现 `run()`
2. 在 `python/methods/registry.py` 的 `IMPLEMENTED` 字典中注册
3. 添加 `@step` 标记注释（用于程序流程可视化）

**前端**:
1. 在 `src/data/methods.json` 添加方法条目（树状结构）
2. 在 `src/content/algorithms/{method}.md` 创建算法文档
3. 如需专用可视化，创建 `src/components/methods/{method}/` 目录
4. 复用通用组件: `GenericStudyViewer`, `CaseStudyViewer`, `shared/charts/`

**适用范围数据**:
1. 使用 `python/methods/{method}_studies.py` 生成蒙特卡洛数据
2. CSV 文件放置到 `public/studies/{method}/chunks/`

### 9.2 添加新案例

1. 在 `public/cases/` 创建 Markdown 文件（含 YAML front matter）
2. 添加 `data_raw` 字段（换行分隔的数值）
3. API 自动发现新文件

### 9.3 扩展检查清单

```
□ 搜索过现有组件是否可复用？
□ 通用组件是否放到 shared/？
□ 方法专用组件放到 methods/{method}/？
□ 数据是否放 content/ 或 public/（非 TS 文件）？
□ 是否更新了 index.ts 导出？
□ 是否更新了 05-状态.md？
```

---

## 10. 架构决策记录

### AD-1: 前后端分离而非全栈框架

**背景**: 需要复杂的科学计算 (SciPy 优化器) 和丰富的可视化 (Plotly)。
**决策**: Python FastAPI (计算) + Next.js (展示)。
**后果**: 需要维护两套构建管线，但职责清晰，算法可独立测试。

### AD-2: Git-Based Flat File 而非数据库

**背景**: 案例数据量小 (100 篇级)，更新频率低，需要版本控制。
**决策**: 所有数据以 Markdown/CSV/JSON 文件存储在 Git 仓库中。
**后果**: 零运维数据库，数据随代码版本化，但不支持复杂查询。

### AD-3: 纯 React useState 而非全局状态管理

**背景**: 计算器页面状态集中在单个页面组件中。
**决策**: 不引入 Redux/Zustand 等，使用 `useState` + Props drilling。
**后果**: 简单直观，但 Calculator 页面组件较大 (~460 行)。

### AD-4: 方法注册表模式

**背景**: 25+ 种方法需要统一管理和别名支持。
**决策**: `registry.py` 集中管理 IMPLEMENTED/ALIASES/NOT_IMPLEMENTED 三层映射。
**后果**: 添加新方法只需在字典中加一行，但别名关系需要手动维护。

### AD-5: 算法 Fallback 到 WMLE

**背景**: 某些算法在特定数据条件下可能失败 (如 MLE 的无界问题)。
**决策**: 任何算法失败时自动降级到 WMLE。
**后果**: 用户始终能得到结果，但可能不是最优方法的结果。

### AD-6: 预计算蒙特卡洛数据 (适用范围)

**背景**: 蒙特卡洛模拟耗时 (数千次迭代)，不适合现场计算。
**决策**: 预生成 CSV 分片文件，前端按需加载。
**后果**: 数据体积大但响应快，但参数组合覆盖需提前规划。

### AD-7: Cloudflare Tunnel 部署

**背景**: NAS 无公网 IP，需要外网访问。
**决策**: Cloudflare Tunnel (cloudflared) 提供安全隧道。
**后果**: 零端口暴露，自动 HTTPS，但依赖 Cloudflare 服务可用性。

---

## 11. 方法完成状态 (2026-04-03)

| 方法 | 后端算法 | 原理文档 | 程序流程 | 计算过程 | 结果分析 | 适用范围 | 可信性验证 |
|------|---------|---------|---------|---------|---------|---------|-----------|
| **MDM** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔶 |
| **MLE** | ✅ | ✅ | ✅ | ⬜ | ⬜ | ✅ | ⬜ |
| **MMLE** | ✅ | ✅ | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| **WMLE** | ✅ | ✅ | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| LRE | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| LSE | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| MM | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| MPS | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| PWM | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| Bayesian | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| Grey GM(1,1) | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

**后端**: 11 个算法已实现，12个别名映射，8个待实现。
**前端**: MDM 最完整 (样板方法)，MLE/WMLE 部分完成，其余仅有后端算法。

---

## 12. 关键文件索引

### 前端核心

| 文件 | 职责 |
|------|------|
| `src/app/layout.tsx` | 全局布局、导航、主题色切换 |
| `src/app/page.tsx` | Calculator 主页（卡片管理） |
| `src/app/methods/[methodId]/page.tsx` | 方法详情页（7 Tab 路由） |
| `src/lib/weibull.ts` | 前端数学工具（中位秩、RRX、PDF/CDF） |
| `src/lib/config.ts` | API 配置（开发/生产环境切换） |
| `src/lib/methods.ts` | 方法树索引解析 |
| `src/hooks/useWeibullCalculation.ts` | 后端计算 API 封装 |
| `src/components/calculator/AnalysisCard.tsx` | 分析卡片（核心 UI 组件） |
| `src/components/methods/shared/studies/GenericStudyViewer.tsx` | 适用范围统一组件 |

### 后端核心

| 文件 | 职责 |
|------|------|
| `python/main.py` | FastAPI 入口（4 个端点 + 统一异常处理） |
| `python/base.py` | WeibullBase 基类 + MethodResult |
| `python/methods/registry.py` | 方法注册表（resolve + alias + 501） |

### 配置与部署

| 文件 | 职责 |
|------|------|
| `docker-compose.yml` | 3 容器编排 |
| `Dockerfile.frontend` | Next.js 多阶段构建 |
| `Dockerfile.backend` | Python 镜像 |
| `next.config.js` | Next.js standalone 输出 |
| `tailwind.config.ts` | Tailwind 主题配置 |

### 文档系统

| 文件 | 职责 |
|------|------|
| `CLAUDE.md` | AI 助手入口文档 |
| `01-结构.md` | 目录结构与数据流 |
| `02-规则.md` | 开发规范 |
| `02-A-适用范围规范.md` | 适用范围开发规范 |
| `02-B-可信性验证规范.md` | 可信性验证规范 |
| `03-维护.md` | 部署与运维 |
| `04-目标.md` | 功能目标 |
| `05-状态.md` | 建设进度 |
| `06-模块.md` | 系统模块定义 |

---

*本蓝图基于 2026-04-03 的 main 分支全量代码分析生成。建议在重大架构变更后更新。*

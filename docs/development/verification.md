# 可信性验证开发说明

建设目的与准则见[可信性验证](../建设规范/02-参数估计方法/06-可信性验证.md)。本文说明已接入的 MDM 验证配置、数据与渲染。

## 概述

页面读取预计算结果，与论文图表并排呈现。方法开放和进度以[建设状态](../../05-状态.md)为准。

## 目录结构

```
软件仓 public/case-studies/mdm/verification-{paperId}/config.md
外部数据根 public/case-studies/mdm/verification-{paperId}/
├── curves.json
├── data.csv
├── results.csv
└── summary.json
```

浏览器仍用 `/case-studies/...` 读取结果文件，目录配置见[外部运行数据](../data/README.md#当前目录与读取)。示例中的原图沿用原图片网址，由[文献资源读取层](../library/README.md)提供。

## 配置文件格式 (config.md)

直接查阅[已登记的 182-046 配置](../../public/case-studies/mdm/verification-182-046/config.md)。YAML 的 `id` 和 `name` 用于登记列表，`paper` 记录题录、论文编号及图号，`verification` 记录真参数、样本量、重复数、MDM 偏移量和资源路径。字段类型见 [VerificationConfig](../../src/components/methods/shared/verification/types.ts)。

## 添加新验证（3步）

### 1. 创建目录和配置

在软件仓 `public/case-studies/mdm/` 下创建 `verification-{paperId}` 目录，按现有示例填写 `config.md`。

### 2. 准备外部数据文件

| 文件 | 格式 | 用途 |
|------|------|------|
| `curves.json` | JSON | 梯度曲线数据 |
| `data.csv` | CSV | 样本数据（sample_id, t₁, t₂, ...） |
| `results.csv` | CSV | 估计结果（sample_id, est_beta, est_eta, est_gamma, bias_*） |
| `summary.json` | JSON | 统计摘要 |

### 3. 验证

MDM 列表接口扫描配置目录。用验证页面核对论文原图、样本、估计结果和曲线路径能否读取，数据与对应图表是否匹配。

## 组件架构

```
src/components/methods/
├── CaseStudyViewer.tsx           # 通用入口组件
└── shared/verification/
    ├── types.ts                  # 类型定义
    ├── VerificationItem.tsx      # 验证项组件（左右对比布局）
    └── index.ts
```

### CaseStudyViewer

通用入口组件，自动：
- 从 API 加载验证列表
- 提供下拉选择器
- 根据选中项加载对应数据

### VerificationItem

单个验证项组件，布局结构：

```
┌─────────────────────────────────────────────────────┐
│ 参数条件（样本/真实参数/仿真设置）                    │
├──────────────────────┬──────────────────────────────┤
│  左栏：论文结果        │  右栏：系统复现               │
│  (图片/表格/文本)      │  (图表/表格)                 │
└──────────────────────┴──────────────────────────────┘
```

Props：
- `title`: 标题
- `params`: 参数条件数组
- `samplesData`: 可折叠的样本数据表格
- `paperContent`: 左栏内容（image/table/text）
- `systemContent`: 右栏内容（React 节点）

## API 路由

- [`GET /api/case-studies/mdm`](../../src/app/api/case-studies/mdm/route.ts) 扫描 MDM 配置，返回 `{ cases }`。扫描支持以 `verification` 或 `case` 开头的目录。
- [`GET /api/case-studies/mdm/{caseId}`](../../src/app/api/case-studies/mdm/%5BcaseId%5D/route.ts) 返回单份兼容配置，响应为 `{ config }`。

## 类型定义

核心类型见[共享类型定义](../../src/components/methods/shared/verification/types.ts)：

| 类型 | 用途 |
|------|------|
| `VerificationConfig` | 验证配置（从 config.md 解析） |
| `SampleData` | 样本数据 |
| `EstimateResult` | 估计结果 |
| `SampleCurve` | 梯度曲线数据 |
| `SummaryData` | 统计摘要 |

## 相关文件

- 前端入口见 [CaseStudyViewer](../../src/components/methods/CaseStudyViewer.tsx)，共享布局见 [VerificationItem](../../src/components/methods/shared/verification/VerificationItem.tsx)。

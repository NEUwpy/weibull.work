# 案例展示开发指南

本文档说明如何为方法创建案例展示功能。

## 什么是案例展示？

案例展示是将**预计算的参数研究/模拟实验数据**进行可视化的功能。适用于：
- 需要大量计算的结果展示
- 蒙特卡洛模拟分析
- 多维度参数影响研究
- 算法性能对比验证

**优势**：避免用户每次访问都重新计算，提升用户体验。

---

## 目录结构

每个方法的案例展示包含三部分：

```
# 1. 数据文件
public/case-studies/[methodId]/
├── case1/
│   ├── config.md          # YAML配置 + Markdown描述
│   └── data.csv           # 模拟数据
├── case2/
│   └── ...
└── caseX/

# 2. Python脚本
python/[methodId]/case_studies/
├── README.md
├── case1/
│   └── generate_data.py   # 数据生成脚本
└── caseX/

# 3. 前端组件（特殊案例需要）
src/components/case-studies/[methodId]/
├── case3/
│   └── Case3Viewer.tsx    # 专用组件
└── caseX/
    └── CaseXViewer.tsx
```

---

## 案例分类

| 类型 | 特点 | 需要的工作 |
|------|------|-----------|
| **常规案例** | 使用统一框架，参数变化分析 | 数据文件 + 配置 |
| **特殊案例** | 独特架构，需要专用可视化 | 数据文件 + 配置 + 组件 |

---

## 新建案例步骤

### 步骤1：创建数据目录

```bash
mkdir -p public/case-studies/[methodId]/caseX
mkdir -p python/[methodId]/case_studies/caseX
```

### 步骤2：编写数据生成脚本

在 `python/[methodId]/case_studies/caseX/generate_data.py` 创建脚本：

```python
"""
案例X: [案例名称]
描述: [案例描述]
生成数据: public/case-studies/[methodId]/caseX/data.csv
"""

import pandas as pd
import numpy as np
# 导入方法实现
import sys
sys.path.append('..')
from methods.[methodId] import [MethodClass]

# 参数设置
BETA_VALUES = [1.5, 2.0, 3.0, 5.0]
SAMPLE_SIZES = [5, 10, 20, 30]
# ... 其他参数

# 生成数据
results = []
for beta in BETA_VALUES:
    for n in SAMPLE_SIZES:
        for sim_id in range(100):  # 100次模拟
            # 1. 生成随机样本
            # 2. 调用方法估计参数
            # 3. 计算偏差
            results.append({...})

# 保存数据
df = pd.DataFrame(results)
df.to_csv('../../../public/case-studies/[methodId]/caseX/data.csv', index=False)
print(f"生成 {len(df)} 行数据")
```

运行脚本：
```bash
python python/[methodId]/case_studies/caseX/generate_data.py
```

### 步骤3：创建配置文件

在 `public/case-studies/[methodId]/caseX/config.md` 创建配置：

```markdown
---
id: "case-X"
name: "案例X: [案例名称]"
description: "[详细描述]"
processName: "[过程参数名]"      # 如: 偏移量
processSymbol: "[过程参数符号]"   # 如: δ
architecture: "normal"           # normal | special
csvFile: "/case-studies/[methodId]/caseX/data.csv"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1
params:
  # 形状参数 β
  - id: "beta"
    name: "形状参数"
    symbol: "β"
    state: "discrete"            # fixed | range | discrete
    discreteValues: [1.5, 2.0, 3, 5, 7]
    isVariable: true             # 是否为变量
    isDisplayDimension: false    # 是否作为展示维度

  # 尺度参数 η
  - id: "eta"
    name: "尺度参数"
    symbol: "η"
    state: "fixed"
    fixedValue: 1000
    isVariable: false
    isDisplayDimension: false

  # 位置参数 γ
  - id: "gamma"
    name: "位置参数"
    symbol: "γ"
    state: "fixed"
    fixedValue: 1000
    isVariable: false
    isDisplayDimension: false

  # 样本量 n
  - id: "sampleSize"
    name: "样本量"
    symbol: "n"
    state: "discrete"
    discreteValues: [5, 7, 10, 20, 30]
    isVariable: true
    isDisplayDimension: false

  # 过程参数（方法特定）
  - id: "process"
    name: "[过程参数名]"
    symbol: "[过程参数符号]"
    state: "discrete"
    discreteValues: [0, 0.05, 0.1, 0.15, 0.2]
    isVariable: true
    isDisplayDimension: false
---

# 案例X: [案例名称]

[Markdown格式的详细说明，可选]
```

### 步骤4：更新组件（如需要）

#### 4a. 常规案例

常规案例自动使用 `CaseStudyViewer` 统一框架，无需额外组件。

在 `src/components/CaseStudyViewer.tsx` 的下拉框中添加选项：

```tsx
// 在所有下拉框中添加新案例
<option value="case-X">案例X: [名称]</option>
```

#### 4b. 特殊案例

如果需要专用可视化：

1. 创建组件目录和文件：
```bash
mkdir -p src/components/case-studies/[methodId]/caseX
```

2. 创建专用组件 `CaseXViewer.tsx`：

```tsx
"use client"

import React, { useState, useEffect } from 'react'
import { ChevronDown, BookOpen } from 'lucide-react'

interface CaseXViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void
}

export default function CaseXViewer({ caseId, onCaseChange }: CaseXViewerProps) {
  const [data, setData] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        const res = await fetch('/case-studies/[methodId]/caseX/data.json')
        if (!res.ok) throw new Error('数据加载失败')
        const json = await res.json()
        setData(json)
      } catch (err) {
        console.error(err)
      } finally {
        setIsLoading(false)
      }
    }
    loadData()
  }, [])

  if (isLoading) {
    return <div>加载中...</div>
  }

  return (
    <div className="space-y-6">
      {/* 案例选择下拉框 */}
      {onCaseChange && (
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-4">
            <BookOpen className="text-purple-600" size={20} />
            <label className="text-sm font-bold text-slate-600">切换案例：</label>
            <div className="relative flex-1 max-w-md">
              <select
                value={caseId}
                onChange={(e) => onCaseChange(e.target.value)}
                className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold"
              >
                <option value="case-1">案例1: ...</option>
                {/* 添加其他案例 */}
                <option value="case-X">案例X: [名称] ★</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            </div>
          </div>
        </div>
      )}

      {/* 专用可视化内容 */}
      {/* ... */}
    </div>
  )
}
```

3. 在 `CaseStudyViewer.tsx` 中添加动态导入和判断逻辑：

```tsx
// 动态导入
const CaseXViewer = dynamic(() => import('./case-studies/[methodId]/caseX/CaseXViewer'), {
  ssr: false,
  loading: () => <div>加载中...</div>
})

// 在渲染逻辑中添加
if (selectedCase?.architecture === 'caseX') {
  return <CaseXViewer caseId={selectedCase.id} onCaseChange={handleCaseChange} />
}
```

---

## CSV 数据格式

常规案例的 CSV 必须包含以下列：

| 列名 | 类型 | 说明 |
|------|------|------|
| `beta_true` | number | 真实 β 值 |
| `sample_size` | number | 样本量 n |
| `offset_value` | number | 过程参数值（方法特定） |
| `sim_id` | number | 模拟 ID |
| `est_beta` | number | 估计 β |
| `est_eta` | number | 估计 η |
| `est_gamma` | number | 估计 γ |
| `bias_beta` | number | β 偏差 (估计值 - 真实值) |
| `bias_eta` | number | η 偏差 |
| `bias_gamma` | number | γ 偏差 |
| `r_squared` | number | R² 值 |

示例：
```csv
beta_true,sample_size,offset_value,sim_id,est_beta,est_eta,est_gamma,bias_beta,bias_eta,bias_gamma,r_squared
2.0,7,0.1,1,1.85,950,1020,-0.15,-50,20,0.98
2.0,7,0.1,2,2.12,1050,980,0.12,50,-20,0.99
```

---

## 完整示例：MDM 案例1

### 文件结构
```
public/case-studies/mdm/case1/
├── config.md
└── data.csv (125组合 × 100模拟 = 12,500行)

python/mdm/case_studies/case1/
└── generate_data.py
```

### config.md
```yaml
---
id: "case-1"
name: "案例1: 多维度参数影响研究 (100组)"
description: "研究形状参数、样本量、偏移量对MDM三参数估计结果的影响。"
processName: "偏移量"
processSymbol: "δ"
csvFile: "/case-studies/mdm/case1/data.csv"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1
params:
  - id: "beta"
    name: "形状参数"
    symbol: "β"
    state: "discrete"
    discreteValues: [1.5, 2.0, 3, 5, 7]
    isVariable: true
    isDisplayDimension: false
  # ... 其他参数
---
```

---

## 检查清单

新建案例时，确保完成以下步骤：

- [ ] 创建 `public/case-studies/[methodId]/caseX/` 目录
- [ ] 创建 `config.md` 配置文件
- [ ] 创建 `data.csv` 数据文件
- [ ] 创建 `python/[methodId]/case_studies/caseX/` 目录
- [ ] 编写 `generate_data.py` 脚本并运行
- [ ] 在 `CaseStudyViewer.tsx` 下拉框中添加案例选项
- [ ] （特殊案例）创建专用组件
- [ ] （特殊案例）在 `CaseStudyViewer.tsx` 中添加架构判断
- [ ] 运行 `npm run build` 验证
- [ ] 测试案例切换和数据加载

---

## 相关文件

| 文件 | 用途 |
|------|------|
| `ARCHITECTURE.md` | 架构说明 |
| `python/[methodId]/case_studies/README.md` | Python脚本说明 |

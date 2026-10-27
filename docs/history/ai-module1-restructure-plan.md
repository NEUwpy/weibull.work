# AI 模块 1 前端页面重构计划

> **创建时间**: 2026-04-27
> **目标**: 将 `ai/relationship/` 从单一 7-Tab 页面拆分为总览页 + 两个独立子页面（M1-R1 / M1-R2）
> **依赖文档**: [ai-module1-status.md](ai-module1-status.md)

---

## 一、重构动机

当前 `ai/relationship/page.tsx` 是一个 7-Tab 页面，两条路线混在一起。需要清晰分离：
- **M1-R1**（直接学习）：样本 → N₂ 网络 → 预测 δ
- **M1-R2**（迭代逼近）：δ₀ → MDM → N₁ → δ₁ → ... → 收敛

分离后各自有独立的 Tab 体系，内容更聚焦，后续扩展更方便。

---

## 二、术语规范

| 术语 | 全称 | 含义 | 旧称 |
|------|------|------|------|
| M1-R1 | Model 1 - Route 1 | 直接学习（样本→δ，N₂ 网络） | N₂ / 路线 1 |
| M1-R2 | Model 1 - Route 2 | 迭代逼近（δ₀→MDM→N₁→δ₁→...） | N₁ / 路线 2 |

**规则**：所有代码、文档、UI 中不再使用 N₁/N₂，统一为 M1-R1/M1-R2。

---

## 三、目标文件结构

```
ai/page.tsx                              ← AI 总览（不变）
ai/relationship/page.tsx                 ← 总览页（M1-R1 + M1-R2 两个卡片）
ai/relationship/m1-r1/page.tsx           ← 路线 1 子页面，8 Tab
ai/relationship/m1-r1/components/        ← 路线 1 的 Tab 组件
ai/relationship/m1-r2/page.tsx           ← 路线 2 子页面，9 Tab
ai/relationship/m1-r2/components/        ← 路线 2 的 Tab 组件
```

旧的 `ai/relationship/components/` 在迁移完成后删除。

---

## 四、总览页设计 (`ai/relationship/page.tsx`)

- 仅两个卡片，简洁风格
- 卡片 1：M1-R1（直接学习），链接到 `/ai/relationship/m1-r1`
- 卡片 2：M1-R2（迭代逼近），链接到 `/ai/relationship/m1-r2`
- 返回按钮：`← 返回 AI 方法总览`（链接到 `/ai`）
- 设计参考：`ai/page.tsx` 的模块卡片风格

---

## 五、M1-R1 子页面（8 个 Tab）

### Tab 列表

| # | Tab ID | 名称 | 图标 | 内容 |
|---|--------|------|------|------|
| 1 | theory | 原理说明 | BookOpen | 直接学习原理（样本→δ 的逻辑、为什么可行） |
| 2 | training | 训练算法 | Cpu | N₂ 网络结构、超参、训练策略 |
| 3 | data | 训练数据 | Database | 数据生成方式、参数空间、数据规模 |
| 4 | delta-accuracy | 偏移量估计精度 | Crosshair | 见下方详细设计 |
| 5 | param-accuracy | 三参数估计精度 | Target | 见下方详细设计 |
| 6 | playground | 在线使用 | Play | 样本输入 → AI 预测 δ |
| 7 | verification | 可信性验证 | FlaskConical | 真值、估计值、偏差列表 |
| 8 | compare | 方法对比 | GitCompare | 先空着（占位） |

### delta-accuracy Tab 详细设计

展示两件事：

**① 真值与最优 δ 的对应关系**
- 散点图：X = 真值参数（β 或 η），Y = 对应的最优 δ
- 按 n 分组着色
- 目的：展示"不同参数组合需要不同的 δ"

**② 模型预测精度**
- 散点图：X = 真值最优 δ，Y = 模型预测 δ
- 对角线参考线（完美预测 = 落在对角线上）
- 按 β/n 分组着色
- 偏差统计：均值、标准差、分位数、直方图

**数据来源**：`validation_predictions_n{n}.csv`（已有）

### param-accuracy Tab 详细设计

对比三种 δ 来源下的参数估计误差：

| δ 来源 | 说明 |
|--------|------|
| δ = 0.5（固定值） | 用户常用的经验值 |
| δ = AI 预测值 | M1-R1 模型输出 |
| δ = 真值最优 δ | 搜索得到的理论最优 |

每种情况展示：
- 绝对误差：|β̂ - β|, |η̂ - η|, |γ̂ - γ|
- 可按 β/n 分组
- 用分组柱状图或箱型图对比

**数据来源**：需要新生成。现有验证数据只有最优 δ 的结果，需要补充 δ=0.5 和 δ=AI 的 MDM 运行结果。

### 组件迁移

| 现有组件 | 去向 | 操作 |
|----------|------|------|
| `components/TrainingTab.tsx` | `m1-r1/components/TrainingTab.tsx` | 移动 |
| `components/DataTab.tsx` | `m1-r1/components/DataTab.tsx` | 移动 |
| `components/PlaygroundTab.tsx` | `m1-r1/components/PlaygroundTab.tsx` | 移动 |
| `components/PerformanceTab.tsx` | — | 拆分，内容分配到 delta-accuracy 和 param-accuracy |
| `components/VerificationTab.tsx` | `m1-r1/components/VerificationTab.tsx` | 移动+改写 |
| `components/CompareTab.tsx` | `m1-r1/components/CompareTab.tsx` | 移动（先空着） |
| 内联 TheoryTab | `m1-r1/components/TheoryTab.tsx` | 提取+改写（聚焦直接学习） |

---

## 六、M1-R2 子页面（9 个 Tab）

### Tab 列表

| # | Tab ID | 名称 | 图标 | 内容 |
|---|--------|------|------|------|
| 1 | theory | 原理说明 | BookOpen | 迭代逼近原理（δ₀→MDM→N₁→δ₁→...→收敛） |
| 2 | training | 训练算法 | Cpu | N₁ 网络结构、迭代算法、收敛判据 |
| 3 | data | 训练数据 | Database | 数据生成 |
| 4 | iteration | 迭代过程 | RefreshCw | δ 收敛轨迹、收敛步数统计 |
| 5 | delta-accuracy | 偏移量估计精度 | Crosshair | 同 R1 逻辑 |
| 6 | param-accuracy | 三参数估计精度 | Target | 同 R1 逻辑 |
| 7 | playground | 在线使用 | Play | 迭代演示（输入样本 → 显示迭代过程） |
| 8 | verification | 可信性验证 | FlaskConical | 同 R1 逻辑 |
| 9 | compare | 方法对比 | GitCompare | 先空着（占位） |

### iteration Tab 详细设计

展示 M1-R2 的迭代收敛过程：
- δ 收敛轨迹图：X = 迭代步数，Y = δ 值
- 参数收敛轨迹：X = 迭代步数，Y = β̂/η̂/γ̂
- 收敛步数分布直方图
- 失败案例统计

**数据来源**：`evaluate_route2.py` 输出

### 组件创建

M1-R2 的组件全部新建（大部分为占位/待开发）：

| 组件 | 状态 |
|------|------|
| `m1-r2/components/TheoryTab.tsx` | 新建（讲迭代逼近） |
| `m1-r2/components/TrainingTab.tsx` | 新建（讲 N₁ + 迭代算法） |
| `m1-r2/components/DataTab.tsx` | 新建或共享 R1 |
| `m1-r2/components/IterationTab.tsx` | 新建（迭代过程可视化） |
| `m1-r2/components/DeltaAccuracyTab.tsx` | 新建（同 R1 逻辑） |
| `m1-r2/components/ParamAccuracyTab.tsx` | 新建（同 R1 逻辑） |
| `m1-r2/components/PlaygroundTab.tsx` | 新建/占位 |
| `m1-r2/components/VerificationTab.tsx` | 新建 |
| `m1-r2/components/CompareTab.tsx` | 占位 |

---

## 七、导航与面包屑

### 总览页
```
← 返回 AI 方法总览     （链接到 /ai）
```

### M1-R1 / M1-R2 子页面
```
← 返回关系建立总览     （链接到 /ai/relationship）
```

---

## 八、需要更新的文档

重构完成后，以下文档需要同步更新：

| 文档 | 更新内容 |
|------|----------|
| `docs/ai-module1-status.md` | 文件清单、前端页面 Tab 状态 |
| `docs/ai-module1-handoff-prompt.md` | 文件路径、当前状态 |
| `docs/ai-methods-handoff-prompt.md` | 模块 1 状态描述 |
| `docs/ai-methods-module1-detail.md` | 可视化方案（27 个图表 → 新 Tab 结构） |

---

## 九、实施步骤

### Phase 1: 创建路由结构
- 创建 `ai/relationship/m1-r1/page.tsx`（8 Tab 骨架）
- 创建 `ai/relationship/m1-r2/page.tsx`（9 Tab 骨架）
- 修改 `ai/relationship/page.tsx` 为总览页（两个卡片）

### Phase 2: 迁移 M1-R1 组件
- 移动现有 Tab 组件到 `m1-r1/components/`
- 改写 TheoryTab（聚焦直接学习）
- 提取 PerformanceTab 内容到 delta-accuracy 和 param-accuracy

### Phase 3: 新建 M1-R1 新 Tab
- 创建 `DeltaAccuracyTab.tsx`
- 创建 `ParamAccuracyTab.tsx`（需要数据支持）
- 改写 VerificationTab

### Phase 4: 创建 M1-R2 组件
- 创建全部 9 个 Tab 组件（大部分占位）
- IterationTab 需要 `evaluate_route2.py` 的数据

### Phase 5: 导航调整
- 面包屑返回链接
- 旧 `components/` 目录清理

### Phase 6: 术语统一
- 代码中 N₁ → M1-R2，N₂ → M1-R1
- 文件名：`delta_from_params.pth` → `m1_r2_model.pth`（可选）
- UI 文字统一

### Phase 7: 文档更新
- 更新 `ai-module1-status.md`
- 更新 `ai-module1-handoff-prompt.md`
- 更新 `ai-methods-handoff-prompt.md`
- 更新 `ai-methods-module1-detail.md`

---

## 十、数据需求

### 已有数据（可直接使用）
- `validation_predictions_n{n}.csv` — 验证集预测结果
- `training_data_n{n}.csv` — 训练数据
- `n{n}_metrics.json` / `delta_from_params_metrics.json` — 模型指标

### 需要新生成的数据
- **param-accuracy 对比数据**：对同一批验证样本，分别用 δ=0.5、δ=AI、δ=最优 运行 MDM，记录 (β̂, η̂, γ̂)
- **M1-R2 迭代数据**：`evaluate_route2.py` 的逐步输出

---

*本文档记录模块 1 前端页面重构的完整计划。*

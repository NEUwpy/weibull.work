# Task Plan: AI 关系建立页面重构 — 路线分离

## Goal
将 `ai/relationship/` 从单一 7-Tab 页面拆分为：总览页（两个路线卡片）+ 两个子页面（M1-R1 八 Tab / M1-R2 九 Tab）。

---

## 已确认决策

| 项目 | 决策 |
|------|------|
| 总览页内容 | 仅两个卡片，简洁风格 |
| URL 命名 | `/ai/relationship/m1-r1` 和 `/ai/relationship/m1-r2` |
| 术语统一 | N₂ → M1-R1，N₁ → M1-R2，不再使用 N₁/N₂ |
| 术语更新范围 | 代码文件名 + 文档内容 + 前端 UI 文字 |
| R1 Tab 数 | 8 个（原 Performance 拆为偏移量精度 + 三参数精度） |
| R2 Tab 数 | 9 个（额外多一个迭代过程 Tab） |
| 方法对比 Tab | 先空着 |

---

## 目标结构
```
ai/page.tsx                              ← AI 总览（不变）
ai/relationship/page.tsx                 ← 总览页（M1-R1 + M1-R2 两个卡片）
ai/relationship/m1-r1/page.tsx           ← 路线 1（直接学习），8 Tab
ai/relationship/m1-r1/components/        ← 路线 1 的 Tab 组件
ai/relationship/m1-r2/page.tsx           ← 路线 2（迭代逼近），9 Tab
ai/relationship/m1-r2/components/        ← 路线 2 的 Tab 组件
```

---

## M1-R1 Tab 结构（8 个）

| # | Tab ID | 名称 | 内容 | 组件来源 |
|---|--------|------|------|----------|
| 1 | theory | 原理说明 | 直接学习原理（样本→δ，N₂ 网络） | 改写现有 TheoryTab |
| 2 | training | 训练算法 | N₂ 网络结构、超参、训练策略 | 迁移现有 TrainingTab |
| 3 | data | 训练数据 | 数据生成、参数空间、分布 | 迁移现有 DataTab |
| 4 | delta-accuracy | 偏移量估计精度 | ① 真值→最优δ 散点图 ② 预测δ vs 最优δ 散点图 ③ 预测偏差统计 | 新建 |
| 5 | param-accuracy | 三参数估计精度 | δ=0.5 / AI δ / 真值最优δ 三种情况的 (β,η,γ) 绝对误差对比 | 新建 |
| 6 | playground | 在线使用 | 样本输入→AI 预测δ | 迁移现有 PlaygroundTab |
| 7 | verification | 可信性验证 | 真值、估计值、偏差 列表 | 改写现有 VerificationTab |
| 8 | compare | 方法对比 | 先空着 | 占位 |

### delta-accuracy Tab 细节
- 散点图 1：X=真值最优δ，Y=预测δ，对角线参考线
- 散点图 2：按 β/n 分组着色
- 偏差统计：均值、标准差、分位数、直方图

### param-accuracy Tab 细节
- 三种 δ 来源：
  1. δ=0.5（固定值）
  2. δ=AI 预测值（M1-R1 模型输出）
  3. δ=真值最优δ（搜索得到的最优）
- 每种情况的绝对误差：|β̂-β|, |η̂-η|, |γ̂-γ|
- 可按 β/n 分组展示

---

## M1-R2 Tab 结构（9 个）

| # | Tab ID | 名称 | 内容 | 组件来源 |
|---|--------|------|------|----------|
| 1 | theory | 原理说明 | 迭代逼近原理（δ₀→MDM→N₁→δ₁→...→收敛） | 新建 |
| 2 | training | 训练算法 | N₁ 网络结构、迭代算法、收敛判据 | 新建 |
| 3 | data | 训练数据 | 数据生成 | 新建或共享 |
| 4 | iteration | 迭代过程 | δ 收敛轨迹、收敛步数统计 | 新建 |
| 5 | delta-accuracy | 偏移量估计精度 | 同 R1 逻辑 | 新建 |
| 6 | param-accuracy | 三参数估计精度 | 同 R1 逻辑 | 新建 |
| 7 | playground | 在线使用 | 迭代演示 | 新建/占位 |
| 8 | verification | 可信性验证 | 同 R1 逻辑 | 新建 |
| 9 | compare | 方法对比 | 先空着 | 占位 |

---

## Phases
- [ ] Phase 1: 创建总览页 + 子页面路由结构
- [ ] Phase 2: 迁移 M1-R1 组件到 m1-r1/ 子目录
- [ ] Phase 3: 新建 M1-R1 的 delta-accuracy 和 param-accuracy Tab
- [ ] Phase 4: 创建 M1-R2 组件（占位/新建）
- [ ] Phase 5: 面包屑 + 导航调整
- [ ] Phase 6: 术语统一更新（文档 + 代码）
- [ ] Phase 7: 验证测试

## Status
**Phase 1** — 开始实现

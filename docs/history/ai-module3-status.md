# AI 模块 3 现状梳理：直接估计（端到端参数估计）

> **更新时间**: 2026-04-27
> **状态**: V2 完成 — 8 种预处理方案全部实验完成，泛化验证已完成
> **性质**: 探索性研究，验证 AI 端到端直接估计三参数的可行性与适用范围

---

## 〇、阶段性结论

**核心发现**：MLP 端到端直接估计 β、η、γ 可行，B-1 统一模型（填充+掩码）实用性最强。

**关键实验结论**：
1. **C-1 ≈ A-1** — 4 个统计量 [mean, std, min, max] 已充分提取 Weibull 参数信息
2. **B-1 统一模型可行** — 一个模型覆盖所有 n，精度与独立模型几乎相同
3. **A-2 对 η 变差** — 除以均值反而丢失尺度信息
4. **A-3 明显变差** — 去位置丢失绝对尺度信息，MAE(β) 几乎翻倍
5. **C-2/C-3 无额外优势** — 偏度/峰度/中位数/Q1/Q3/IQR/CV 未提供新信息
6. **B-2 ≈ B-1** — 除以均值+掩码与原始+掩码精度相当

**泛化验证结论**：
7. **插值精度略降** — 插值集 MAE(β) 比组内高约 20-30%
8. **外推精度大幅下降** — 外推集 MAE(β) 是组内的 8-10 倍
9. **a2/b2 外推爆炸** — 除以均值预处理在外推时产生极大值（MAE(β) 达 10^10）
10. **a1/b1/c1/c2 外推相对稳健** — 虽精度下降，但输出仍在合理范围

**已完成**：数据生成、8 种方案训练、后端 API、前端 7-Tab 页面、泛化评估——基础设施完备。

**待做**：AI vs 传统方法对比（MLE/MDM）、扩大参数空间、架构实验。

---

## 一、模块 3 做了什么（一句话）

训练了一个神经网络，输入一组失效时间样本 [t1, ..., tn]，直接输出 Weibull 三参数估计值 (β̂, η̂, γ̂)，无迭代优化。

---

## 二、整体流程

```
离线（已完成）:
  蒙特卡洛模拟生成 Weibull 样本（β×η×γ×n，MC=500）
    → 8 种预处理方案分别生成训练数据
    → PyTorch MLP 训练（按 n 独立模型 / 统一模型）
    → 泛化评估（组内/插值/外推三类测试集）

在线（已部署）:
  用户输入样本 → 选择方案 → API 调用 → 模型推理 → 输出 (β̂, η̂, γ̂)
```

---

## 三、三大方案组、8 种预处理

### 方案 A：独立模型（按 n 分别训练）

| 子选项 | 输入形式 | 说明 | 结论 |
|--------|---------|------|------|
| A-1 原始样本 | [t1, t2, ..., tn] | 最简单，网络自己学尺度不变性 | **基线方案** |
| A-2 除以均值 | [t1/t̄, t2/t̄, ..., tn/t̄, t̄] | 消 η 影响，t̄ 保留 η 信息 | 对 η 变差 |
| A-3 去位置 | [t1-t_min, t2-t_min, ..., tn-t_min] | 消 γ，网络只学 β 和 η | 明显变差 |

### 方案 B：填充+掩码（统一模型覆盖所有 n）

| 子选项 | 输入形式 | 说明 | 结论 |
|--------|---------|------|------|
| B-1 原始+掩码 | [t1,...,tn,0,...,0, mask] | 补零到 n_max=15，掩码标记真实数据 | **最优方案** |
| B-2 除以均值+掩码 | [t1/t̄,...,tn/t̄,0,...,0, t̄, mask] | 消 η + 掩码 | ≈ B-1 |

### 方案 C：统计量输入（维度固定，与 n 无关）

| 子选项 | 输入特征 | 说明 | 结论 |
|--------|---------|------|------|
| C-1 基础 | [t̄, s, t_min, t_max] | 4 个特征 | ≈ A-1 |
| C-2 扩展 | C-1 + [偏度, 峰度, 中位数] | 7 个特征 | 无额外优势 |
| C-3 最大化 | C-2 + [Q1, Q3, IQR, CV] | 11 个特征 | ≈ C-1 |

---

## 四、已确认的设计决策

| 项目 | 决策 |
|------|------|
| 架构 | MLP: Linear(n, 128)→ReLU→Linear(128, 64)→ReLU→Linear(64, 32)→ReLU→Linear(32, 3) |
| 损失函数 | 归一化 MSE（输出 y 归一化为零均值单位方差，推理时反归一化） |
| 踩坑 | 最初用相对 MSE + 原始 y 值，η(100-5000) 和 β(0.5-5) 量纲差距太大，改为归一化后解决 |
| 变长输入 | 按 n 分别训练独立模型（方案 A/C）；填充+掩码统一模型（方案 B） |
| 输出 | 线性输出层，3 个值对应 (β̂, η̂, γ̂) |
| 训练超参 | Adam, lr=0.001, batch=64, ReduceLROnPlateau, 早停 patience=50 |

---

## 五、参数空间与数据规模

### V2 参数空间（当前）

| 参数 | 取值 | 数量 |
|------|------|------|
| β | {0.5, 1.0, 2.0, 3.0, 5.0} | 5 |
| η | {100, 500, 1000, 3000, 5000} | 5 |
| γ | {0, 50, 100, 200} | 4 |
| n | {5, 7, 10, 15} | 4 |
| MC | 500 | — |
| **总组合** | 5×5×4×4 = **400 组** | |
| **总样本** | 400 × 500 = **200,000 条** | |

### 泛化测试数据

| 类型 | 标记 | 参数组合来源 | 条数 |
|------|------|-------------|------|
| 组内 (in_group) | ig | 训练集参数组合 | ~40,000 |
| 插值 (interpolation) | ip | 训练点之间的新组合 | ~19,200 |
| 外推 (extrapolation) | ex | 训练范围外的组合 | ~8,400 |

---

## 六、全部方案精度对比

### 组内验证精度（验证集 20% 随机划分）

| 方案 | n=5 MAE(β) | n=7 MAE(β) | n=10 MAE(β) | n=15 MAE(β) | n=5 MAE(η) | n=10 MAE(η) | n=15 MAE(η) |
|------|-----------|-----------|------------|------------|-----------|------------|------------|
| A-1  | 0.587     | 0.505     | 0.390      | 0.304      | 363.9     | 268.0      | 210.5      |
| A-2  | 0.573     | 0.489     | 0.381      | 0.296      | 413.7     | 314.2      | 252.8      |
| A-3  | 0.972     | 0.871     | 0.684      | 0.554      | 693.2     | 513.7      | 407.3      |
| B-1  | 0.560     | 0.473     | 0.382      | 0.295      | 360.3     | 248.2      | 208.0      |
| B-2  | 0.560     | 0.473     | 0.382      | 0.295      | 360.3     | 248.2      | 208.0      |
| C-1  | 0.599     | 0.491     | 0.380      | 0.284      | 380.6     | 263.5      | 205.7      |
| C-2  | 0.599     | 0.491     | 0.380      | 0.284      | 380.6     | 263.5      | 205.7      |
| C-3  | 0.600     | 0.491     | 0.380      | 0.284      | 380.6     | 263.5      | 205.7      |

### 泛化验证精度（B-1 方案示例）

| 验证类型 | MAE(β) | 说明 |
|---------|--------|------|
| 组内 (ig) | 0.455 | 基线精度 |
| 插值 (ip) | 0.578 | 比组内高 ~27% |
| 外推 (ex) | 大幅下降 | 8-10 倍，符合预期 |

---

## 七、文件清单

### 7.1 训练数据生成

| 文件 | 说明 |
|------|------|
| `python/studies/direct_estimation/generate_training_data.py` | 蒙特卡洛模拟 + 生成训练数据 |
| `python/studies/direct_estimation/generate_test_data.py` | 泛化测试数据生成（ig/ip/ex 三类） |
| `python/studies/direct_estimation/data/training_data_n{5,7,10,15}.csv` | A-1 训练集 |
| `python/studies/direct_estimation/data/test_data_{ig,ip,ex}_n{5,7,10,15}.csv` | 泛化测试集 |

### 7.2 模型训练

| 文件 | 说明 |
|------|------|
| `python/studies/direct_estimation/train_model.py` | PyTorch 训练脚本（支持全部 8 种预处理） |
| `python/models/direct_estimation/n{5,7,10,15}_model.pth` | A-1 模型 |
| `python/models/direct_estimation/n{5,7,10,15}_a2_model.pth` | A-2 模型 |
| `python/models/direct_estimation/n{5,7,10,15}_a3_model.pth` | A-3 模型 |
| `python/models/direct_estimation/b1_model.pth` | B-1 统一模型 |
| `python/models/direct_estimation/b2_model.pth` | B-2 统一模型 |
| `python/models/direct_estimation/n{5,7,10,15}_c{1,2,3}_model.pth` | C-1/C-2/C-3 模型 |
| `python/models/direct_estimation/*_metrics.json` | 各模型训练指标 |

### 7.3 泛化评估

| 文件 | 说明 |
|------|------|
| `python/studies/direct_estimation/evaluate_generalization.py` | 泛化评估脚本 |
| `python/studies/direct_estimation/generate_preprocessed_data.py` | 预处理数据生成（前端用） |

### 7.4 后端 API

| 文件 | 位置 | 说明 |
|------|------|------|
| `python/main.py` | 直接估计 API 部分 | `POST /ai/direct-estimation` |

### 7.5 前端页面

| 文件 | 说明 |
|------|------|
| `src/app/ai/direct-estimation/page.tsx` | 方案选择页（8 个子选项） |
| `src/app/ai/direct-estimation/[scheme]/page.tsx` | 7-Tab 详情页（动态路由） |
| `src/app/ai/direct-estimation/components/TheoryTab.tsx` | 原理说明 |
| `src/app/ai/direct-estimation/components/TrainingTab.tsx` | 训练算法（Loss 曲线） |
| `src/app/ai/direct-estimation/components/DataTab.tsx` | 训练数据 |
| `src/app/ai/direct-estimation/components/PlaygroundTab.tsx` | 在线使用 |
| `src/app/ai/direct-estimation/components/PerformanceTab.tsx` | 性能展示（散点图+直方图+精度表） |
| `src/app/ai/direct-estimation/components/VerificationTab.tsx` | 可信性验证（精度汇总+验证类型切换） |
| `src/app/ai/direct-estimation/components/CompareTab.tsx` | 方法对比（8 方案横向对比+折线图） |
| `src/components/ai/charts/BoxPlot.tsx` | 箱线图组件（新增） |

### 7.6 前端数据（public/ai/data/）

| 文件模式 | 说明 |
|---------|------|
| `direct_estimation_*_metrics.json` | 各方案模型指标 |
| `direct_estimation_*_preprocessed.json` | 预处理数据（8 个） |
| `direct_estimation_training_history_*.csv` | 训练历史 |
| `direct_estimation_validation_predictions_*.csv` | 验证集预测 |
| `direct_estimation_generalization_metrics.json` | 泛化评估结果 |

---

## 八、前端页面结构

### 方案选择页 `/ai/direct-estimation`

展示 A/B/C 三大方案组，每组下列出所有预处理子选项（含状态标记）。点击进入对应 7-Tab 详情页。

### 7-Tab 详情页 `/ai/direct-estimation/[scheme]`

| # | Tab | 状态 | 核心内容 |
|---|-----|------|---------|
| 1 | 原理说明 | ✅ | 方案原理、网络架构、参数空间 |
| 2 | 训练算法 | ✅ | Loss 曲线、超参数、指标汇总 |
| 3 | 训练数据 | ✅ | 参数空间表格、数据规模 |
| 4 | 在线使用 | ✅ | 样本输入 → AI 预测 (β,η,γ) |
| 5 | 性能展示 | ✅ | 散点图、直方图、按 n/β/η 维度精度表、验证类型切换 |
| 6 | 可信性验证 | ✅ | 精度汇总表（MAE/MRE 切换）、验证类型切换（组内/插值/外推） |
| 7 | 方法对比 | ✅ | 8 方案横向对比表、MAE 按 n 折线图、7 条实验结论 |

---

## 九、端到端调用链路

```
用户浏览器
  ↓ 选择方案（如 B-1）+ 填写失效时间数据
  ↓ 点击"AI 预测参数"
  ↓
src/app/ai/direct-estimation/components/PlaygroundTab.tsx
  ↓ fetch POST /ai/direct-estimation
  ↓
python/main.py → ai_direct_estimation()
  ↓ _load_direct_estimation_model(scheme, n)
  ↓ 按方案预处理 → PyTorch 推理 → 反归一化
  ↓
返回 { beta, eta, gamma, scheme, confidence }
  ↓
前端展示三参数估计值 + 置信度
```

---

## 十、下一步方向

### 已完成

1. ✅ 8 种预处理方案全部实验（A-1/A-2/A-3/B-1/B-2/C-1/C-2/C-3）
2. ✅ V2 参数空间扩展（γ∈{0,50,100,200}，200k 训练数据）
3. ✅ 泛化验证（组内/插值/外推三类测试集）
4. ✅ 前端方案选择 + 7-Tab 详情页 + 可视化优化

### 后续方向

5. **AI vs 传统方法对比** — 与 MLE、MDM 在同参数空间下的精度对比
6. **扩大参数空间** — 更多 β/η 值、更多 n（如 n=20, 30）
7. **网络架构实验** — 更宽/更深/BatchNorm/Dropout
8. **截尾数据处理** — 当前仅支持完全样本，后续可扩展

---

## 十一、历史文档

已完成的设计文档和任务记录已移至 `docs/history/`：
- `ai-direct-estimation-design.md` — 完整设计方案（含所有方案细节）
- `ai-direct-estimation-tasks.md` — 任务进度清单（8 个阶段）
- `ai-direct-estimation-v2-plan.md` — V2 规划（γ≠0 + 泛化验证）
- `ai-direct-estimation-handoff-prompt.md` — 旧版衔接提示词

---

*本文档记录模块 3 截至 2026-04-27 的阶段性总结。V2 已完成，基础设施完备，后续方向为 AI vs 传统方法对比和参数空间扩展。*

# AI 模块 1 交接提示词（2026-04-27）

> **用途**：在新窗口中继续 AI 模块 1 的工作
> **当前状态**：前端页面重构完成（路线分离），所有 17 个 Tab 已填充真实数据，M1-R2 评估完成，param-accuracy 三-way 对比已生成
> **下一步重点**：边界过滤修复 + 搜索策略优化（Brent 法）

---

## 背景

Weibull 分析平台（weibull.work）的 **AI 模块 1**（MDM 偏移量 δ 优化）。

**核心问题**：MDM 方法需要偏移量 δ，不同样本最优 δ 不同。用神经网络学习"参数→最优 δ"的映射。

**两条路线**（术语已更新，不再使用 N₁/N₂）：
- **M1-R1（路线 1）**：样本 → 直接预测 δ（按 n 分模型，已训练，当前可用）
- **M1-R2（路线 2）**：δ₀=0.5 → MDM → N₁(β̂,η̂,γ̂) → δ₁ → ... → 收敛

---

## 术语规范

| 术语 | 全称 | 含义 | 旧称 |
|------|------|------|------|
| M1-R1 | Model 1 - Route 1 | 直接学习（样本→δ，N₂ 网络） | N₂ / 路线 1 |
| M1-R2 | Model 1 - Route 2 | 迭代逼近（δ₀→MDM→N₁→δ₁→...） | N₁ / 路线 2 |

**规则**：所有代码、文档、UI 中不再使用 N₁/N₂，统一为 M1-R1/M1-R2。

---

## 已完成的工作

### 数据生成（已完成）
- 参数空间：β∈{1,2,5}, η∈{100,1000,5000}, γ=1000, n∈{5,7,10,15,20}, MC=500
- 45 组 × 500 MC = 22,500 总样本，12,597 有效（成功率 56.0%）
- 数据文件：`python/studies/mdm_delta/data/training_data_n{5,7,10,15,20}.csv`
- 已同步到 `public/ai/data/`

### M1-R1 模型训练（已完成，5 个 n 值）

| n | 验证 MSE | MAE | RMSE | 验证集 | 早停 |
|---|---------|-----|------|--------|------|
| 5 | 0.0279 | 0.104 | 0.167 | 483 | 92 |
| 7 | **0.0275** | **0.100** | **0.166** | 499 | 109 |
| 10 | 0.0340 | 0.113 | 0.184 | 515 | 170 |
| 15 | 0.0335 | 0.110 | 0.183 | 508 | 76 |
| 20 | 0.0305 | 0.105 | 0.175 | 513 | 96 |

### M1-R2 模型训练（已完成，β 扩展后改善）

| 指标 | 旧值（β=2 only） | 新值（β={1,2,5}） |
|------|-------------------|-------------------|
| MSE | 0.053 | 0.052 |
| 预测范围 | [0.246, 0.295]（恒定） | [0.036, 0.814]（有变化） |
| 早停 epoch | 29 | 29 |

### M1-R2 评估（已完成）

运行 `evaluate_route2.py --test-samples 50 --betas 1,2,5`，结果：
- **收敛率**：74-80%（各 n 值）
- **平均迭代步数**：5.7-6.7 步
- **Route 2 vs 固定 δ**：小样本 (n=5) 不如固定 δ（MSE 3.72 vs 2.00），大样本 (n=20) 优于固定 δ（MSE 0.49 vs 0.76）
- 输出文件：`route2_convergence.csv` (2250 条)、`route2_iteration_traces.csv` (1068 条)

### param-accuracy 三-way 对比（已完成）

运行 `generate_param_accuracy.py`，对 45 个验证组合分别用 δ=0.5、δ=AI、δ=网格搜索最优 运行 MDM：
- 输出文件：`param_accuracy_comparison.csv` (45 条)
- AI δ 在多数情况下优于固定 δ=0.5，但与最优 δ 仍有差距

### 前端页面重构（已完成）

`ai/relationship/` 已拆分为：
- `/ai/relationship/` — 总览页（两个卡片）
- `/ai/relationship/m1-r1/` — M1-R1 子页面（8 Tab）
- `/ai/relationship/m1-r2/` — M1-R2 子页面（9 Tab）

**所有 17 个 Tab 已填充真实数据**（无占位 Tab）。

---

## 待做任务（按优先级）

### 任务 1：边界过滤修复（高优先级）

`generate_training_data.py` 第 328-329 行：
```python
if is_boundary:
    optimal_delta = None  # 边界最优 → 当作"无解"丢弃
```

- ~44% 样本被过滤（主要是最优 δ 趋近 0.001 边界的情况）
- MSE-δ 曲线分析：大部分 n≤10 样本最优 δ 就是 0，n=20 才需要正 δ
- **待决定**：去掉边界过滤？或 delta_min 改为 0？

### 任务 2：搜索策略优化（高优先级）

当前粗搜+细搜 31 次 MDM 调用。MSE(δ) 曲线 11/12 单峰，可用 Brent 法减到 ~10-15 次。

### 任务 3：模型改进（低优先级）

更深网络、学习率调度、数据增强。

### 任务 4：ONNX 导出（低优先级）

减少 PyTorch 依赖。

### 任务 5：截尾支持（低优先级）

处理不完全样本（Type II censoring）。

---

## 关键文件清单

### 后端脚本
| 文件 | 说明 |
|------|------|
| `python/studies/mdm_delta/generate_training_data.py` | 训练数据生成（有边界过滤） |
| `python/studies/mdm_delta/generate_comparison_data.py` | 对比数据生成（betas 已更新为 [1,2,5]） |
| `python/studies/mdm_delta/generate_param_accuracy.py` | param-accuracy 三-way 对比数据生成 |
| `python/studies/mdm_delta/train_model.py` | M1-R1/M1-R2 模型训练 |
| `python/studies/mdm_delta/evaluate_route2.py` | M1-R2 评估脚本（含迭代轨迹输出） |
| `python/studies/mdm_delta/plot_mse_delta_curve.py` | MSE-δ 曲线分析 |

### 模型文件
| 文件 | 说明 |
|------|------|
| `python/models/mdm_delta/n{5,7,10,15,20}_model.pth` | M1-R1 模型（路线 1，当前可用） |
| `python/models/mdm_delta/delta_from_params.pth` | M1-R2 模型（路线 2，已重新训练） |

### 前端数据文件（public/ai/data/）
| 文件 | 说明 | 记录数 |
|------|------|--------|
| `training_data_n{5,7,10,15,20}.csv` | M1-R1 训练数据 | 12,597 总 |
| `validation_predictions_n{5,7,10,15,20}.csv` | M1-R1 验证预测 | ~500/n |
| `delta_from_params_metrics.json` | M1-R2 训练指标 | — |
| `route2_convergence.csv` | M1-R2 收敛详情（含 est_beta/eta/gamma） | 2,250 |
| `route2_iteration_traces.csv` | M1-R2 迭代轨迹 | 1,068 |
| `route2_comparison.csv` | M1-R2 vs 固定 δ 对比 | 5 |
| `param_accuracy_comparison.csv` | M1-R1 三-way 对比（δ=0.5/AI/最优） | 45 |
| `verification_cases.csv` | M1-R1 验证案例 | 45 |
| `comparison_ai_vs_fixed.csv` | M1-R1 AI vs 固定 δ | 2,250 |

### 前端页面
| 文件 | 说明 |
|------|------|
| `src/app/ai/relationship/page.tsx` | 总览页（两个卡片） |
| `src/app/ai/relationship/m1-r1/page.tsx` | M1-R1 子页面（8 Tab） |
| `src/app/ai/relationship/m1-r1/components/` | M1-R1 Tab 组件（8 个） |
| `src/app/ai/relationship/m1-r2/page.tsx` | M1-R2 子页面（9 Tab） |
| `src/app/ai/relationship/m1-r2/components/` | M1-R2 Tab 组件（9 个） |

### 文档
| 文件 | 说明 |
|------|------|
| `docs/ai-module1-status.md` | 完整状态文档（最重要） |
| `docs/ai-module1-route2-results.md` | M1-R2 实验结果 |
| `docs/ai-methods-module1-detail.md` | 完整技术方案 |

---

## 设计决策

| 决策 | 值 | 说明 |
|------|-----|------|
| 指标方案 | 相对 MSE | (β̂-β)²/β² + (η̂-η)²/η² + (γ̂-γ)²/γ² |
| δ 搜索范围 | [0.001, 1.00] | 粗搜(0.1)+细搜(0.01) |
| M1-R1 架构 | Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid |
| M1-R2 架构 | Linear(3,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→Sigmoid |
| M1-R2 收敛 | |δ_new - δ_old| < 0.001，最大 10 步 |
| M1-R2 初始 δ₀ | 0.5 |
| 参数空间 | β∈{1,2,5}, η∈{100,1000,5000}, γ=1000, n∈{5,7,10,15,20} |
| 页面 URL | `/ai/relationship/m1-r1` 和 `/ai/relationship/m1-r2` |

---

## 注意事项

1. **Windows GBK 编码**：Python print 中 δ, →, ± 等 Unicode 字符在终端显示为乱码
2. **PyTorch CPU**：无需 GPU
3. **边界过滤**：当前 ~44% 样本被丢弃，是最大的数据质量问题
4. **M1-R2 早停快**：epoch 29 就停了，可能需要调整 patience 或增大模型容量
5. **术语统一**：不再使用 N₁/N₂，统一为 M1-R1/M1-R2

---

*本文档记录模块 1 截至 2026-04-27 的完整实现状态和下一步任务。*

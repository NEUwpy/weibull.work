# AI 模块 1 交接提示词（2026-04-26）

> **用途**：在新窗口中继续 AI 模块 1 的工作
> **当前状态**：路线 2 因 β 固定而失败，需要扩展 β 到 {1, 2, 5} 重新实验

---

## 背景

Weibull 分析平台（weibull.work）的 **AI 模块 1**（MDM 偏移量 δ 优化）。

**核心问题**：MDM 方法需要偏移量 δ，不同样本最优 δ 不同。用神经网络学习"参数→最优 δ"的映射。

**两条路线**：
- **路线 1（N₂）**：样本 → 直接预测 δ（按 n 分模型，已训练，可用但有过拟合问题）
- **路线 2（N₁ 迭代）**：δ₀=0.5 → MDM → N₁(β̂,η̂,γ̂) → δ₁ → ... → 收敛（**因 β 固定而失败**）

---

## 已完成的工作

### 数据生成（已完成）
- 参数空间：β=2, η∈{100,1000,5000}, γ=1000, n∈{5,7,10,15,20}, MC=500
- 生成 4,391 条有效样本（成功率 58.5%）
- 数据文件：`python/studies/mdm_delta/data/training_data_n{5,7,10,15,20}.csv`

### N₂ 模型训练（已完成，5 个 n 值）
| n | 验证 MSE | MAE | RMSE |
|---|---------|-----|------|
| 5 | 0.01859 | 0.084 | 0.136 |
| 7 | 0.00688 | 0.054 | 0.083 |
| 10 | 0.00984 | 0.065 | 0.099 |
| 15 | 0.01350 | 0.076 | 0.116 |
| 20 | 0.01572 | 0.085 | 0.125 |

### N₁ 模型训练（失败）
- MSE=0.053, 预测范围 [0.25, 0.29]（恒定输出）
- 原因：β=2 固定时，η 与最优 δ 无强相关

### 路线 2 评估（已完成）
- `evaluate_route2.py` 已创建
- 结果：Route2 MSE 比固定 δ=0.2 高 2-7 倍

### 前端（已更新）
- 所有组件支持 n=10, n=20
- CompareTab 新增 Route 2 对比表（C5）
- 数据已复制到 `public/ai/data/`

---

## 下一步：扩展 β 重新实验

### 问题
β=2 固定时，N₁ 只有 η 一个有效输入，而 η 与 δ 无强相关（三个 η 的 δ 均值 0.23, 0.23, 0.25）。N₁ 退化为常数预测器。

### 解决方案
扩展 β 到 {1, 2, 5}，让 N₁ 有 3 个有效输入维度。

### 执行步骤

#### Step 1: 重新生成训练数据
```bash
cd python/studies/mdm_delta

# 扩展 β 到 {1, 2, 5}，其他参数不变
python generate_training_data.py --betas 1,2,5 --etas 100,1000,5000 --sample-sizes 5,7,10,15,20 --mc-runs 500

# 预期：3×3×5 = 45 组 × 500 = 22,500 样本
# 耗时：~4-6 小时（每个组合约 5-8 分钟）
```

#### Step 2: 重新训练 N₁
```bash
python train_model.py --model-type n1 --epochs 300 --batch-size 32

# 预期：N₁ 现在有 β, η, γ 三个有效输入，应该能学到有意义的映射
```

#### Step 3: 重新训练 N₂（可选）
```bash
python train_model.py --model-type n2 --epochs 300

# N₂ 按 n 分模型，β 扩展后每个模型的训练数据增加 3 倍
```

#### Step 4: 重新评估路线 2
```bash
python evaluate_route2.py --test-samples 100 --betas 1,2,5

# 预期：N₁ 能学到 β→δ 的关系，迭代收敛到更好的 δ
```

#### Step 5: 生成对比数据并更新前端
```bash
python generate_comparison_data.py
python copy_data_to_public.py
```

---

## 关键文件清单

### 文档
| 文件 | 说明 |
|------|------|
| `docs/ai-methods-module1-detail.md` | 完整技术方案 |
| `docs/ai-module1-investigation.md` | 问题调查与修复计划 |
| `docs/ai-module1-route2-results.md` | **路线 2 实验结果（重要）** |
| `docs/ai-module1-status.md` | 状态文档 |
| `route2_plan.md` | 路线 2 实施计划 |
| `route2_notes.md` | 研究笔记 |

### 后端
| 文件 | 说明 |
|------|------|
| `python/studies/mdm_delta/generate_training_data.py` | 训练数据生成（支持 `--betas` 参数）|
| `python/studies/mdm_delta/train_model.py` | N₁/N₂ 模型训练 |
| `python/studies/mdm_delta/evaluate_route2.py` | 路线 2 评估脚本 |
| `python/studies/mdm_delta/generate_comparison_data.py` | 对比数据生成 |
| `python/studies/mdm_delta/copy_data_to_public.py` | 复制到前端 |
| `python/main.py` | API 端点（路线 1 + 路线 2）|

### 模型
| 文件 | 说明 |
|------|------|
| `python/models/mdm_delta/n{5,7,10,15,20}_model.pth` | N₂ 模型（路线 1，当前可用）|
| `python/models/mdm_delta/delta_from_params.pth` | N₁ 模型（路线 2，恒定输出，需重新训练）|

### 前端
| 文件 | 说明 |
|------|------|
| `src/app/ai/relationship/page.tsx` | 7 个 Tab 框架 |
| `src/app/ai/relationship/components/CompareTab.tsx` | 方法对比（含 C5 Route 2 对比）|
| `src/app/ai/relationship/components/PlaygroundTab.tsx` | 在线使用（路线 1 + 路线 2 切换）|

---

## 设计决策记录

| 决策 | 值 | 说明 |
|------|-----|------|
| 指标方案 | 相对 MSE | (β̂-β)²/β² + (η̂-η)²/η² + (γ̂-γ)²/γ² |
| δ 搜索范围 | [0.001, 1.00] | 粗搜+细搜模式 |
| N₂ 架构 | Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid |
| N₁ 架构 | Linear(3,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→Sigmoid |
| 路线 2 收敛条件 | \|δ_new - δ_old\| < 0.001，最大 10 步 |
| 路线 2 初始 δ₀ | 0.5 |

---

## 注意事项

1. **Windows GBK 编码**：Python print 中不能用 δ, →, ± 等 Unicode 字符
2. **PyTorch CPU**：无需 GPU
3. **训练时间**：β 扩展后数据量增加 3 倍，数据生成约 4-6 小时
4. **N₁ 训练 batch size**：使用 `--batch-size 32` 避免 batch size 警告
5. **已有 N₂ 模型**：当前的 N₂ 模型（β=2 only）仍然可用，可以先用着

---

## 快速启动

```bash
# 查看当前状态
cd python/studies/mdm_delta
cat data/summary.json

# 测试现有 N₂ 模型
python -c "
import torch
model = torch.load('../models/mdm_delta/n5_model.pth', map_location='cpu', weights_only=False)
print('N2 n=5 metrics:', model['metrics'])
"

# 开始扩展 β 实验
python generate_training_data.py --betas 1,2,5 --mc-runs 500
```

# AI 模块 1 交接提示词（2026-04-27）

> **用途**：在新窗口中继续 AI 模块 1 的工作
> **当前状态**：β={1,2,5} 数据生成完成，N₁/N₂ 已重新训练，前端数据已同步

---

## 背景

Weibull 分析平台（weibull.work）的 **AI 模块 1**（MDM 偏移量 δ 优化）。

**核心问题**：MDM 方法需要偏移量 δ，不同样本最优 δ 不同。用神经网络学习"参数→最优 δ"的映射。

**两条路线**：
- **路线 1（N₂）**：样本 → 直接预测 δ（按 n 分模型，已训练，当前可用）
- **路线 2（N₁ 迭代）**：δ₀=0.5 → MDM → N₁(β̂,η̂,γ̂) → δ₁ → ... → 收敛

---

## 已完成的工作

### 数据生成（已完成）
- 参数空间：β∈{1,2,5}, η∈{100,1000,5000}, γ=1000, n∈{5,7,10,15,20}, MC=500
- 45 组 × 500 MC = 22,500 总样本，12,597 有效（成功率 56.0%）
- 数据文件：`python/studies/mdm_delta/data/training_data_n{5,7,10,15,20}.csv`
- 已同步到 `public/ai/data/`

### N₂ 模型训练（已完成，5 个 n 值）

| n | 验证 MSE | MAE | RMSE | 验证集 | 早停 |
|---|---------|-----|------|--------|------|
| 5 | 0.0279 | 0.104 | 0.167 | 483 | 92 |
| 7 | **0.0275** | **0.100** | **0.166** | 499 | 109 |
| 10 | 0.0340 | 0.113 | 0.184 | 515 | 170 |
| 15 | 0.0335 | 0.110 | 0.183 | 508 | 76 |
| 20 | 0.0305 | 0.105 | 0.175 | 513 | 96 |

### N₁ 模型训练（已完成，β 扩展后改善）

| 指标 | 旧值（β=2 only） | 新值（β={1,2,5}） |
|------|-------------------|-------------------|
| MSE | 0.053 | 0.052 |
| 预测范围 | [0.246, 0.295]（恒定） | [0.036, 0.814]（有变化） |
| 早停 epoch | 29 | 29 |

旧 N₁ 是常数预测器（β=2 固定时 η 与 δ 无强相关）。新 N₁ 预测范围显著扩大，不再是常数。

### 前端（已同步）
- `public/ai/data/` 已更新为 β={1,2,5} 新数据
- 模型指标 JSON 已同步
- 验证数据已重新生成（45 个验证案例 + 8 个边界测试）

---

## 待解决问题

### 1. 边界过滤问题（重要）

`generate_training_data.py` 第 328-329 行：
```python
if is_boundary:
    optimal_delta = None  # 边界最优 → 当作"无解"丢弃
```

- ~44% 样本被过滤（主要是最优 δ 趋近 0.001 边界的情况）
- MSE-δ 曲线分析：大部分 n≤10 样本最优 δ 就是 0，n=20 才需要正 δ
- **待决定**：去掉边界过滤？或 delta_min 改为 0？

### 2. 路线 2 待重新评估

N₁ 已用新数据重新训练，不再是常数预测器。需要运行：
```bash
cd python/studies/mdm_delta
python evaluate_route2.py --test-samples 100 --betas 1,2,5
```

### 3. 搜索策略优化

当前粗搜+细搜 31 次 MDM 调用。MSE(δ) 曲线 11/12 单峰，可用 Brent 法减到 ~10-15 次。

---

## 关键文件清单

### 后端脚本
| 文件 | 说明 |
|------|------|
| `python/studies/mdm_delta/generate_training_data.py` | 训练数据生成（有边界过滤） |
| `python/studies/mdm_delta/train_model.py` | N₁/N₂ 模型训练 |
| `python/studies/mdm_delta/evaluate_route2.py` | 路线 2 评估脚本 |
| `python/studies/mdm_delta/plot_mse_delta_curve.py` | MSE-δ 曲线分析 |

### 模型文件
| 文件 | 说明 |
|------|------|
| `python/models/mdm_delta/n{5,7,10,15,20}_model.pth` | N₂ 模型（路线 1，当前可用） |
| `python/models/mdm_delta/delta_from_params.pth` | N₁ 模型（路线 2，已重新训练） |

### 训练数据
| 文件 | 说明 |
|------|------|
| `python/studies/mdm_delta/data/training_data_n{5,7,10,15,20}.csv` | 按 n 分文件 |
| `python/studies/mdm_delta/data/training_data_all.csv` | 全量合并（12,597 条） |
| `python/studies/mdm_delta/data/summary.json` | 生成统计 |
| `python/studies/mdm_delta/data/mse_curves/` | MSE-δ 曲线数据 |

### 文档
| 文件 | 说明 |
|------|------|
| `docs/ai-module1-status.md` | 完整状态文档（已更新） |
| `docs/ai-module1-route2-results.md` | 路线 2 实验结果（待更新） |
| `docs/ai-methods-module1-detail.md` | 完整技术方案 |

---

## 设计决策

| 决策 | 值 | 说明 |
|------|-----|------|
| 指标方案 | 相对 MSE | (β̂-β)²/β² + (η̂-η)²/η² + (γ̂-γ)²/γ² |
| δ 搜索范围 | [0.001, 1.00] | 粗搜(0.1)+细搜(0.01) |
| N₂ 架构 | Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid |
| N₁ 架构 | Linear(3,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→Sigmoid |
| 路线 2 收敛 | |δ_new - δ_old| < 0.001，最大 10 步 |
| 路线 2 初始 δ₀ | 0.5 |
| 参数空间 | β∈{1,2,5}, η∈{100,1000,5000}, γ=1000, n∈{5,7,10,15,20} |

---

## 快速启动

```bash
# 查看当前状态
cd python/studies/mdm_delta
cat data/summary.json

# 评估路线 2（下一步）
python evaluate_route2.py --test-samples 100 --betas 1,2,5

# 测试 N₂ 模型
python -c "
import torch
model = torch.load('../models/mdm_delta/n5_model.pth', map_location='cpu', weights_only=False)
print('N2 n=5 metrics:', model['metrics'])
"
```

---

## 注意事项

1. **Windows GBK 编码**：Python print 中 δ, →, ± 等 Unicode 字符在终端显示为乱码
2. **PyTorch CPU**：无需 GPU
3. **边界过滤**：当前 ~44% 样本被丢弃，是最大的数据质量问题
4. **N₁ 早停快**：epoch 29 就停了，可能需要调整 patience 或增大模型容量

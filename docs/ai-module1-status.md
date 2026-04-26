# AI 模块 1 现状梳理：MDM 偏移量 δ 优化

> **更新时间**: 2026-04-26
> **状态**: 方案重新讨论中（原型已完成，正在梳理完整设计）
> **详细方案**: [ai-methods-module1-detail.md](ai-methods-module1-detail.md)

---

## 〇、当前讨论进展

**已完成的讨论**：
- [x] 研究目的的逻辑链条（现状→问题→尝试→瓶颈→路线）
- [x] 两条研究路线：路线 1（直接学习）和路线 2（迭代逼近）
- [x] 神经网络分支结构：N₁（公共，真值→δ）+ N₂（路线1，样本→δ）
- [x] 指标方案：5 种方案做对比
- [x] 参数空间：β∈{1,2,5}, η∈{100,1000,5000}, γ=1000, n∈{5,7,15}, MC=500
- [x] 路线 2 收敛判据：方案 C（δ<0.001 / 最大10步 / MDM失败）
- [x] 路线 2 初始 δ₀ = 0.5
- [x] 可视化方案：27 个图表，按 Tab 分组，组件复用

**待讨论**：
（无，方案全部确认）

**讨论规则**：随着讨论深入，更新 detail.md（方案）和本文件（状态）。

---

## 一、模块 1 做了什么（一句话）

训练了一个神经网络，输入一组失效时间样本，直接输出 MDM 方法应使用的最优偏移量 δ，替代人工反复尝试。

---

## 二、整体流程

```
离线（已完成）:
  蒙特卡洛模拟生成 Weibull 样本
    → 对每个样本遍历 50 个 δ 值 [0.01, 0.02, ..., 0.50]
    → 每个 δ 运行 MDM 得到 est_β, est_η, est_γ
    → 用 MSE(β,η,γ) 选出最优 δ*
    → 训练 PyTorch MLP 学习"样本 → δ*"的映射

在线（已部署）:
  用户输入样本 → API 调用 → 模型推理 → 输出最优 δ
```

---

## 三、已确认的设计决策

### 原型决策（已完成，待讨论是否调整）

| 项目 | 原型决策 | 讨论状态 |
|------|----------|----------|
| 最优评价标准 | MSE(β,η,γ) | 待讨论：计划设多种方案对比 |
| 框架 | PyTorch (CPU) | 已确认 |
| 网络架构 | 全连接 MLP | 待讨论 |
| 数据预处理 | 输入标准化，目标缩放到 [0,1] | 待讨论 |
| 变长输入处理 | 按 n 分别训练独立模型 | 待讨论 |
| 参数空间 | β∈{1,2}, η=1000, γ=0, n∈{5,10} | 待讨论：需扩展 |
| MC 次数 | 200 | 待讨论 |
| 模型格式 | .pth | 已确认 |

### 讨论确认的设计

| 项目 | 决策 |
|------|------|
| 研究路线 | 路线 1（直接学习）→ 路线 2（迭代逼近），网页 Tab 切换 |
| 神经网络 | N₁（公共，真值→δ）供路线 2 使用；N₂（样本→δ）供路线 1 使用 |
| 指标方案 | 多种方案对比：MSE / 相对MSE / 加权MSE / 仅β+η / R² |
| 参数空间 | β∈{1,2,5}, η∈{100,1000,5000}, γ=1000, n∈{5,7,15}, MC=500 |
| 路线 2 初始值 | δ₀ = 0.5 |
| 路线 2 收敛 | 方案 C：\|δ_new-δ_old\|<0.001 / 最大10步 / MDM失败 |
| 可视化 | 27 个图表，通用组件复用，数据来自训练结果 CSV |
| N₁ 架构 | Linear(3,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→Sigmoid |
| N₂ 架构 | Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid |
| 训练超参 | Adam, lr=0.001, batch=64, ReduceLROnPlateau, patience=30, max_epoch=300 |

---

## 四、文件清单

### 4.1 训练数据生成

| 文件 | 说明 |
|------|------|
| `python/studies/mdm_delta/generate_training_data.py` | 蒙特卡洛模拟 + δ 网格搜索，生成训练数据 |
| `python/studies/mdm_delta/data/training_data_n5.csv` | n=5 训练数据（309 条） |
| `python/studies/mdm_delta/data/training_data_n10.csv` | n=10 训练数据（289 条） |
| `python/studies/mdm_delta/data/config.json` | 生成配置记录 |
| `python/studies/mdm_delta/data/summary.json` | 生成统计摘要 |

**CSV 格式**: `n, t1, t2, ..., tn, optimal_delta, best_mse`

### 4.2 模型训练

| 文件 | 说明 |
|------|------|
| `python/studies/mdm_delta/train_model.py` | PyTorch MLP 训练脚本 |
| `python/models/mdm_delta/n5_model.pth` | n=5 模型权重 |
| `python/models/mdm_delta/n10_model.pth` | n=10 模型权重 |
| `python/models/mdm_delta/n5_metrics.json` | n=5 训练指标 + 损失历史 |
| `python/models/mdm_delta/n10_metrics.json` | n=10 训练指标 + 损失历史 |

### 4.3 后端 API

| 文件 | 位置 | 说明 |
|------|------|------|
| `python/main.py` | 第 370-491 行 | DeltaMLP 类定义 + 模型加载 + API 端点 |

**API 端点**: `POST /ai/relationship/mdm`
- 请求: `{ "data": [398.3, 520.3, 814.4, 921.3, 2344.0] }`
- 响应: `{ "optimal_delta": 0.1234, "model_n": 5, "confidence": "high" }`

### 4.4 前端页面

| 文件 | 说明 |
|------|------|
| `src/app/ai/page.tsx` | AI 总览页（3 个模块卡片 + 交叉矩阵） |
| `src/app/ai/relationship/page.tsx` | 关系建立子页面（7 个 Tab） |
| `src/app/ai/optimization/page.tsx` | 优化求解（占位页） |
| `src/app/ai/direct-estimation/page.tsx` | 直接估计（占位页） |
| `src/lib/config.ts` | API 端点配置 `aiPredictDelta` |
| `src/app/layout.tsx` | 导航栏"人工智能方法"按钮（紫色 Brain 图标） |

---

## 五、模型效果

### 5.1 数据生成统计

| 样本量 | 总模拟数 | 有效数 | 无解数 | 成功率 |
|--------|---------|--------|--------|--------|
| n=5 | 400 | 309 | 91 | 77.2% |
| n=10 | 400 | 289 | 111 | 72.2% |
| **合计** | **800** | **598** | **202** | **74.8%** |

> 注：无解 = 所有 50 个 δ 值运行 MDM 均返回 no_intersection（MDM 算法本身对某些样本无解）

### 5.2 模型验证指标

| 指标 | n=5 模型 | n=10 模型 |
|------|---------|----------|
| MSE | 0.006824 | 0.001352 |
| MAE | 0.036692 | 0.020116 |
| RMSE | 0.082605 | 0.036770 |
| 最佳 epoch | 60 | 50 |
| 训练样本数 | 248 | 232 |
| 验证样本数 | 61 | 57 |

> MAE 含义：预测 δ 与真实最优 δ 的平均绝对误差。δ 范围为 [0.01, 0.50]，所以 MAE=0.037 意味着平均偏差约 7.4%。

### 5.3 模型配置

| 配置项 | 值 |
|--------|-----|
| epochs | 200（含早停 patience=20） |
| 学习率 | 0.01 |
| 批次大小 | 32 |
| 隐藏层 | 64 → 32 |
| 验证比例 | 20% |
| 优化器 | Adam |
| 损失函数 | MSE |

---

## 六、前端页面 Tab 状态

| Tab | 名称 | 状态 | 内容 |
|-----|------|------|------|
| Theory | 原理说明 | ✅ 已完成 | 为什么需要、AI 与传统方法关系、工作流程 |
| Training | 训练算法 | ✅ 已完成 | 网络结构、数据预处理、训练策略、评价标准 |
| Data | 训练数据 | ✅ 已完成 | 生成方式、参数空间表格、数据规模、数据格式 |
| Playground | 在线使用 | ✅ 已完成 | 样本输入 → AI 预测 δ → 置信度评估 |
| Performance | 性能展示 | ⚠️ 部分完成 | 有指标卡片，缺可视化（热力图、箱型图） |
| Verification | 可信性验证 | ❌ 占位 | 空白占位页 |
| Compare | 方法对比 | ❌ 占位 | 空白占位页 |

---

## 七、端到端调用链路

```
用户浏览器
  ↓ 填写失效时间数据
  ↓ 点击"AI 预测最优 δ"
  ↓
src/app/ai/relationship/page.tsx (PlaygroundTab)
  ↓ fetch POST /ai/relationship/mdm
  ↓
python/main.py → ai_predict_delta()
  ↓ _load_delta_model(n) — 按样本量加载对应 .pth
  ↓ 排序样本 → 标准化 → PyTorch 推理 → 反缩放
  ↓ 置信度评估（基于是否接近边界）
  ↓
返回 { optimal_delta, model_n, confidence }
  ↓
前端展示 δ 值 + 置信度 + 使用提示
```

---

## 八、命令行使用

### 生成训练数据

```bash
cd python/studies/mdm_delta

# 默认精简方案
python generate_training_data.py

# 自定义参数
python generate_training_data.py --betas 1,2 --sample-sizes 5,10 --mc-runs 200
```

### 训练模型

```bash
cd python/studies/mdm_delta

# 默认参数
python train_model.py

# 自定义超参数
python train_model.py --epochs 200 --lr 0.001 --batch-size 32
```

### API 调用

```bash
curl -X POST http://localhost:8001/ai/relationship/mdm \
  -H "Content-Type: application/json" \
  -d '{"data": [398.3, 520.3, 814.4, 921.3, 2344.0]}'
```

---

## 九、当前局限性

1. **参数空间小** — β 只有 {1, 2}，η 固定 1000，γ 固定 0，n 只有 {5, 10}
2. **无截尾处理** — 只支持完全样本（Type II censoring 等未处理）
3. **训练数据少** — 共 598 条，部分样本无解被过滤
4. **无可视化** — Performance Tab 缺少热力图、箱型图、收敛曲线等
5. **无验证案例** — Verification Tab 为空
6. **无方法对比** — Compare Tab 为空（应展示 AI δ vs 固定 δ 的蒙特卡洛对比）
7. **模型只有 2 个** — n=5 和 n=10，其他样本量无模型

---

## 十、可扩展方向

| 方向 | 说明 | 优先级 |
|------|------|--------|
| 扩展参数空间 | 增加 β/η/γ/n 的取值范围 | 高 |
| Performance 可视化 | 热力图、箱型图、收敛曲线 | 高 |
| 可信性验证 | 已知参数的验证案例 | 中 |
| 方法对比 | AI δ vs 固定 δ 的蒙特卡洛对比 | 中 |
| 更多样本量 | n=15, 20, 30 等 | 中 |
| 模型改进 | 更深网络、学习率调度、数据增强 | 低 |
| ONNX 导出 | 减少 PyTorch 依赖 | 低 |
| 截尾支持 | 处理不完全样本 | 低 |

---

*本文档记录模块 1 截至 2026-04-26 的完整实现状态。*

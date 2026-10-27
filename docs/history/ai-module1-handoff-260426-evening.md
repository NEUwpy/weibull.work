# AI 模块 1 交接提示词（2026-04-26 晚间）

> **用途**：在新窗口中无缝继续 AI 模块 1 的工作
> **当前状态**：β 扩展数据生成中（后台运行），n=5,7 已完成，n=10 处理中，预计还需 ~2.5 小时

---

## 项目概况

**Weibull 分析平台**（weibull.work）— 可靠性工程参数估计与数据分析平台。

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 后端 | Python + FastAPI + SciPy/NumPy |
| 部署 | Docker + Cloudflare Tunnel → 绿联 NAS |

项目根目录：`C:\Web\Weibull`

---

## AI 模块 1：MDM 偏移量 δ 优化

### 核心问题

MDM（Minimum Difference Method）需要偏移量 δ，不同样本最优 δ 不同。用神经网络学习"参数→最优 δ"的映射，替代人工反复尝试。

### 两条路线

- **路线 1（N₂）**：样本 → 直接预测 δ（按 n 分模型，已训练，当前可用）
- **路线 2（N₁ 迭代）**：δ₀=0.5 → MDM → N₁(β̂,η̂,γ̂) → δ₁ → ... → 收敛

### 路线 2 实验结果：失败

在 β=2 固定的参数空间下，N₁ 退化为常数预测器（输出恒定 δ≈0.27），原因：
- β=2 和 γ=1000 固定时，只有 η 一个有效输入维度
- η 与最优 δ 无强相关（三个 η 的 δ 均值 0.23, 0.23, 0.25）
- 迭代收敛到 N₁ 的常数输出，不是最优 δ
- Route2 MSE 比固定 δ=0.2 高 2-7 倍

### 解决方案：扩展 β 到 {1, 2, 5}

让 N₁ 有 3 个有效输入维度（β, η, γ），应该能学到 β→δ 的有意义映射。

---

## 当前正在做的事

**数据生成任务正在后台运行**：

```bash
cd C:\Web\Weibull\python\studies\mdm_delta
python -u generate_training_data.py --betas 1,2,5 --mc-runs 500
```

- 预期：3(β) × 3(η) × 5(n) = 45 组 × 500 MC = 22,500 样本
- 耗时：~6 小时（之前 β=2 only 的 15 组用了 ~2 小时）
- 输出到 `data/` 目录，会覆盖之前的 β=2 数据

**进度（截至 2026-04-26 23:15）**：

| n | 状态 | 文件时间 | 行数 |
|---|------|---------|------|
| n=5 | ✅ 已完成 | 21:54 | 2415 |
| n=7 | ✅ 已完成 | 23:01 | 2495 |
| n=10 | ⏳ 处理中 | （旧数据） | ~1500 |
| n=15 | 等待 | （旧数据） | ~1500 |
| n=20 | 等待 | （旧数据） | ~1500 |

- 进程 PID 20208，CPU 利用率 98%，每个 n 约 1 小时
- 预计还需 ~2.5 小时完成全部

**检查进度**：
```bash
# 查看进程是否还在运行
tasklist | grep python

# 查看数据文件更新时间
ls -la python/studies/mdm_delta/data/training_data_n*.csv

# 查看 summary.json 是否已更新
cat python/studies/mdm_delta/data/summary.json
```

**判断是否完成**：
- 如果 `data/summary.json` 中 `config.betas` 包含 `[1.0, 2.0, 5.0]`，说明新数据已生成完毕
- 或者所有 `training_data_n*.csv` 文件时间戳都在 20:46 之后

---

## 数据生成完成后的步骤

### Step 1: 备份新数据
```bash
cd python/studies/mdm_delta
cp data/summary.json data/summary_expanded_beta.json
```

### Step 2: 重新训练 N₁（路线 2 的核心）
```bash
python train_model.py --model-type n1 --epochs 300 --batch-size 32
# 预期：N₁ 现在有 β, η, γ 三个有效输入，应该能学到有意义的映射
```

### Step 3: 重新训练 N₂（可选但推荐）
```bash
python train_model.py --model-type n2 --epochs 300
# N₂ 按 n 分模型，β 扩展后每个模型的训练数据增加 3 倍
```

### Step 4: 重新评估路线 2
```bash
python evaluate_route2.py --test-samples 100 --betas 1,2,5
# 预期：N₁ 能学到 β→δ 的关系，迭代收敛到更好的 δ
```

### Step 5: 生成对比数据并更新前端
```bash
python generate_comparison_data.py
python copy_data_to_public.py
```

---

## 待验证：MDM δ 搜索优化

### 问题

当前 `generate_training_data.py` 使用**粗搜+细搜网格搜索**找最优 δ：
- 粗搜：步长 0.1，遍历 [0.001, 1.0] → ~10 个点
- 细搜：步长 0.01，在最佳点 ±0.1 范围 → ~21 个点
- 总计：~31 次 MDM 调用/样本

每次 MDM 调用内部有 60×2 的 γ 搜索 + `minimize_scalar`，单次调用已很重。45 组 × 500 MC × 31 次 = ~70 万次 MDM 调用，耗时 ~6 小时。

### 初步实验结果

用 `plot_mse_delta_curve.py` 测试了不同种子的 MSE(δ) 曲线：

```
seed=42   best_d=0.315  MSE=0.0146  ← 中间有明显最小值
seed=100  best_d=0.475  MSE=0.1673  ← 中间有最小值
seed=200  best_d=0.175  MSE=0.0217  ← 前半部分有最小值
seed=300  best_d=0.045  MSE=0.1347  ← 靠近起点
seed=400  best_d=0.005  MSE=0.6616  ← 单调递增
```

**发现**：
- MSE(δ) 曲线形状因样本不同而异（有的单峰，有的近似单调）
- 不是所有样本都有清晰的最小值
- 需要更多验证才能确定优化策略

### 可能的优化方向

1. **Brent 法 / 黄金分割**：如果 MSE(δ) 是单峰的，一维优化只需 ~10-15 次（vs 31 次）
2. **抛物线插值**：取 3 个点拟合抛物线，取顶点，只需 3 次调用
3. **粗搜 + 抛物线精修**：保留粗搜（10 次），用抛物线替代细搜，~13 次
4. **先验加速**：用已有 N₂ 模型预测初始 δ₀，在小范围细搜

### 下一步：验证曲线性质

在修改搜索算法之前，需要验证：

1. **MSE(δ) 是否通常光滑？** → 画更多样本的曲线
2. **是否有多个局部极小？** → 检查单峰性
3. **无解区域在哪里？** → 检查 δ 过小时是否无解
4. **不同参数空间下的曲线形状差异** → β=1 vs 2 vs 5

**验证脚本**：`python/studies/mdm_delta/plot_mse_delta_curve.py`

```bash
cd python/studies/mdm_delta
python plot_mse_delta_curve.py --samples 12 --delta-step 0.005
# 输出到 data/mse_curves/ 目录
```

**注意**：验证实验不影响后台数据生成进程（PID 20208），可以并行进行。

---

## 关键文件清单

### 后端脚本
| 文件 | 说明 |
|------|------|
| `python/studies/mdm_delta/generate_training_data.py` | 训练数据生成（支持 `--betas` 参数）|
| `python/studies/mdm_delta/train_model.py` | N₁/N₂ 模型训练 |
| `python/studies/mdm_delta/evaluate_route2.py` | 路线 2 评估脚本 |
| `python/studies/mdm_delta/generate_comparison_data.py` | 对比数据生成 |
| `python/studies/mdm_delta/copy_data_to_public.py` | 复制到前端 public 目录 |
| `python/studies/mdm_delta/plot_mse_delta_curve.py` | **新** MSE-δ 曲线分析（搜索优化验证）|

### 模型文件
| 文件 | 说明 |
|------|------|
| `python/models/mdm_delta/n{5,7,10,15,20}_model.pth` | N₂ 模型（路线 1，当前可用，β=2 only）|
| `python/models/mdm_delta/delta_from_params.pth` | N₁ 模型（路线 2，恒定输出，需重新训练）|

### 前端
| 文件 | 说明 |
|------|------|
| `src/app/ai/relationship/page.tsx` | 7 个 Tab 框架 |
| `src/app/ai/relationship/components/CompareTab.tsx` | 方法对比（含 C5 Route 2 对比）|
| `src/app/ai/relationship/components/PlaygroundTab.tsx` | 在线使用（路线 1 + 路线 2 切换）|
| `src/app/ai/relationship/components/PerformanceTab.tsx` | 性能展示 |
| `src/app/ai/relationship/components/TrainingTab.tsx` | 训练算法说明 |

### 文档
| 文件 | 说明 |
|------|------|
| `docs/ai-methods-module1-detail.md` | 完整技术方案 |
| `docs/ai-module1-investigation.md` | 问题调查与修复计划 |
| `docs/ai-module1-route2-results.md` | 路线 2 实验结果（失败分析）|
| `docs/ai-module1-status.md` | 状态文档 |
| `docs/ai-module1-handoff-prompt.md` | 上一次交接提示词 |
| `route2_plan.md` | 路线 2 实施计划 |
| `route2_notes.md` | 研究笔记 |

### 训练数据
| 文件 | 说明 |
|------|------|
| `python/studies/mdm_delta/data/training_data_n{5,7,10,15,20}.csv` | 按 n 分文件（供 N₂ 训练）|
| `python/studies/mdm_delta/data/training_data_all.csv` | 全量合并（供 N₁ 训练）|
| `python/studies/mdm_delta/data/summary.json` | 生成统计摘要 |
| `python/studies/mdm_delta/data/config.json` | 生成配置记录 |

### 数据格式说明

每行代表一次蒙特卡洛模拟：

```
n, beta, eta, gamma, t1, t2, ..., tn, optimal_delta, best_relative_mse
5,   1.0,  100,  1000, 1003.16, 1031.13, 1084.51, 1146.34, 1189.43, 0.431, 0.0355
```

- **n, beta, eta, gamma**：样本量和 Weibull 真实参数
- **t1 ~ tn**：从 Weibull(β,η,γ) 随机抽取的失效时间（已排序）
- **optimal_delta**：使 MDM 估计误差最小的偏移量 δ（通过粗搜+细搜找到）
- **best_relative_mse**：用该 δ 得到的相对 MSE = (β̂-β)²/β² + (η̂-η)²/η² + (γ̂-γ)²/γ²

**N₂ 训练**：输入 t1~tn → 预测 optimal_delta
**N₁ 训练**：输入 (β,η,γ) → 预测 optimal_delta

---

## 设计决策

| 决策 | 值 | 说明 |
|------|-----|------|
| 指标方案 | 相对 MSE | (β̂-β)²/β² + (η̂-η)²/η² + (γ̂-γ)²/γ² |
| δ 搜索范围 | [0.001, 1.00] | 粗搜(0.1)+细搜(0.01) |
| N₂ 架构 | Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid |
| N₁ 架构 | Linear(3,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→Sigmoid |
| 路线 2 收敛 | |δ_new - δ_old| < 0.001，最大 10 步 |
| 路线 2 初始 δ₀ | 0.5 | |
| 参数空间（扩展后）| β∈{1,2,5}, η∈{100,1000,5000}, γ=1000 | 45 组 |
| 样本量 | n∈{5,7,10,15,20} | 5 个 N₂ 模型 |
| MC 次数 | 500 | 每组参数 |

---

## 注意事项

1. **Windows GBK 编码**：Python print 中 δ, →, ± 等 Unicode 字符在终端显示为乱码，不影响逻辑
2. **PyTorch CPU**：无需 GPU
3. **已有 N₂ 模型**：当前的 N₂ 模型（β=2 only）仍然可用，扩展 β 后会重新训练
4. **N₁ 训练 batch size**：使用 `--batch-size 32` 避免 batch size 警告
5. **train_model.py**：已修复 n=10 被排除的 bug，已添加 `drop_last=True`

---

## 快速启动

```bash
# 1. 检查数据生成进度
cd C:\Web\Weibull\python\studies\mdm_delta
tail -5 data/summary.json  # 看 betas 是否已变为 [1,2,5]

# 2. 如果数据已生成完毕，开始训练
python train_model.py --model-type n1 --epochs 300 --batch-size 32
python train_model.py --model-type n2 --epochs 300

# 3. 评估路线 2
python evaluate_route2.py --test-samples 100 --betas 1,2,5

# 4. 更新前端
python generate_comparison_data.py
python copy_data_to_public.py
```

---

## 上下文：之前发生了什么

1. 最初参数空间是 β=2, η∈{100,1000,5000}, γ=1000, n∈{5,7,10,15,20}
2. N₂ 模型（路线 1）训练成功，5 个 n 值都有模型，MSE 在 0.007-0.019 之间
3. N₁ 模型（路线 2）训练失败——输出恒定 δ≈0.27，因为 β 固定时 η 与 δ 无强相关
4. 路线 2 评估确认失败——Route2 MSE 比固定 δ=0.2 高 2-7 倍
5. 结论：需要扩展 β 到 {1, 2, 5}，让 N₁ 有 3 个有效输入维度
6. 当前：数据生成正在后台运行（扩展 β 到 {1,2,5}）

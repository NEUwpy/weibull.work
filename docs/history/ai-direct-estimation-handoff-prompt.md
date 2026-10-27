# AI 直接估计（模块 3）— 衔接提示词

> 用于新会话无缝衔接，复制以下内容作为新会话的开场消息。

---

## 提示词（复制此部分）

我正在为 Weibull 分析平台（weibull.work）实现"AI 直接估计"模块（模块 3）。请先阅读以下文档：

1. `C:\weibull\CLAUDE.md` — 项目总览
2. `C:\weibull\docs\ai-direct-estimation-design.md` — 模块 3 设计方案（含所有决策和当前进度）
3. `C:\weibull\docs\ai-direct-estimation-tasks.md` — 任务进度清单
4. `C:\weibull\docs\ai-direct-estimation-v2-plan.md` — V2 规划（已完成）

### 项目背景

Weibull 分析平台是可靠性工程的参数估计研究平台，现有模块：
- Calculator（计算器）— 交互式参数估计
- Methods（参数估计方法）— 25+ 种传统方法的探索平台
- Cases（案例数据库）、Library（可靠性图书馆）
- ★ AI（人工智能方法）— 新增模块，已搭建框架

AI 模块下有三个子页面：
1. **关系建立**（/ai/relationship）— 模块 1 已完成（MDM δ 优化）
2. **优化求解**（/ai/optimization）— 暂空
3. **直接估计**（/ai/direct-estimation）— **本模块**

### 模块 3 当前状态：V2 完成，γ≠0 + 泛化验证

端到端实现：数据生成 → 模型训练 → 后端 API → 前端方案选择 + 7-Tab 页面。

**三大方案组、8 个预处理子选项，全部已完成**：

| 方案 | 输入 | 模型类型 | 状态 |
|------|------|---------|------|
| A-1 原始样本 | [t1, ..., tn] | 按 n 独立模型 | ✅ |
| A-2 除以均值 | [t1/t̄, ..., tn/t̄, t̄] | 按 n 独立模型 | ✅ |
| A-3 去位置 | [t1-t_min, ..., tn-t_min] | 按 n 独立模型 | ✅ |
| B-1 原始+掩码 | [..., mask] | 统一模型 | ✅ |
| B-2 除以均值+掩码 | [..., t̄, mask] | 统一模型 | ✅ |
| C-1 基础统计量 | [mean, std, min, max] | 按 n 独立模型 | ✅ |
| C-2 扩展统计量 | 7 特征 | 按 n 独立模型 | ✅ |
| C-3 最大化统计量 | 11 特征 | 按 n 独立模型 | ✅ |

**核心设计决策**：
- **架构**: MLP, n→128→64→32→3，线性输出
- **损失函数**: 归一化 MSE（输出 y 归一化为零均值单位方差，训练后反归一化）
- **关键踩坑**: 最初用相对 MSE + 原始 y 值，但 η(100-5000) 和 β(0.5-5) 量纲差距太大导致网络学不好，改为输出归一化后解决

**当前参数空间**（V2）：
- β∈{0.5, 1.0, 2.0, 3.0, 5.0}, η∈{100, 500, 1000, 3000, 5000}, **γ∈{0, 50, 100, 200}**, n∈{5,7,10,15}, MC=500
- 400 组 × 500 = 200,000 条训练数据

**实验结论**：
1. C-1 ≈ A-1 — 4 个统计量已充分提取 Weibull 参数信息
2. B-1 统一模型可行 — 一个模型覆盖所有 n，精度几乎相同，实用性最强
3. A-2 对 η 变差 — 除以均值反而丢失尺度信息
4. C-2 无额外优势 — 偏度/峰度/中位数未提供新信息
5. A-3 明显变差 — 去位置丢失绝对尺度，MAE(β) 几乎翻倍
6. B-2 ≈ B-1 — 除以均值+掩码与原始+掩码精度相当
7. C-3 ≈ C-1 — Q1/Q3/IQR/CV 未提供超出基础统计量的新信息

**V2 泛化验证结论**：
8. 插值精度略降 — 插值集 MAE(β) 比组内高约 20-30%
9. 外推精度大幅下降 — 外推集 MAE(β) 是组内的 8-10 倍
10. a2/b2 外推爆炸 — 除以均值预处理在外推时产生极大值（MAE(β) 达 10^10）
11. a1/b1/c1/c2 外推相对稳健 — 虽然精度下降，但输出仍在合理范围

### V1.1 前端可视化优化（已完成）

- PerformanceTab: 散点图改为真正的 ScatterPlot（非折线图），误差分布改为直方图，精度表支持按 n/β/η 维度切换
- VerificationTab: 新增精度汇总表，支持绝对精度(MAE)/相对精度(MRE) 小 Tab 切换
- CompareTab: 8 个方案状态全部更新为"已完成"，新增 MAE 按 n 的折线图，补充完整 7 条结论

### V2 已完成：γ≠0 + 泛化验证

V2 已全部实施完成，详见 `C:\weibull\docs\ai-direct-estimation-v2-plan.md`。

**已完成内容**：
- γ 从 {0} 扩展为 {0, 50, 100, 200}，总样本从 50k→200k
- 新建 `generate_test_data.py`（ig/ip/ex 三类测试集，67,600 条）
- 新建 `evaluate_generalization.py`（泛化评估脚本）
- 全部 8 个方案重新训练 + 泛化评估
- VerificationTab + PerformanceTab 增加 validation_type 切换
- 输出 `generalization_metrics.json`（40KB）

### 关键文件

```
python/studies/direct_estimation/
├── generate_training_data.py     # 蒙特卡洛生成训练数据（V2: γ∈{0,50,100,200}）
├── generate_test_data.py         # 泛化测试数据生成（ig/ip/ex 三类）
├── train_model.py                # PyTorch 训练脚本（支持全部 8 种预处理）
├── evaluate_generalization.py    # 泛化评估脚本（输出 generalization_metrics.json）
└── data/                         # 训练数据 CSV + 测试数据 CSV

python/models/direct_estimation/  # 模型权重 (.pth) + 指标 (.json)

python/main.py                    # POST /ai/direct-estimation API
src/app/ai/direct-estimation/     # 前端方案选择 + 7-Tab 详情页
src/lib/ai-data.ts                # 数据加载工具（含 scheme-aware 路径函数 + 泛化指标类型）
public/ai/data/                   # 前端加载的 metrics JSON + CSV + generalization_metrics.json
```

### 运行环境

- Python 3.11: `C:\Users\ilove\AppData\Local\Programs\Python\Python311\python.exe`
- 依赖: numpy, torch, scipy, fastapi, uvicorn, pyyaml
- 训练: `cd python/studies/direct_estimation`
- 生成数据: `python generate_training_data.py --gammas 0,50,100,200`
- 训练单方案: `python train_model.py --preprocessing a1`（支持 a1/a2/a3/b1/b2/c1/c2/c3）
- 复制数据到前端: 将 metrics JSON 和 validation CSV 复制到 `public/ai/data/`（加 `direct_estimation_` 前缀）

---

*提示词结束。将以上内容粘贴到新会话中即可继续工作。*

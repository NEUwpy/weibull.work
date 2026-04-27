# 人工智能方法模块 — AI 衔接提示词

> 用于新会话无缝衔接，复制以下内容作为新会话的开场消息。

---

## 提示词（复制此部分）

我正在为 Weibull 分析平台（weibull.work）添加"人工智能方法"模块。请先阅读以下文档了解背景：

1. `C:\Web\Weibull\CLAUDE.md` — 项目总览
2. `C:\Web\Weibull\docs\ai-methods-plan.md` — 人工智能方法模块总规划
3. `C:\Web\Weibull\docs\ai-module1-status.md` — 模块 1 当前状态
4. `C:\Web\Weibull\docs\ai-module3-status.md` — 模块 3 当前状态

### 项目背景

Weibull 分析平台是可靠性工程的参数估计研究平台，现有模块：
- Calculator（计算器）— 交互式参数估计
- Methods（参数估计方法）— 25+ 种传统方法的探索平台
- Cases（案例库）、Library（图书馆）
- ★ AI（人工智能方法）— 新增模块，已搭建框架

AI 模块与 Methods 同级，探索 AI 辅助参数估计的效果与适用范围。

### 三类用途划分（按 AI 介入方式）

1. **关系建立**（/ai/relationship）— AI 学习"样本 → 过程参数"映射，当前做 MDM 偏移量 δ 优化
2. **优化求解**（/ai/optimization）— AI 辅助传统数值优化，暂空
3. **直接估计**（/ai/direct-estimation）— AI 端到端直接输出 β、η、γ

**实施顺序**：模块 1（MDM δ）→ 模块 3（直接估计）→ 模块 2（暂空）

### 模块 1 当前状态（2026-04-27 阶段性结束）

**术语**：M1-R1（路线1，直接学习），M1-R2（路线2，迭代逼近）。不再使用 N₁/N₂。

**阶段性结论**：
- ✅ 方向可行：最优 δ 替代固定 δ 能提升 MDM 精度 97-99%
- ✅ 基础设施完备：框架、模型、前端、可视化全部完成
- ⚠️ 数据质量有问题：对 MSE-δ 曲线性质认识不足，导致搜索策略盲目

**根本问题**：对 MSE-δ 曲线的数学性质（单调性、极值点、有效范围）缺乏系统性认识，导致：
1. 搜索策略盲目 — 不知道该搜多宽、搜多密
2. 训练数据质量不稳定 — 边界过滤、搜索范围不一致
3. 模型学到的映射本身不准确 — 垃圾进垃圾出

**下一步方向**（需要你提出具体 plan）：
1. 系统性研究 MSE-δ 曲线数学性质（单调性、极值点、有效范围）
2. 基于曲线性质优化搜索策略（Brent 法等）
3. 统一搜索策略，消除数据不一致
4. 用高质量数据重新训练模型

**关键文件**：
- 状态文档: `docs/ai-module1-status.md`
- 训练数据: `python/studies/mdm_delta/data/`
- 模型文件: `python/models/mdm_delta/n{5,7,10,15,20}_model.pth`
- 训练脚本: `python/studies/mdm_delta/train_model.py`
- 后端 API: `POST /ai/relationship/mdm`（在 python/main.py 末尾）
- 前端页面: `src/app/ai/relationship/`（总览）→ `m1-r1/`（路线1）→ `m1-r2/`（路线2）

### 模块 3 当前状态（2026-04-27 V2 完成）

**核心发现**：MLP 端到端直接估计 β、η、γ 可行，B-1 统一模型（填充+掩码）实用性最强。

**三大方案组、8 种预处理，全部已完成**：

| 方案 | 结论 |
|------|------|
| A-1 原始样本 | 基线方案 |
| A-2 除以均值 | 对 η 变差 |
| A-3 去位置 | 明显变差，MAE(β) 几乎翻倍 |
| B-1 原始+掩码 | **最优方案**，统一模型覆盖所有 n |
| B-2 除以均值+掩码 | ≈ B-1 |
| C-1 基础统计量 | ≈ A-1，4 个统计量已充分 |
| C-2/C-3 扩展统计量 | 无额外优势 |

**参数空间**（V2）：β∈{0.5,1,2,3,5}, η∈{100,500,1000,3000,5000}, γ∈{0,50,100,200}, n∈{5,7,10,15}, MC=500, 共 200,000 条

**泛化验证结论**：
- 插值精度略降（比组内高 ~27%）
- 外推精度大幅下降（8-10 倍）
- a2/b2 外推发散（MAE(β) 达 10^10）
- a1/b1/c1/c2 外推相对稳健

**下一步方向**：
1. AI vs 传统方法对比（MLE/MDM）
2. 扩大参数空间（更多 β/η、更多 n）
3. 网络架构实验

**关键文件**：
- 状态文档: `docs/ai-module3-status.md`
- 训练数据: `python/studies/direct_estimation/data/`
- 模型文件: `python/models/direct_estimation/`
- 训练脚本: `python/studies/direct_estimation/train_model.py`
- 后端 API: `POST /ai/direct-estimation`（在 python/main.py）
- 前端页面: `src/app/ai/direct-estimation/`（方案选择）→ `[scheme]/`（7-Tab 详情）

### 关键文件参考

- MDM 算法实现: `python/methods/mdm.py`
- 前端路由: `src/app/`
- 方法系统组件: `src/components/methods/`
- 后端入口: `python/main.py`
- 数据模型: `01-A-数据模型与接口.md`
- 规则: `02-规则.md`（写新代码前必读）

---

*提示词结束。将以上内容粘贴到新会话中即可继续工作。*

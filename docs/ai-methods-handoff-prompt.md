# 人工智能方法模块 — AI 衔接提示词

> 用于新会话无缝衔接，复制以下内容作为新会话的开场消息。

---

## 提示词（复制此部分）

我正在为 Weibull 分析平台（weibull.work）添加"人工智能方法"模块。请先阅读以下文档了解背景：

1. `C:\Web\Weibull\CLAUDE.md` — 项目总览
2. `C:\Web\Weibull\docs\ai-methods-plan.md` — 人工智能方法模块总规划
3. `C:\Web\Weibull\docs\ai-methods-module1-detail.md` — 模块 1 详细方案（已含已确认决策）

### 项目背景

Weibull 分析平台是可靠性工程的参数估计研究平台，现有模块：
- Calculator（计算器）— 交互式参数估计
- Methods（参数估计方法）— 25+ 种传统方法的探索平台
- Cases（案例库）、Library（图书馆）
- ★ AI（人工智能方法）— 新增模块，已搭建框架

现在要新增"AI"模块，与 Methods 同级，探索 AI 辅助参数估计的效果与适用范围。

### 已确认的设计

**三类用途划分**（按 AI 介入方式）：
1. **关系建立**（/ai/relationship）— AI 学习"样本 → 过程参数"映射，当前做 MDM 偏移量 δ 优化
2. **优化求解**（/ai/optimization）— AI 辅助传统数值优化，暂空
3. **直接估计**（/ai/direct-estimation）— AI 端到端直接输出 β、η、γ

**实施顺序**：模块 1（MDM δ）→ 模块 3（直接估计）→ 模块 2（暂空）

**Tab 结构**（每个子页面 7 个 Tab）：
1. 原理说明
2. 训练算法
3. 训练数据
4. 在线使用
5. 性能展示
6. 可信性验证
7. 方法对比

**模块 1 已确认决策**：
- 最优评价标准: MSE(β,η,γ) 三参数均方误差之和
- 框架: PyTorch (CPU)
- 架构: 全连接 MLP (n→64→32→1)，输入标准化，目标缩放到 [0,1]
- 参数空间: β∈{1,2}, η=1000, γ=0, n∈{5,10}, δ∈[0.01,0.50], MC=200
- 按 n 分别训练独立模型

### 模块 1 原型已完成

端到端实现：数据生成 → 模型训练 → 后端 API → 前端页面。

**关键文件**：
- 训练数据: `python/studies/mdm_delta/data/training_data_n{5,10}.csv`（共 598 条）
- 模型文件: `python/models/mdm_delta/n{5,10}_model.pth`
- 训练脚本: `python/studies/mdm_delta/generate_training_data.py` + `train_model.py`
- 后端 API: `POST /ai/relationship/mdm`（在 python/main.py 末尾）
- 前端页面: `src/app/ai/`（总览 + 3 个子页面）
- 导航配置: `src/app/layout.tsx`（紫色 Brain 图标）
- API 端点: `src/lib/config.ts`

**模型效果**：n=5 MAE=0.037, n=10 MAE=0.020

### 当前待完善事项

**模块 1**：
1. 扩展参数空间（更多 β/η/γ/n 取值）
2. 性能可视化（热力图、AI δ vs 固定 δ 对比）
3. 可信性验证 Tab
4. 方法对比 Tab

**后续模块**：
5. 模块 3 — 直接估计（端到端输出 β,η,γ）
6. 模块 2 — 优化求解（AI 辅助 MLE）

### 关键文件参考

- MDM 算法实现: `python/methods/mdm.py`
- 前端路由: `src/app/`
- 方法系统组件: `src/components/methods/`
- 后端入口: `python/main.py`
- 数据模型: `01-A-数据模型与接口.md`
- 规则: `02-规则.md`（写新代码前必读）

---

*提示词结束。将以上内容粘贴到新会话中即可继续工作。*

# 人工智能方法模块 — AI 衔接提示词

> 用于新会话无缝衔接，复制以下内容作为新会话的开场消息。

---

## 提示词（复制此部分）

我正在为 Weibull 分析平台（weibull.work）添加"人工智能方法"模块。请先阅读以下文档了解背景：

1. `C:\Web\Weibull\CLAUDE.md` — 项目总览
2. `C:\Web\Weibull\docs\ai-methods-plan.md` — 人工智能方法模块总规划
3. `C:\Web\Weibull\docs\ai-module1-status.md` — 模块 1 当前状态（**最重要**）

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

### 模块 1 当前状态（2026-04-27）

**已完成**：
- 数据生成：β∈{1,2,5}, η∈{100,1000,5000}, γ=1000, n∈{5,7,10,15,20}, MC=500
- 12,597 条有效训练数据（22,500 总样本，56% 成功率）
- N₂ 模型（路线 1）：5 个 n 值，MSE 0.027-0.034
- N₁ 模型（路线 2）：已重新训练，不再是常数预测器
- 前端数据已同步到 public/ai/data/

**待解决**：
1. 边界过滤问题（~44% 样本被丢弃）
2. 路线 2 重新评估（evaluate_route2.py）
3. 搜索策略优化（Brent 法）

**关键文件**：
- 状态文档: `docs/ai-module1-status.md`
- 训练数据: `python/studies/mdm_delta/data/`
- 模型文件: `python/models/mdm_delta/n{5,7,10,15,20}_model.pth`
- 训练脚本: `python/studies/mdm_delta/train_model.py`
- 后端 API: `POST /ai/relationship/mdm`（在 python/main.py 末尾）
- 前端页面: `src/app/ai/`

### 关键文件参考

- MDM 算法实现: `python/methods/mdm.py`
- 前端路由: `src/app/`
- 方法系统组件: `src/components/methods/`
- 后端入口: `python/main.py`
- 数据模型: `01-A-数据模型与接口.md`
- 规则: `02-规则.md`（写新代码前必读）

---

*提示词结束。将以上内容粘贴到新会话中即可继续工作。*

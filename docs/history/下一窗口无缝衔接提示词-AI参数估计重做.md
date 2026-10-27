# 下一窗口无缝衔接提示词：AI 参数估计模块重做

> 用途：复制到下一个 Codex / AI coding / chatbox 窗口，让它无缝接上当前工作。

---

## 直接复制提示词

```text
我正在做一个项目：C:\weibull，威布尔分析平台（Weibull Analysis Platform）。

项目技术栈：
- 前端：Next.js 14 + TypeScript + Tailwind CSS
- 后端：Python + FastAPI + SciPy/NumPy
- 研究对象：可靠性工程中的 Weibull 参数估计与数据分析

请先阅读项目根目录的 AGENTS.md，并遵守其中规则：
- 先读文档
- 复用优先
- 禁止读取 _archive/
- 写新代码前先读 02-规则.md

当前我正在重做 AI 辅助 Weibull 参数估计模块。注意：现在不要急着改代码、不要训练模型、不要跑实验，先继续做规划、规范和方案审查。

一、当前背景

原 AI 模块已经有 M1/M3 原型、训练结果、模型文件和页面展示，但由于之前 AI coding 使用过多，导致：

1. 指标口径不统一。
2. 损失函数没有对齐研究目标。
3. 训练集、验证集、测试集、组内测试、插值测试、外推测试没有统一 benchmark。
4. 传统方法和 AI 方法没有全部在同一测试集、同一指标下公平比较。
5. 蒙特卡洛实验每个模块各写各的，CSV 字段、失败记录、统计方式都不统一。
6. 部分失败结果可能被写成 0 或 NaN，没有统一 status / failure_reason。
7. 旧 M1/M3 结果不能继续作为正式研究结论。

因此现在的核心决策是：

- 旧 M1/M3 结果全部降级为历史原型。
- 旧模型、旧页面、旧数据可以保留作历史对照。
- 新指标、新 benchmark、新损失函数、新训练协议确定后，M1/M3 必须重新训练。
- 当前阶段先做指标、蒙特卡洛框架、方法调用接口、结果文件规范。

二、AI 模块新结构

M1：AI 辅助传统方法
- M1-A：AI 优化传统方法过程量，例如 MDM 方法的偏移量 δ
- M1-B：AI 纠正传统方法偏差

M2：智能优化算法辅助传统方法求解
- 暂时不做，只保留中长期方向

M3：AI 直接求解
- 直接从样本或样本特征预测 Weibull 三参数 β、η、γ

三、已完成的关键文档

请优先阅读这些文档：

1. docs/AI辅助参数估计重做简明路线图.md
   - 最简单版本，说明每一步干什么、产出什么、达到什么目标。

2. docs/AI辅助参数估计模块重做总纲.md
   - 详细总纲，说明为什么重做、旧结果如何处理、M1/M2/M3 如何定义。

3. docs/AI辅助参数估计指标定义方案V2.md
   - 当前最新指标方案，已经综合人的意见、审查报告1、审查报告2。
   - 核心是：参数精度、稳定性、工程寿命、方法可用性。

4. docs/AI辅助参数估计统一蒙特卡洛实验框架方案.md
   - 当前最新蒙特卡洛框架方案。
   - 核心是统一参数空间、样本生成、方法调用、predictions CSV、metrics_summary CSV。

5. docs/ai-research/research-roadmap.md
6. docs/ai-research/research-progress.md
7. docs/ai-engineering/engineering-roadmap.md
8. docs/ai-engineering/engineering-progress.md
9. docs/ai-research/agent-execution-guide.md
10. docs/ai-research/benchmark-spec-v1.md

四、目前已经完成的阶段

简明路线图中的：

0. 旧 M1/M3 正式结论废止为历史原型 —— 已完成
1. 研究大目标 —— 已完成
2. AI 模块三大部分 M1/M2/M3 —— 已完成
3. 指标方案 V2 —— 已形成草案，待审查/敲定
4. 统一蒙特卡洛实验框架方案 —— 已形成草案，待审查/敲定

五、当前最重要的理解

现在的问题不是“再训练一个 AI 模型”，而是：

传统方法计算、蒙特卡洛实验、指标统计、AI 训练、页面展示这几层以前都没有统一协议。

所以后续必须建立一条统一证据链：

参数空间配置
↓
统一样本生成器
↓
samples.csv
↓
统一方法调用接口
↓
predictions.csv
↓
统一指标函数
↓
metrics_summary.csv
↓
前端页面 / 组会图表 / 论文实验表格

六、指标 V2 的核心内容

指标分四组：

1. 参数精度
   - mae_log_beta
   - mae_log_eta
   - mre_beta
   - mre_eta
   - mae_gamma
   - scaled_gamma_error

2. 稳定性
   - bias_log_beta
   - bias_log_eta
   - bias_gamma_scaled
   - std_log_beta
   - std_log_eta
   - std_gamma_scaled

3. 工程寿命
   - B0.5/B1/B5/B10 life scaled error
   - B1/B5/B10 life MAE
   - protected B-life MRE
   - low_denominator_ratio

4. 方法可用性
   - success_rate
   - outlier_rate
   - failure_rate
   - runtime
   - failure_reason_distribution
   - common_count/common_ratio

关键规则：
- γ 不使用普通 MRE。
- B-life MRE 必须有分母保护。
- 使用 success / outlier / failed 三态。
- 跨方法主对比需要共同成功集 common 口径。
- M1-A 的主指标不是 δ 误差，而是 AI δ 代入 MDM 后下游结果是否改善。
- M1-B 必须看 bias 和 std，因为它研究的是偏差修正。

七、统一蒙特卡洛框架核心内容

要建立这些规范：

1. 参数空间配置规范
   - benchmark_v1.yaml
   - 定义 train/val/ig/ip/ex

2. 样本 CSV 规范
   - samples_{split}_n{n}.csv
   - 必须有 sample_id、seed、n、beta_true、eta_true、gamma_true、t1...tn

3. 方法调用接口规范
   - 所有传统方法和 AI 方法统一输入输出

4. predictions CSV 规范
   - sample_id, method, scheme, n, validation_type, beta_hat, eta_hat, gamma_hat, status, failure_reason, runtime_ms, extra_json

5. metrics_summary CSV 规范
   - method, scheme, validation_type, n, group_key, metric_name, metric_value, count, total_count

6. run manifest
   - 保存一次实验的参数空间、方法配置、指标版本、输出路径、运行时间

八、当前不要做什么

不要：
- 不要训练模型。
- 不要重写 AI 页面。
- 不要引用旧 M1/M3 结果作为正式结论。
- 不要直接实现大规模代码重构。
- 不要启动 M2。
- 不要读取 _archive/。
- 不要把旧 CSV/JSON 当作新 benchmark 结果。

九、现在你需要做什么

请接着当前工作，优先做以下其中一项：

方案 A：审查并完善 docs/AI辅助参数估计统一蒙特卡洛实验框架方案.md
- 看它是否足够解决“每次蒙特卡洛都重写一套”的问题。
- 检查 samples/predictions/metrics_summary 字段是否够用。
- 检查 status/failure_reason 是否科学。
- 检查是否能同时支持 MDM、MLE、M1-A、M1-B、M3。

方案 B：把指标 V2 和蒙特卡洛框架合并成下一阶段执行顺序
- 先 /help/metrics
- 再公共指标函数
- 再 benchmark 参数空间
- 再 sample_generator/method_runner/metrics_runner 接口
- 再 MDM/MLE dry-run

方案 C：开始写“统一蒙特卡洛框架审计提示词”
- 让我复制给其他 AI 审查这个框架。

请先不要写代码。先给我判断、方案或文档。
```

---

## 极简版提示词

如果下个窗口不想贴长提示词，可以贴这个短版：

```text
项目在 C:\weibull，是 Weibull Analysis Platform。请先读 AGENTS.md、README.md、02-规则.md，禁止读 _archive/。

当前任务是 AI 辅助 Weibull 参数估计模块重做。旧 M1/M3 因指标、损失、训练/测试、传统基准、蒙特卡洛输出不统一，已降级为历史原型，不能作为正式研究结论。

请优先读：
1. docs/AI辅助参数估计重做简明路线图.md
2. docs/AI辅助参数估计模块重做总纲.md
3. docs/AI辅助参数估计指标定义方案V2.md
4. docs/AI辅助参数估计统一蒙特卡洛实验框架方案.md

目前已完成：旧结果定位、研究目标、M1/M2/M3 新结构、指标 V2 草案、统一蒙特卡洛框架草案。

下一步不要训练模型、不要改页面、不要跑实验。请先审查和完善统一蒙特卡洛框架：参数空间配置、samples.csv、method runner、predictions.csv、metrics_summary.csv、status/failure_reason、run_manifest，确保未来 MDM/MLE/M1-A/M1-B/M3 都能用同一套框架生成和比较结果。
```


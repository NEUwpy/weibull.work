# 方法建设总路线图

## Goal

把方法总览中的 22 个叶子方法逐步建设为可审计的平台能力：每个方法至少完成后端算法、独立测试、计算器接入、公式及原理、程序流程和专项论文依据；随后补齐计算过程、结果分析、适用范围和可信性验证。

设计依据：`docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`。

## Scope

### 叶子方法

- 极大化适配：MLE、MMLE、MPS、WMLE
- 极小化适配：LSE、WLSE、MDM、EIV
- 线性回归：LRE、BLRE
- 矩方法：MM、PWM、LM、TLM
- 灰色方法：GM(1,1)
- 构造统计量：MVE、LSF
- 贝叶斯：Gibbs、MAP
- AI：PSO、SVR、ANN

8 个类别页只负责组织和介绍，不作为算法实现对象。

## Global Rules

1. `05-状态.md` 是方法建设状态的唯一事实源；总体层级自动推导。
2. 第一层全部完成后，方法才能在计算器中公开选择。
3. 同族方法可以共享核心组件，但每个叶子方法必须有独立公式或规则、执行分支、测试、详情说明和专项论文依据。
4. 181-004 只作为分类和文献线索，不单独充当方法专项论文。
5. 方法失败不得静默返回另一个方法的结果。
6. “方法对比”是平台级能力，不计入单方法闭环。
7. PSO、SVR、ANN 需要独立的 AI 成熟度设计，不能直接套用传统解析算法验收表。
8. 不修改或提交 `Study/01`、`Study/02` 等不相关研究线文件。

## Paper Handoff

论文材料由用户处理。发现缺口时提交 `PAPER_NEEDED`，包含方法、需要的论文类型、已知题名/作者/年份/DOI 线索、用途和仍可继续的工作。不得自行用综述、博客或 181-004 替代。

当前本地已发现：

- MDM：`src/content/182-046-pdf原文.md`
- WMLE：`src/content/182-088-pdf原文.md`

当前本地未发现可直接作为完整专项证据的全文：

- MLE：181-004 给出 Smith (1985)、Hirose (1996) 等线索；需选择与当前三参数 MLE 实现口径一致的专项论文。
- MMLE：Cohen & Whitten (1982), *Modified maximum likelihood and modified moment estimators for the three-parameter Weibull distribution*。
- LRE：Park (2017), *Weibullness test and parameter estimation for the three-parameter Weibull model using the sample correlation coefficient*。

这些论文缺口不阻止状态基础设施建设，但相应方法不得因此被判定第一层完成。

## Phases

### Phase 0: 单一状态源与安全基础

执行计划：`coworker/plans/2026-07-17-method-status-foundation.md`

交付：

- `05-状态.md` 的 YAML 状态源；
- 构建期解析、校验和只读生成数据；
- 功能状态看板读取化；
- 计算器第一层门控，保持现有视觉；
- 方法详情页未完成状态；
- `?method=` 正确预选；
- 删除静默 WMLE 回退；
- 文档、状态、代码和证据一致性检查。

闸门：Codex `APPROVE` 后才能把状态基础设施作为后续方法批次的共同底座。

### Phase 1: 现有可运行方法重新验真

对象：MLE、MMLE、WMLE、MDM、LRE。

任务：

- 确认每个算法与专项论文的公式、参数化和边界条件一致；
- 补独立基准测试，不以“能返回数字”代替算法验证；
- 核对计算器调用返回的方法身份；
- 补齐第一层缺项；
- 根据证据升级 `05-状态.md`。

停机：缺专项论文时提交 `PAPER_NEEDED`；可以继续不依赖论文的测试、接口和状态审计。

### Phase 2: 极大化与极小化方法

按独立批次执行：

1. MPS；
2. LSE、WLSE；
3. EIV。

每批先核论文和公式，再实现共享核心与独立分支，最后完成第一层验收。

### Phase 3: 回归与矩方法

按独立批次执行：

1. BLRE；
2. MM、PWM；
3. LM、TLM。

LM/TLM 不得继续仅作为 PWM 的别名；需要独立矩定义、执行分支和测试。

### Phase 4: 灰色与构造统计量

按独立批次执行：

1. GM(1,1)；
2. MVE；
3. LSF。

MVE、LSF 若只能估计部分参数，任务必须明确与哪个可部署方法组合，以及计算器输出三参数的完整合同。

### Phase 5: 贝叶斯方法

对象：Gibbs、MAP。

两者可以共享似然、先验和后验模型，但必须使用不同推断路径：Gibbs 返回抽样后验摘要，MAP 返回后验众数优化结果。不得继续都映射到同一个 `bayesian` 占位类。

### Phase 6: AI 方法独立设计

对象：PSO、SVR、ANN。

先确认：

- 估计目标和输出参数化；
- 训练或搜索数据来源；
- 训练/推理资产；
- 数据切分与泄漏防护；
- 泛化验证；
- 在线推理失败策略；
- 可复现性与模型版本。

设计经用户批准后，分别创建执行计划。

### Phase 7: 第二层与第三层

对第一层已稳定的方法，按使用优先级补：

- 第二层：计算过程、结果分析；
- 第三层：适用范围、可信性验证。

后续层可以提前施工，但总体成熟度不得跨过未完成前置层。

### Phase 8: 平台级方法对比

当至少两个方法具备可比口径和稳定证据后，独立设计方法对比的数据合同、指标、图表和适用范围。该阶段不改变单方法闭环判定。

## Per-Batch Verification

每个方法批次至少验证：

- 方法 ID、注册和计算器调用一致；
- 专项论文可追溯，公式映射有记录；
- 固定样本或论文样例基准测试；
- 合理参数网格下返回有限、合法的参数；
- 失败时明确失败，不冒充其他方法；
- 共享核心具有本方法独立分支测试；
- `05-状态.md` 只按真实证据升级；
- `git diff --check`、相关 pytest、`npm run check:method-status`、`npx tsc --noEmit`；
- 若影响生产构建，运行 `npm run build`。

## Report and Review

Hermes 每批在 `coworker/reports/` 写执行报告，包含改动文件、精确测试结果、论文映射、跳过检查、偏离和阻塞。Codex 根据实际 diff 和证据在 `coworker/reviews/` 返回：

- `APPROVE`：范围正确，证据充分，无阻塞问题；
- `REVISE`：方向可接受，但有明确修复项；
- `BLOCK`：违反硬边界、论文/公式不足或需要重新规划。

# AI 辅助三参数威布尔参数估计重构当前路线图

> 本文是当前接手入口，用来把最初总纲、后续研究 01-04、MDM 默认求解器改造、统一指标、统一蒙特卡洛流水线和下一步 AI 模块建设接起来。
> 原始研究意图见 `docs/oldrules/AI辅助三参数威布尔参数估计重构与实验设计总纲.md`；当前工程规则见 `02-规则.md`、`python/studies/common/README.md`、`python/studies/mdm/README.md`。

---

## 1. 当前主线

最终目标不是再堆一批零散 AI 页面或一次性实验脚本，而是形成两层稳定体系：

```text
传统估计方法层
  每个方法都有正规的后端实现、统一注册、统一调用、统一蒙特卡洛评估、统一前端图表表达。

AI 方法层
  在传统方法层已经立稳的基础上，按 M1/M2/M3/M4 进行 AI 辅助、修正、直接估计和智能优化尝试。
```

换句话说，旧平台要先从“每个方法一摊脚本、每个页面一套指标”收束为统一工程底座；AI 模块再作为这个底座上的研究扩展，而不是另一摊独立体系。

---

## 2. 为什么路线和最初总纲有所偏离

最初总纲的顺序大致是：

```text
整理旧平台 -> 建立双视角评价体系 -> loss 对比实验 -> 统一蒙特卡洛框架 -> 建设 M1/M2/M3/M4
```

实际执行中先暂停了 AI 模块推进，转而补做研究 01-04 和 MDM 基础问题，原因是：

- 评价体系当时没有先调研清楚，继续训练 AI 模型会不知道该按什么口径判断好坏。
- 旧 MDM 存在 `no_intersection` / `no_offset_root` 一类无解或旧式失败语义，继续做 M1 offset 学习会把求解器本身的问题混入 AI 结论。
- 旧蒙特卡洛流程是“用一次写一次”，样本、调用、结果保存、指标聚合都不统一，无法保证横向比较可信。
- 旧 AI public 数据和前端展示基于旧 MDM、旧参数空间、旧 MAE/MRE/MSE 口径，只能作为历史原型，不适合作为当前正式结论。

因此当前正确路线是：

```text
先把评价标准、MDM 默认求解器、公共蒙特卡洛流水线稳住
-> 固定 full-v1 作为研究03 baseline
-> 再继续 NN offset、loss 实验和 AI 模块建设
```

这个偏移不是推翻总纲，而是补齐总纲推进前必须先解决的研究和工程前提。

---

## 3. 已完成并可作为当前依据的内容

### 3.1 默认 MDM

当前默认 MDM 固定为：

- 生产实现：`python/methods/mdm.py`
- 默认 offset：`0.1`
- 工程约束：`gamma >= 0`
- 负 offset-root：截断到 `gamma = 0`
- 旧式 `no_intersection` / `no_offset_root`：不作为默认生产求解结果
- 历史分支：不恢复 `mdm_case6.py`、`mdm_case7.py`、`mdm_case8.py`、`mdm_fine.py`

行级求解诊断通过 `last_solution_info` 暴露，并由 `python/studies/common/runner.py::run_method()` 放入 `extra.solution_info`。

### 3.2 统一指标

当前默认主指标为：

```text
Bias / SD / RMSE / MAE
```

参数视角和工程寿命分位点视角都保留，但 S2R、MdAPE、P95 等作为 diagnostics，而不是唯一主口径。指标定义源：

- 后端：`python/studies/common/metrics.py`
- 前端：`src/lib/metrics.ts`
- 可读规范：`/help/metrics`，源码在 `src/app/help/metrics/page.tsx`

### 3.3 统一蒙特卡洛流水线

公共后端流水线已收束到 `python/studies/common/`：

| 文件 | 当前职责 |
|------|----------|
| `sample.py` | 确定性样本生成 |
| `runner.py` | 统一方法注册解析、参数过滤、调用和结果标准化 |
| `simulation.py` | API 现场蒙特卡洛模拟，供 `/monte_carlo_simulate` 调用 |
| `experiment.py` | 文件型实验，生成 `results.csv / summary.json / manifest.json` |
| `metrics.py` | 标准指标、诊断指标、质量控制 |

`python/main.py` 是 API 层，不应继续堆复杂蒙特卡洛主逻辑。

### 3.4 MDM 真值抽样 full-v1

当前已新增：

```text
python/studies/mdm/run_truth_sampling.py
```

pilot 和 full 都调用 `run_experiment()`，不复写抽样、方法调用或指标聚合逻辑。

full-v1 当前作为研究03 baseline：

- 产物目录：`python/output/truth_sampling/full/`
- `run_label`: `full-v1`
- `seed_namespace`: `2026`
- `total_rows`: `15000`
- 15000 次全部返回候选估计
- 未出现旧式 `no_intersection` / `no_offset_root` 无解
- 1 行 `right_edge_fit` 边界病态候选解保留在 `results.csv`，默认 `summary.json` 按质量控制口径排除

阶段总结见：

```text
docs/MDM真值抽样估计full-v1阶段总结.md
```

---

## 4. 仍未完成或仍是旧口径的内容

### 4.1 旧 AI 模块和旧 public 数据

以下内容仍主要是历史原型或旧口径展示：

- `python/studies/direct_estimation/`
- `python/studies/mdm_delta/`
- `python/models/direct_estimation/`
- `python/models/mdm_delta/`
- `public/ai/data/`
- `src/app/ai/**`

它们仍有参考价值，但不能直接作为当前正式研究结论。主要原因：

- 旧训练和验证数据未按 full-v1 baseline 重新生成。
- 旧指标大量使用 MAE/MRE、total_relative_mse、旧 MDM 成功率等口径。
- 旧 MDM 对比数据可能来自 S4.9 前旧求解器。
- M1/M3 旧页面尚未接入当前 `python/studies/common/metrics.py` 的标准聚合口径。
- M2 和 M4 仍未形成当前版本的正式实现。

### 4.2 旧方法适用范围分片数据

`public/studies/{mdm,mle,wmle}/` 下的分片数据和 `python/studies/{mdm,mle,wmle}/simulate.py` 仍用于兼容旧页面和旧适用范围数据。

当前规则是：

- 旧脚本可以保留作历史兼容。
- 新实验和新方法不要复制旧 `simulate.py`。
- 新实验优先走 `python/studies/common/experiment.py::run_experiment()`。
- 前端若要发布新数据，应先设计从 `results.csv / summary.json / manifest.json` 到 public 数据的转换规则。

### 4.3 前端可视化统一还未完全完成

已有可复用资产：

- `src/components/shared/charts/`
- `src/components/ai/charts/`
- `/help/charts`

但 AI 页面仍包含旧模块命名、旧指标和旧 public 数据引用。后续不能继续每个 AI 页面单独造图表，应把相似表达收束到共享组件和规范化数据适配层。

---

## 5. 当前目标架构

### 5.1 方法层

每个传统参数估计方法应满足：

```text
python/methods/{method}.py
  -> methods.registry.resolve_method()
  -> studies.common.runner.run_method()
  -> studies.common.simulation / experiment
  -> studies.common.metrics
```

要求：

- 一方法一实现文件。
- 不在 `main.py`、研究脚本或前端重复实现估计算法。
- 方法特有诊断放入 `extra`，行级保存。
- 失败、病态、边界候选要保留状态信息，不静默删除。

### 5.2 数据层

文件型实验统一输出：

```text
results.csv      行级主数据
summary.json     默认聚合指标
manifest.json    溯源契约
```

默认统计口径：

- 生成阶段保留所有候选估计。
- `summary.json` 主指标按质量控制后的有效行聚合。
- 如需包含病态候选解的敏感性统计，从 `results.csv` 另算并明确标注。

### 5.3 AI 模块层

当前仍沿用总纲的 M1/M2/M3/M4 划分，但要在统一底座上实现：

| 模块 | 当前定位 | 下一步 |
|------|----------|--------|
| M1 | AI 预测过程量，例如 MDM offset | 以 full-v1 为 baseline，做 NN offset 或最优 offset 对比 |
| M2 | AI 修正传统方法误差 | 先定义基础估计器、修正对象和输出约束，再接统一流水线 |
| M3 | AI 直接估计参数，可含分类辅助回归 | 旧 direct_estimation 仅作原型；需按新指标和新样本重训/重评 |
| M4 | 智能优化传统求解过程 | 等传统方法统一调用和指标稳定后再接入 |

AI 方法也必须产出可被 `aggregate_standard_metrics()` 使用的估计行，不能拥有另一套独立指标体系。

### 5.4 前端层

前端目标：

- Calculator 负责单次估计和多方法对比。
- Methods 的结果分析使用 API 现场模拟。
- Studies 展示预计算结果。
- AI 页面展示 M1/M2/M3/M4 的研究结果，但数据口径必须来自统一流水线。
- 图表优先复用 `shared/charts` 或 `ai/charts`，同类表达不重复造组件。

---

## 6. 推荐下一步里程碑

### M0：文档和接手入口对齐

目标：

- 当前路线图成为 AI 重构接手入口。
- 原总纲标注“战略原意”，不再被误读为已经完全当前化的执行计划。
- 旧 AI 数据、旧 simulate、旧 public 数据被清楚标为历史兼容或待迁移。

验收：

```text
AGENTS.md 能引导到当前路线图；
02-规则.md 能阻止重复 MC/指标实现；
python/studies/common/README.md 说明统一流水线；
python/studies/mdm/README.md 说明 full-v1 baseline；
旧 AI/public 数据不再被误认为当前正式结论。
```

### M1：固定 full-v1 为研究03 baseline

目标：

- 把 full-v1 的 manifest、summary、报告口径固定为后续对比基准。
- 明确 NN offset 或最优 offset 必须同 seed、同网格、同指标、同质量控制口径。

验收：

```text
后续研究03脚本复用 run_experiment()；
新结果能与 full-v1 逐组对齐；
报告明确是否排除 right_edge_fit 病态候选。
```

### M2：实现 NN offset / 最优 offset 对比

目标：

- 在同一参数网格和 seed_namespace 下生成 MDM offset 策略对比。
- 至少包含 fixed offset=0.1 baseline 与新策略。
- 输出仍为 `results.csv / summary.json / manifest.json`。

验收：

```text
不复写抽样和指标；
所有策略有 method_variant；
每个策略可按 Bias/SD/RMSE/MAE 横向比较；
保留 solution_info 或策略诊断。
```

### M3：重新定义 AI 训练数据和 loss 实验

目标：

- 以标准指标和工程分位点指标设计 loss 对比实验。
- 旧 direct_estimation 作为参考，不直接沿用旧模型结论。

验收：

```text
训练/验证/测试划分有 manifest；
loss 实验产物可追溯；
评价走 common metrics 或等价共享实现；
gamma=0 不再使用 gamma 自身作为相对误差分母。
```

### M4：迁移 AI 页面和 public 数据发布规则

目标：

- 设计从实验产物到前端 public 数据的转换规则。
- AI 页面从旧 MAE/MRE 展示迁移到当前标准指标和 diagnostics。
- 同类图表复用共享组件。

验收：

```text
public/ai/data 有版本/manifest；
页面标明数据口径；
M1/M2/M3/M4 页面不重复造相似图表；
旧数据保留历史标识，不混入当前结论。
```

### M5：传统方法和 AI 方法统一横向比较

目标：

- 传统方法、M1、M2、M3、M4 能在同一参数空间、同一样本、同一指标下比较。

验收：

```text
所有方法走 registry + runner；
所有方法产出统一估计行；
比较表同时包含参数视角、工程寿命视角、有效率/失败率、时间；
结论能追溯到 manifest 和 code_version。
```

---

## 7. 新窗口接手阅读顺序

后续 AI 接手时，优先按以下顺序读：

```text
1. AGENTS.md
2. README.md
3. 02-规则.md
4. docs/AI协作协议.md
5. docs/AI辅助三参数威布尔参数估计重构当前路线图.md
6. docs/MDM真值抽样估计full-v1阶段总结.md
7. python/studies/common/README.md
8. python/studies/mdm/README.md
```

禁止把 `_archive/` 作为当前依据。`docs/history/` 可以作为历史追溯，但不能覆盖当前路线图、规则文档和代码事实。

如需追溯原始战略意图，可再读：

```text
docs/oldrules/AI辅助三参数威布尔参数估计重构与实验设计总纲.md
```

---

## 8. Codex/Hermes 执行边界

按 `docs/AI协作协议.md`：

- Codex 负责计划、审查和审批。
- Hermes/mimo 或 Claude Code 负责按计划执行。
- 审批结论使用 `VERDICT: APPROVE / REVISE / BLOCK`。
- 用户保留最终范围、提交、合并、上线决策权。

任何后续执行计划都应明确：

```text
目标
范围内文件
明确不碰的目录
是否会改 public 数据
是否会重跑实验
验证命令
STOP 条件
```

尤其是 public 数据、旧 AI 页面、历史文档迁移和大规模实验输出，不应在没有计划和确认的情况下顺手修改。

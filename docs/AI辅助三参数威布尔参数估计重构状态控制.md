# AI 辅助三参数威布尔参数估计重构状态控制

> 用途：作为多轮 AI Coding / chatbox 接力时的轻量状态控制文档。
> 定位：它不是详细实施计划，不替代总纲；只记录当前推进到哪里、哪些决策已确定、下一轮应从哪里接着做。
> 原则：少而准。只记录会影响后续接手的信息，不把实现细节提前锁死。

---

## 1. 当前权威文档

后续接手本任务时，优先阅读：

1. `AGENTS.md`
2. `README.md`
3. `02-规则.md`
4. `docs/S2R统一评价指标体系进程控制.md`
5. `docs/AI辅助三参数威布尔参数估计重构前因后果.md`
6. `docs/AI辅助三参数威布尔参数估计重构与实验设计总纲.md`
7. 本文档

旧草案、旧审查稿、旧交接说明已归档到 `docs/history/`。它们只作为历史资料，不作为当前执行依据。

---

## 2. 当前总体状态

当前阶段：

```text
S2R 唯一评价指标体系基础迁移已完成。旧 NE/NQE_R/RE_R/Outlier Rate 体系已废止；页面、前后端指标模块、统一实验框架、总纲和接手提示词已同步。下一步是用 S2R 重新计算 S4.7。S4.7 旧 NE 表格不再作为当前结论依据。
```

已完成：

- 明确旧 AI 结果只作为历史原型；
- 清理 `docs` 根目录，只保留当前主线文档；
- 完成重构前因后果文档；
- 完成重构与实验设计总纲；
- 根据外部审稿意见补充总纲中的关键契约性约束；
- S1 旧平台现状梳理：代码现状清单和关键差异分析已融入前因后果文档；
- S2R 统一评价指标：旧 NE/NQE_R/RE_R/Outlier Rate 体系废止，`python/studies/common/metrics.py` 重写为 MdAPE/方向/IQR/尾部/有效率唯一体系；
- S2R 指标规范同步：`/help/metrics` 页面与 `src/lib/metrics.ts` 前端共享函数同步为唯一体系，并在页面和模块头部写明双向同步维护关系；
- S2R 文档同步：总纲、S3 前审查稿、新窗口接手提示词已改为 S2R 唯一口径；
- S2R 基础验证：`python -m pytest -q`、`python -m compileall -q python/studies`、`npx tsc --noEmit`、`npm run build` 已通过；
- S4 规划文档：`docs/AI辅助三参数威布尔参数估计S4统一蒙特卡洛框架规划.md`，已通过外部审查（有条件），审查意见已全部修正；
- S4 统一蒙特卡洛框架实现：`python/studies/common/sample.py` + `runner.py` + `experiment.py`，接入 MLE/MDM/LRE，59 个测试全部通过（含原有 33 个指标测试 + 9 个样本测试 + 9 个方法调用测试 + 8 个端到端测试）；
- S4.5 MDM 调用配置校准 + failure 深度诊断 + 梯度曲线性质探究：定位 failure 全为 `no_intersection`（offset 判据内点条件不满足），默认配置确定为 offset=0.1, gamma_steps=20，61 个测试全部通过；fallback 策略评估确认可消除全部 failure 且精度不降。
- S4.7 MDM 约束边界处理研究（初版）：实现四种 MDM 变体，81 个测试全部通过。初版结论过于乐观（验证空间仅 gamma/eta ∈ {0, 0.1}）。
- S4.7 MDM 约束边界处理研究（修正版）：旧 NE/outlier 口径下的结果已完成并通过审查，但该结论需用 S2R 指标重新计算后再作为当前结论。

尚未开始：

- loss 对比实验（S3）；
- S4.7 新指标重算；
- M1/M2/M3/M4 正式实验；
- 新结果可视化和论文表格。

当前禁止：

- 不要直接训练模型；
- 不要直接用旧 M1/M3 结果写正式结论；
- 不要跳过统一指标和统一样本框架；
- 不要再新增或使用 NE/NQE_R/RE_R/Outlier Rate 作为当前指标；
- 不要在 S4.7 新指标重算前沿用旧 NE 表格写新结论；
- 不要读取 `_archive/`；
- 不要把 `docs/history/` 里的旧方案重新提升为当前主线。

---

## 3. 阶段状态表

| 阶段 | 目标 | 当前状态 | 验收信号 |
|------|------|----------|----------|
| S0 文档收敛 | 保留一个清晰总纲和接力状态 | 已完成 | `docs` 根目录主线清楚 |
| S1 旧平台梳理 | 梳理传统方法、AI 原型、蒙特卡洛脚本、指标和可视化 | 已完成 | 现状清单融入前因后果文档 |
| S2R 唯一评价指标 | 废止旧 NE/NQE/outlier 体系，建立 MdAPE/方向/IQR/尾部/有效率体系 | 基础迁移完成 | `studies/common/metrics.py` + `/help/metrics` + `src/lib/metrics.ts` 同口径，测试/构建通过 |
| S2R 进程控制 | 明确页面与模块双向同步、S4.7 重算前置条件 | 已新增 | `docs/S2R统一评价指标体系进程控制.md` |
| S3 Loss 对比实验 | 用简单 M3 验证不同 loss 的影响 | 未开始 | 输出 loss 对比表和推荐原则 |
| S4 统一蒙特卡洛框架 | 建立共享样本、统一调用、统一结果保存 | 已实现，59 个测试通过，端到端验证通过 | 同一框架能跑传统方法和 AI 方法 |
| S4.5 MDM 调用配置校准 | 定位 MDM failure 来源，校准 offset/gamma_steps 默认配置 | 已完成 | failure 确认为 offset 判据内点条件不满足，默认配置确定 |
| S4.7 MDM 约束边界处理 | 实现 MDM 变体，消除 failure，比较精度 | 待 S2R 重算 | 旧 NE/outlier 表格不再作为当前结论依据 |
| S5 模块整理 | 整理 M1/M2/M3/M4 代表方案 | 未开始 | 各模块可接入统一框架 |
| S6 横向比较 | 在同一参数空间和指标下比较所有方法 | 未开始 | 统一结果表含传统方法与 AI 方法 |
| S7 汇报产物 | 生成组会或论文用表格和图 | 未开始 | 图表可追溯到统一实验配置 |

阶段可以迭代推进，但不能绕过关键前置条件：统一指标和共享样本框架未完成前，不应进入正式模型训练和正式横向结论。

---

## 4. 当前已确定的关键决策

### 4.1 模块划分

AI 模块采用四分法：

- M1：AI 预测过程量；
- M2：AI 误差修正 / 偏差纠正；
- M3：AI 直接估计；
- M4：智能优化算法。

M3 中允许保留分类扩展，但作为 M3 子方向，不单独新增主模块。

### 4.2 评价体系

当前只保留 S2R 唯一评价体系。评价体系包含两套可读视角，使用同一套误差分布指标：

- 参数估计视角：`e_beta=(beta_hat-beta)/beta`，`e_eta=(eta_hat-eta)/eta`，`e_gamma=(gamma_hat-gamma)/eta`；
- 工程应用分位点视角：`e_R=(x_hat_R-x_R)/x_R`，默认 `R ∈ {0.50, 0.90, 0.95, 0.99, 0.999}`。

每个误差分布统一报告：

```text
MdAPE
中位带符号相对误差
[P25, P75] / RelIQR
[P5, P95]
P95(|e|)，必要时 P99(|e|)
有效估计率
```

NE、NQE_R、RE_R、Outlier Rate、TRMSE 以及旧均值型主排序口径已废止。

### 4.3 状态判定

方法输出统一分为：

- `success`
- `failure`

误差很大但数值有效的解仍为 `success`，必须进入尾部统计；只有不收敛、数值非法、物理非法或 gamma 贴到样本最小值等边界病态才是 `failure`。

### 4.4 样本规则

所有方法必须使用共享样本。给定参数组合、样本量和重复编号，应能复现同一份样本。

共享样本用于保证传统方法、M1、M2、M3、M4 可以做配对比较。

### 4.5 Loss 对比实验

正式训练复杂模型前，先用简单 M3 直接估计模型比较 loss。

候选包括：

- 原始参数 MSE；
- log-参数 MSE；
- Huber Loss；
- log-分位 MSE；
- Hybrid log loss。

Hybrid-Loss 第一版使用：

```text
alpha ∈ {0, 0.25, 0.5, 0.75, 1.0}
```

除 loss 外的主要训练条件应固定，并尽量重复多次报告均值和方差。

### 4.6 参数空间

第一版建议参数空间：

```text
beta ∈ {0.8, 1.2, 1.5, 2.0, 3.0, 5.0}
eta ∈ {50, 100, 200}
gamma / eta ∈ {0, 0.05, 0.10, 0.20}
n ∈ {10, 20, 30, 50, 100}
```

如果实验预算有限，主实验可先固定 `eta=100`，多个 `eta` 用于数值稳定性扩展。

### 4.7 数据边界

当前第一版只处理完全观测失效数据。删失数据后续单独规划。

---

## 5. 每轮 AI 接手时应该怎么做

每一轮 AI Coding 工具接手时，应先完成：

1. 阅读当前权威文档；
2. 判断自己处于哪个阶段；
3. 只推进当前阶段合理范围内的任务；
4. 避免一次性试图完成全部总纲；
5. 结束前更新本文档的“接手记录”和“下一步建议”。

接手记录应简洁，建议格式：

```text
日期：
执行者：
本轮阶段：
做了什么：
改了哪些文件：
形成了什么决策：
还有什么问题：
下一轮建议：
```

如果本轮没有实质推进，也应说明原因，避免下一轮误判状态。

---

## 6. 当前推荐下一步

下一轮最适合做：

```text
完成 S2R 全量验证后，用新指标重算 S4.7。
```

S4.7 旧表使用 NE/outlier 口径，已不再作为当前结论。重算时必须输出 MdAPE、方向、IQR、尾部、有效率，并按 gamma/eta、n 分层检查。

旧结论中 min_sigma 的风险来自高 gamma/eta 下系统偏差；需用 S2R 的方向和尾部指标重新确认。

---

## 7. 接手记录

### 2026-05-21

执行者：Codex

本轮阶段：S0 文档收敛

做了什么：

- 将旧路线图、旧草案、旧审查稿和旧交接说明归档到 `docs/history/`；
- 保留新的重构总纲和前因后果文档；
- 根据外部审稿意见补充总纲中的契约性约束；
- 创建本文档作为后续 AI Coding 接力状态控制入口。

改了哪些文件：

- `docs/AI辅助三参数威布尔参数估计重构与实验设计总纲.md`
- `docs/AI辅助三参数威布尔参数估计重构前因后果.md`
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`

形成了什么决策：

- 当前只保留高层总纲，不再扩散多个草案；
- 后续每轮 AI 接手后应更新本文档；
- 下一步从旧平台现状梳理开始，不直接训练模型。

还有什么问题：

- 旧平台代码和脚本尚未系统梳理；
- 统一指标和统一蒙特卡洛框架尚未实现；
- loss 对比实验尚未开始。

下一轮建议：

- 读取总纲和本文档；
- 进入 S1，梳理旧平台现有传统方法、AI 原型、蒙特卡洛脚本、指标和可视化；
- 输出一份短现状清单，不做代码重构。

### 2026-05-22

执行者：Claude Code

本轮阶段：S1 旧平台梳理

做了什么：

- 遍历项目代码，梳理传统方法、AI 原型、蒙特卡洛脚本、指标和可视化；
- 将 S1 梳理结果融入前因后果文档（而非单独新建清单文件）；
- 在前因后果文档中新增 1.1 代码现状清单、3.1/3.2/3.3 可复用资产和关键差异表；
- 为 2.1/2.2/2.4/2.5 各问题补充了具体代码证据。

改了哪些文件：

- `docs/AI辅助三参数威布尔参数估计重构前因后果.md`（融入 S1 梳理结果）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（更新状态和接手记录）

形成了什么决策：

- S1 产物不单独建文件，直接融入前因后果文档，避免文档膨胀；
- 旧平台 11 个传统方法可复用，AI 模型仅作历史参考；
- 旧 loss 的 gamma 归一化问题（用 /γ 而非 /η）是关键差异，总纲 NE 设计正确；
- 统一指标模块是 S2 的正确起点。

还有什么问题：

- 统一指标模块尚未实现；
- 统一蒙特卡洛框架尚未实现；
- loss 对比实验尚未开始。

### 2026-05-22（续）

执行者：Claude Code + 外部审查者

本轮阶段：S2 规划审查

做了什么：

- 创建 S2 统一评价指标规划文档；
- 外部审查者审查 S2 规划，指出 3 个问题；
- 逐一修正审查意见。

改了哪些文件：

- `docs/AI辅助三参数威布尔参数估计S2统一评价指标规划.md`（修正 3 个审查问题）
- `docs/AI辅助三参数威布尔参数估计重构前因后果.md`（修正 MethodResult 返回格式描述）

审查意见及修正：

1. `check_status()` 缺少真值参数无法计算 NE → 签名增加 `beta, eta, gamma` 参数
2. 模块位置与 02-规则.md 冲突 → 改为 `python/studies/common/metrics.py`
3. Outlier Rate 定义歧义 → 明确三态互斥，outlier 不含 failure

还有什么问题：

- S2 已实现，33 个测试全部通过；
- 统一蒙特卡洛框架尚未实现；
- loss 对比实验尚未开始。

下一轮建议：

- 进入 S3 或 S4（需外部审查者确认顺序）；
- S3：用简单 M3 模型做 loss 对比实验；
- S4：建立统一蒙特卡洛调度框架，接入新指标模块。

### 2026-05-22（S2 实现）

执行者：Claude Code

本轮阶段：S2 统一评价指标实现

做了什么：

- 创建 `python/studies/common/metrics.py`，实现全部指标函数；
- 创建 `python/tests/test_metrics.py`，33 个测试全部通过；
- 修正 S2 规划文档中的过期问题和 gamma_hat 检查。

改了哪些文件：

- `python/studies/common/__init__.py`（新建）
- `python/studies/common/metrics.py`（新建）
- `python/tests/test_metrics.py`（新建）
- `docs/AI辅助三参数威布尔参数估计S2统一评价指标规划.md`（修正批注 3、4）

实现了什么：

- `ne()` — 归一化综合误差，gamma 用 eta 归一化
- `quantile_true()` / `quantile_est()` — 真实/估计分位点
- `nqe_R()` / `re_R()` — 分位点误差指标
- `check_status()` — 三态判定（failure/outlier/success）
- `aggregate_param_metrics()` — 批量聚合，三态互斥，精度仅统计 success

测试覆盖（审查要求的最小集）：

- gamma=0 时 NE 有限 ✓
- beta_hat/eta_hat 非法为 failure ✓
- gamma_hat 非有限为 failure ✓
- converged=False 为 failure ✓
- NE>1 为 outlier ✓
- NE<=1 为 success ✓
- 分位点公式正确 ✓
- failure/outlier 不进入精度均值但进入总分母 ✓

还有什么问题：

- 统一蒙特卡洛框架尚未实现；
- loss 对比实验尚未开始。

下轮建议：

- S3 或 S4，需外部审查者确认顺序。

### 2026-05-22（S2.5 实现）

执行者：Claude Code

本轮阶段：S2.5 指标规范同步

做了什么：

- 更新 `/help/metrics` 页面，按 S2 三视角（参数估计/工程分位点/方法可用性）重写指标定义；
- 新增 NE、NQE_R、RE_R、Bias_QR、Failure Rate、Outlier Rate、Time 等指标说明；
- 新增三态互斥（success/failure/outlier）可视化说明；
- 旧 TRMSE 标记为已废弃（被 NE 替代），旧 MSE/MAE/MRE/bias/std 保留为单参数基础指标并标注适用范围；
- 创建 `src/lib/metrics.ts`，camelCase 命名，实现 ne/quantileTrue/quantileEst/nqeR/reR/checkStatus 等基础函数；
- `npm run build` 通过，后端 33 个测试未受影响。

改了哪些文件：

- `src/app/help/metrics/page.tsx`（重写为三视角指标体系）
- `src/lib/metrics.ts`（新建，前端共享指标函数）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（更新状态和接手记录）

形成了什么决策：

- 指标规范页面和共享函数共同承载前端指标定义，不互相竞争权威：页面展示规范，前后端共享函数实现同一公式；
- `src/lib/metrics.ts` 第一版只实现基础函数，批量聚合等前端确有需求时再补；
- 旧指标不删除，标注适用范围和局限性（如 MRE 不适用于 gamma=0）。

还有什么问题：

- 统一蒙特卡洛框架尚未实现；
- loss 对比实验尚未开始。

下轮建议：

- S3 或 S4，需外部审查者确认顺序。

### 2026-05-22（S4 审查修正）

执行者：MiMo

本轮阶段：S4 规划审查修正

做了什么：

- 接收外部审查者对 S4 规划的有条件通过结论；
- 修正 4 个必须项：种子策略改为 hashlib.sha256、结果结构加入 method_variant、ne_threshold 一致性处理、CSV ne 字段记录 success+outlier；
- 同步扩展 S2 `aggregate_param_metrics()` 接收 `ne_threshold` 参数并透传；
- 新增 1 个测试（ne_threshold 透传），加上原有 32 个测试，共 33 个；
- 更新状态控制文档：S4 状态改为"规划审查通过（有条件），待实现"，下一步改为"S4 实现"。

改了哪些文件：

- `docs/AI辅助三参数威布尔参数估计S4统一蒙特卡洛框架规划.md`（4 个必须项修正 + 验收标准 + 文件清单 + 审查记录）
- `python/studies/common/metrics.py`（`aggregate_param_metrics()` 新增 `ne_threshold` 参数）
- `python/tests/test_metrics.py`（新增 `test_ne_threshold_passthrough`）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（状态更新 + 接手记录）

形成了什么决策：

- S4 实现阶段固定默认阈值 1.0，不暴露 `ne_threshold` 参数；聚合函数已具备扩展能力，后续需要时再暴露；
- `method_variant` 是区分同一方法不同方案的关键字段，CSV 和聚合均按此分组；
- 种子使用 `hashlib.sha256` + `repr()` 规范化，不依赖 Python 内置 `hash()`。

还有什么问题：

- S4 三个模块（sample.py / runner.py / experiment.py）尚未实现；
- loss 对比实验尚未开始。

下轮建议：

- 进入 S4 实现：按规划文档创建 `sample.py`、`runner.py`、`experiment.py`，接入 MLE/MDM/LSE，运行小规模端到端验证。

### 2026-05-22（S4 实现）

执行者：MiMo

本轮阶段：S4 统一蒙特卡洛框架实现

做了什么：

- 创建 `python/studies/common/sample.py`，实现 `generate_sample()`，使用 hashlib.sha256 + repr() 种子策略；
- 创建 `python/studies/common/runner.py`，实现 `run_method()`，兼容 MethodResult/5元组/4元组三种返回格式；
- 创建 `python/studies/common/experiment.py`，实现 `run_experiment()`，遍历参数网格 × 样本量，共享样本，调用方法，计算指标，保存逐条 CSV + 聚合 JSON；
- 创建 `python/tests/test_sample.py`（9 个测试）、`test_runner.py`（9 个测试）、`test_experiment.py`（8 个测试）；
- 验证方法：MLE、MDM（需 offset 参数）、LRE（替代未实现的 LSE）；
- 全部 59 个测试通过（33 指标 + 9 样本 + 9 方法调用 + 8 端到端）；
- 修正状态控制文档两处口径（S4 状态、S2 测试数）；
- 修正 S4 规划文档种子字符串顺序（beta|eta|gamma|n|repeat_id）。

改了哪些文件：

- `python/studies/common/sample.py`（新建）
- `python/studies/common/runner.py`（新建）
- `python/studies/common/experiment.py`（新建）
- `python/tests/test_sample.py`（新建）
- `python/tests/test_runner.py`（新建）
- `python/tests/test_experiment.py`（新建）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（状态更新 + 接手记录）
- `docs/AI辅助三参数威布尔参数估计S4统一蒙特卡洛框架规划.md`（种子顺序修正）

形成了什么决策：

- LSE 未实现，用 LRE 替代作为第三个验证方法；
- MDM 必须传 offset 参数，否则抛 ValueError；实验调用时需显式指定；
- runner.py 直接使用 registry 的 resolve_method()，捕获异常返回 failure 结构；
- experiment.py 固定默认阈值 1.0，不暴露 ne_threshold 参数。

还有什么问题：

- S3 Loss 对比实验尚未开始。

端到端验证结果（外部审查者运行）：

- 验证参数空间：beta ∈ {1.5, 2.0, 3.0}, eta=100, gamma/eta ∈ {0, 0.10}, n ∈ {10, 30}, 100 repeats, 3 个方法（MLE/MDM/LRE）
- 结果：3600 行 CSV/JSON 生成成功，耗时约 36.77 秒
- 状态分布：2864 success / 657 failure / 79 outlier
- failure 主要来自 MDM，需 S4.5 诊断原因并校准调用配置

下轮建议：

- 进入 S4.5：MDM 调用配置校准 / 计算预算评估，定位 failure 来源，比较 offset × gamma_steps 小网格，给出默认配置建议；
- S4.5 完成后再进入 S3 Loss 对比实验。

### 2026-05-22（S4.5 实现）

执行者：MiMo

本轮阶段：S4.5 MDM 调用配置校准 / 计算预算评估

做了什么：

- 增强 `runner.py` 失败诊断能力：捕获 MDM 的 `no_intersection` 状态和异常信息，写入 `extra` 字段；
- 编写并运行 `s4_5_mdm_calibration.py`，在验证参数空间上测试 offset ∈ {0.05, 0.1, 0.2} × gamma_steps ∈ {20, 40, 60} 共 9 种配置；
- 分析 failure 来源：所有 failure 均为 `no_intersection`（梯度曲线未达 offset 阈值），无实现 bug、无异常吞没；
- 新增 2 个 runner 测试（failure reason 捕获），总测试数 61 个全部通过。

改了哪些文件：

- `python/studies/common/runner.py`（增强 failure reason 捕获）
- `python/tests/test_runner.py`（新增 2 个 failure reason 测试）
- `python/studies/s4_5_mdm_calibration.py`（新建，校准实验脚本）
- `output/s4_5_mdm_calibration.json`（新建，详细结果）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（状态更新 + 接手记录）

校准实验结果：

| variant | offset | gs | NE mean | NQE_R | fail% | out% | t_mean | t_p95 |
|---------|--------|----|---------|-------|-------|------|--------|-------|
| mdm_o0.05_gs20 | 0.05 | 20 | 0.3843 | 0.0948 | 39.6% | 1.2% | 5.1ms | 7.5ms |
| mdm_o0.05_gs40 | 0.05 | 40 | 0.3876 | 0.0951 | 39.4% | 1.3% | 9.6ms | 12.0ms |
| mdm_o0.05_gs60 | 0.05 | 60 | 0.3857 | 0.0945 | 39.3% | 1.6% | 14.2ms | 17.3ms |
| mdm_o0.1_gs20 | 0.10 | 20 | 0.3864 | 0.0946 | 32.8% | 1.2% | 5.1ms | 7.0ms |
| mdm_o0.1_gs40 | 0.10 | 40 | 0.3870 | 0.0941 | 32.4% | 1.7% | 9.9ms | 12.8ms |
| mdm_o0.1_gs60 | 0.10 | 60 | 0.3875 | 0.0938 | 32.2% | 1.7% | 17.2ms | 24.6ms |
| mdm_o0.2_gs20 | 0.20 | 20 | 0.3884 | 0.0919 | 22.5% | 1.6% | 5.6ms | 8.5ms |
| mdm_o0.2_gs40 | 0.20 | 40 | 0.3893 | 0.0913 | 22.4% | 2.0% | 10.7ms | 14.8ms |
| mdm_o0.2_gs60 | 0.20 | 60 | 0.3876 | 0.0907 | 22.4% | 2.3% | 15.8ms | 22.1ms |

形成了什么决策：

- MDM 默认配置确定为 **offset=0.1, gamma_steps=20**（`mdm_o0.1_gs20`）；
- 选择理由：失败率适中（32.8%），耗时最低（5.1ms/call），精度与高成本配置无实质差异；
- gamma_steps 对失败率几乎无影响（20→60 仅差 <1%），但线性增加耗时（3x），故选最小值；
- offset=0.2 失败率更低（22.5%）但 outlier 率更高（2.3%）且精度略差（NQE_R 0.091 vs 0.095），不做默认；
- 后续实验中 MDM 统一使用 `("mdm", {"offset": 0.1, "gamma_steps": 20, "variant": "mdm_o0.1_gs20"})`。

还有什么问题：

- S3 Loss 对比实验尚未开始；
- MDM 的 32.8% 失败率是方法本身的限制（no_intersection），非 bug，后续可考虑 MDM 变体或 fallback 策略。

下轮建议：

- 进入 S3 Loss 对比实验，使用 S4 统一框架 + 共享样本，MDM 使用 mdm_o0.1_gs20 作为 baseline。

### 2026-05-22（S4.5 failure 深度诊断）

执行者：MiMo

本轮阶段：S4.5 MDM failure 深度诊断（追加要求）

做了什么：

- 编写并运行 `s4_5_mdm_diagnosis.py`，对全部 394 个 failure 样本做抽样复核；
- 分类 failure 原因：100% 为"梯度范围不含 offset"（grad_min > 0.1），0% 为网格太粗或数值噪声；
- 梯度范围统计：grad_min ∈ [0.10, 6.49]，均值 0.45，offset=0.1 远低于梯度最小值；
- failure 参数分布：gamma=0 占 64%（254/394），gamma=10 占 36%；beta 和 n 分布较均匀；
- 修复 `s4_5_mdm_fallback_eval.py` 的 `diffs` 变量未定义 bug，重新运行 fallback 评估；
- 诊断结果保存到 `output/s4_5_mdm_diagnosis.json`。

改了哪些文件：

- `python/studies/s4_5_mdm_diagnosis.py`（新建，failure 深度诊断脚本）
- `python/studies/s4_5_mdm_fallback_eval.py`（修复 diffs 变量 bug）
- `output/s4_5_mdm_diagnosis.json`（新建，诊断摘要）
- `output/s4_5_mdm_fallback_eval.json`（更新，修正后结果）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（状态更新 + 接手记录）

核心结论：

MDM failure 是**理论失败**，不是实现失败、调用配置失败或状态判定口径导致的失败。

证据：

1. 100% failure 样本的 grad_min > offset（0.1），梯度曲线从未下降到 offset 阈值；
2. 增大 gamma_steps 不可能恢复交点（诊断已验证 offset 不在梯度范围内）；
3. 改变 offset 也不可能（除非 offset > grad_min，但那会改变方法语义）；
4. failure 在参数空间中非均匀分布（gamma=0 时更多），说明是参数组合导致的梯度特性。

fallback 评估结果：

| 策略 | NE mean | NQE_R | fail% | out% | t_mean |
|------|---------|-------|-------|------|--------|
| MLE (参考) | 0.350 | 0.081 | 22.5% | 1.8% | 4.8ms |
| MDM 标准 | 0.386 | 0.095 | 32.8% | 1.2% | 4.7ms |
| MDM + fallback_min_sigma | 0.343 | 0.085 | 0.0% | 1.3% | 6.0ms |

- fallback 消除全部 failure，NE 和 NQE_R 反而更好（0.343 vs 0.386）；
- 394 个 no_intersection 样本的 fallback NE mean=0.26，outlier 仅 0.5%；
- 说明 no_intersection 样本用最小 sigma 解质量很好，offset 判据对这些样本过于保守。

形成了什么决策：

- MDM failure 的根源是 offset 判据在某些参数组合下过于保守（梯度曲线整体高于 offset），不是实现 bug；
- fallback_min_sigma 策略可作为 MDM 的可选增强，但需外部审查者确认是否改变方法语义；
- 当前 baseline 仍使用 MDM 标准（offset=0.1, gs=20），fallback 作为备选方案记录；
- S3 实验中可同时比较 MDM 标准和 MDM + fallback，看 loss 对比是否受影响。

还有什么问题：

- fallback 是否应成为 MDM 默认行为，需外部审查者确认（它改变了方法的判定逻辑）；
- S3 Loss 对比实验尚未开始。

下轮建议：

- 进入 S3 Loss 对比实验，使用 S4 统一框架 + 共享样本；
- S3 中可同时测试 MDM 标准和 MDM + fallback，看不同策略对 loss 对比的影响。

### 2026-05-22（S4.6 梯度曲线性质探究）

执行者：MiMo

本轮阶段：S4.6 梯度-位置参数曲线性质探究

做了什么：

- 编写并运行 `s4_6_gradient_curve_study.py`，对 failure 样本做高分辨率梯度曲线分析和灵敏度测试；
- 对 20 个 failure 样本用 2000 点重算梯度曲线，检查 t_min 附近是否有陡降或非单调行为；
- 测试 gamma_steps ∈ {20, 40, 80, 160, 320, 640, 1280} 能否恢复交点；
- 分析梯度曲线的单调性、曲率分布和 t_min 附近行为。

改了哪些文件：

- `python/studies/s4_6_gradient_curve_study.py`（新建，梯度曲线性质研究脚本）
- `output/s4_6_gradient_study.json`（新建，详细分析结果）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（状态更新 + 接手记录）

核心发现：

1. **梯度曲线形状**：从 gamma=0 处开始（grad 最小），随 gamma 增大单调递增，接近 t_min 时梯度值很高（1.0~4.0），**不是下降趋势**；
2. **2000 点高分辨率分析**：19/20 个 failure 样本即使 2000 点也找不到交点，1/20 个样本（rid=13）在 gamma≈0.04 处有交点（grad_min=0.0998，刚好接近 offset=0.1）；
3. **灵敏度测试**：9/10 个样本即使 1280 steps 也无交点，1/10 个样本在 640 steps 时恢复；
4. **t_min 附近行为**：当 gamma → t_min 时，(t_1 - gamma) → 0，伪尺度参数 η_1 → 0，标准差反而急剧增大，梯度上升而非下降。

形成了什么决策：

- MDM failure 不是搜索网格遗漏，是梯度曲线本身不会下降到 offset 阈值；
- 用户假设的"解在 t_min 附近被跳过"不成立：梯度曲线在 t_min 附近是上升的；
- 少数边界样本（grad_min ≈ offset）可通过更细网格恢复，但不是系统性问题；
- failure 的根本原因是 offset 判据对某些参数组合过于保守，不是实现或搜索问题。

还有什么问题：

- fallback 是否应成为 MDM 默认行为，需外部审查者确认；
- S3 Loss 对比实验尚未开始。

下轮建议：

- 进入 S3 Loss 对比实验，S4.5+/S4.6 诊断工作已闭环。

### 2026-05-22（S4.7 MDM 约束边界处理）

执行者：MiMo

本轮阶段：S4.7 MDM 约束边界处理研究

做了什么：

- 创建 `python/methods/mdm_variants.py`，实现四种 MDM 变体：mdm_offset_strict、mdm_offset_constrained、mdm_min_sigma、mdm_allow_negative_gamma；
- 更新 `python/studies/common/runner.py`，新增 MDM 变体函数表，支持通过 variant 名直接调用变体函数；
- 创建 `python/tests/test_mdm_variants.py`，20 个测试全部通过；
- 运行全部 81 个测试（原有 61 个 + 新增 20 个），无回归；
- 编写并运行 `s4_7_mdm_constrained_study.py`，在验证参数空间上比较四种变体 + MLE。

改了哪些文件：

- `python/methods/mdm_variants.py`（新建，四种 MDM 变体实现）
- `python/studies/common/runner.py`（新增 MDM 变体函数表和调用逻辑）
- `python/tests/test_mdm_variants.py`（新建，20 个测试）
- `python/studies/s4_7_mdm_constrained_study.py`（新建，对比研究脚本）
- `output/s4_7_mdm_constrained_study.json`（新建，详细结果）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（状态更新 + 接手记录）

研究结果：

| Variant | NE | NE_std | NQE95 | fail% | out% | t_ms |
|---------|------|--------|-------|-------|------|------|
| MLE (reference) | 0.3500 | 0.2098 | 0.0811 | 22.5% | 1.8% | 5.0 |
| mdm_offset_strict | 0.3864 | 0.2216 | 0.0946 | 32.8% | 1.2% | 4.8 |
| mdm_offset_constrained | 0.3432 | 0.2126 | 0.0848 | 0.0% | 1.3% | 6.2 |
| mdm_min_sigma | 0.3284 | 0.2096 | 0.0814 | 0.0% | 1.8% | 6.1 |
| mdm_allow_negative_gamma | 0.3578 | 0.2084 | 0.0851 | 0.0% | 4.3% | 4.5 |

形成了什么决策：

- MDM strict 的 32.8% failure 不是"理论无解"，而是在当前离散搜索（gamma_steps=20）和扩展验证下，offset 判据的内点条件不满足，failure 样本表现为边界最优；
- mdm_offset_constrained（约束边界解）消除全部 failure，NE 从 0.386 降到 0.343，NQE95 从 0.095 降到 0.085；
- mdm_min_sigma（网格搜索下的最小 sigma 解）在初版验证空间下精度最优（NE=0.328），但扩展验证后 outlier 率飙升；
- mdm_allow_negative_gamma 虽然 0% failure，但 outlier 率偏高（4.3%），仅适合诊断；
- 推荐 mdm_offset_constrained 作为默认 MDM 实现；
- strict 保留作为诊断 variant，不作为默认工程方法。

还有什么问题：

- 最终选择 min_sigma 还是 constrained 作为默认，需外部审查者确认（两者精度接近，min_sigma 更简单，constrained 更符合 MDM 的 offset 理论框架）；
- S3 Loss 对比实验尚未开始。

下轮建议：

- 进入 S3 Loss 对比实验，使用无 failure 的 MDM 变体作为 baseline；
- S3 中可同时比较 min_sigma 和 constrained，看不同变体对 loss 对比结论的影响。

### 重要更正

**撤回"MDM failure 是理论限制"的表述。** 正确表述为：在当前离散搜索（gamma_steps=20）与扩展验证（gamma/eta ∈ {0, 0.1, 0.5, 1.0}）下，无交点样本表现为边界最优；这不等价于"永远不可能找到内点解"（有 4 个 failure 样本 grad_min - offset ≤ 0.001，边界很近）。默认工程实现需要约束边界规则。

**撤回"min_sigma 可作为默认 MDM"的结论。** 初版 S4.7 验证空间仅 gamma/eta ∈ {0, 0.1}，偏向边界场景。扩展至 gamma/eta ∈ {0, 0.1, 0.5, 1.0} 后，min_sigma（网格搜索下的最小 sigma 解）outlier 率从初版 1.8% 飙升至 15.2%（gamma/eta=1.0 时达 33%）。原因是 min_sigma 倾向于选 gamma≈0，当真值 gamma 较大时产生系统性偏差。推荐 mdm_offset_constrained 作为默认。

**撤回"success 样本都是 U 形"的表述。** 初版声称 failure 样本 sigma 单调上升、success 样本呈 U 形。修正版诊断显示：39% 的全部样本（含 success）sigma 曲线单调非降，success 样本中也有 26.7% 是单调的。正确说法是：failure 样本的最小 sigma 全部在边界（gamma≈0），而 success 样本的最小 sigma 多数在内部。

### 2026-05-22（S4.7 修正版）

执行者：MiMo

本轮阶段：S4.7 MDM 约束边界处理研究修正

做了什么：

- 修正 `mdm_min_sigma` 搜索逻辑：创建独立的 `_compute_sigma_curve()` 函数，覆盖完整 [0, t_min) 区间，不再复用 `_compute_mdm_search` 的两段分割逻辑；
- 修正 `mdm_offset_constrained` 注释：将"梯度单调高于 offset"改为"采样点上梯度均高于 offset"，不假设曲线单调性；
- 扩展 S4.7 验证参数空间：gamma/eta ∈ {0, 0.1, 0.5, 1.0}，n ∈ {7, 10, 30}；
- 新增逐样本诊断：sigma_monotone、min_location、grad_min/max、offset_crossing；
- 运行修正版研究，分析结果。

改了哪些文件：

- `python/methods/mdm_variants.py`（新增 `_compute_sigma_curve`，修正 `mdm_min_sigma` 和 `mdm_offset_constrained` 注释）
- `python/studies/s4_7_mdm_constrained_study.py`（重写：扩展参数空间 + 逐样本诊断）
- `output/s4_7_mdm_constrained_study_v2.json`（新建，修正版结果含逐样本诊断）
- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（状态更新 + 接手记录）

形成了什么决策：

- **默认 MDM 推荐 mdm_offset_constrained**，不推荐 min_sigma；
- min_sigma（网格搜索下的最小 sigma 解）在高 gamma/eta 时 outlier 率过高（gamma/eta=1.0 时 33%），原因是它倾向于选 gamma≈0；
- constrained 在所有 gamma/eta 水平均稳健（outlier 5.1%），0% failure；
- 初版结论"min_sigma 最优"是验证空间不足导致的假象；
- MLE 在扩展网格上 failure 率 32.3%、outlier 13.9%，也需要关注。

还有什么问题：

- ~~S4.7 修正版待外部审查者确认~~ → 已通过（有条件），见下方接手记录。

下轮建议：

- ~~外部审查 S4.7 修正版~~ → 已完成；
- 进入 S3 Loss 对比实验。

### 2026-05-22（S4.7 审查通过）

执行者：MiMo + 外部审查者

本轮阶段：S4.7 外部审查

做了什么：

- 外部审查者审查 S4.7 修正版，给出有条件通过结论；
- 处理审查必须修改项：修正结论措辞、修正 min_sigma 描述、写入 gamma/eta 分组表、清理旧文档；
- 处理审查建议项：给 mdm_offset_constrained 增加 fallback_reason 字段；
- 重新运行 S4.7 研究，保存逐样本 NE/status 和 gamma/eta 分组统计到 JSON。

改了哪些文件：

- `docs/AI辅助三参数威布尔参数估计重构状态控制.md`（状态更新 + 接手记录 + 分组表）
- `docs/提示词_新窗口接手.md`（修正旧结论措辞）
- `python/studies/s4_7_mdm_constrained_study.py`（新增逐样本 NE/status + 分组统计 + fallback_reason）
- `python/methods/mdm_variants.py`（增加 fallback_reason 返回字段）
- `output/s4_7_mdm_constrained_study_v2.json`（更新：含 grouped_by_gamma_eta）

审查意见及处理：

1. **必须项 1**：结论措辞从"永远不可能找到内点解"改为"在当前离散搜索/扩展验证下未发现内点交点，且 failure 样本表现为边界最优" ✓
2. **必须项 2**：min_sigma 描述改为"网格搜索下的最小 sigma 解" ✓
3. **必须项 3**：gamma/eta 分组表写入状态文档和 JSON ✓
4. **必须项 4**：清理 docs 根目录旧文档中的过时结论 ✓
5. **建议项 1**：给 mdm_offset_constrained 增加 fallback_reason 字段 ✓

形成了什么决策：

- **默认 MDM 确定为 mdm_offset_constrained**；
- mdm_min_sigma 保留为敏感性对照，不作为默认；
- mdm_offset_strict 保留为诊断变体；
- mdm_allow_negative_gamma 仅诊断用；
- S3 Loss 对比实验中 MDM baseline 使用 constrained，同时保留 min_sigma 作为对照。

还有什么问题：

- S3 Loss 对比实验尚未开始。

下轮建议：

- 进入 S3 Loss 对比实验，使用 S4 统一框架 + 共享样本；
- MDM baseline 使用 mdm_offset_constrained，同时保留 mdm_min_sigma 作为敏感性对照；
- S3 中必须按 gamma/eta 分层看结果，不要只看平均值。

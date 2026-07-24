# G3 Test Consumer R1 设计审查与影响分析

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`91ccc8e6` (origin/main)
> 状态：**设计审查，不改生产代码，等待 Codex R1 裁决**
> Codex verdict：BLOCK — 不得启动 formal、authorize 或 test unseal

---

## 0. 现有实现的根本缺陷

`formal_test_consumer.py`（91ccc8e6）假设 **单一 winner checkpoint** 进入 test。这与协议要求不符：

- 协议 §5.3 要求配对比较（同参数点、同 MC 样本的配对差）和双层 bootstrap（参数点 + 训练 seed）
- 协议 §5.2 A9 要求 10 seed 的均值/SD/最差 seed/方差占比/排序稳定性
- 协议 §4.2 要求传统方法与 NN 共享同一份 test 样本
- 冻结 matrix 中 formal-seed fit_kind 产生 **多模型 cohort**，不是单一 winner

当前实现需要重新设计，不是打补丁。

---

## 1. 每模块进入 test 的完整 checkpoint cohort

### 1.1 权威来源

| 来源 | 位置 | 决定内容 |
|------|------|----------|
| 冻结 matrix | `matrix.py` L13-83 | fit_kind × route × n × seed 的完整展开 |
| 搜索配置 | `A-g2-search-v1.json` L102-178 | 每 rule 的 seeds、routes、selection rule |
| 协议 §7.1 | `02-A-实验协议.md` L193 | screening 3 seeds; formal 10 seeds 完全不相交 |
| 协议 §3.3 | `02-A-实验协议.md` L85 | 24 screening 配置 → top4 → 3 optimizer → 入选配置 × 10 formal seeds |
| staged selection | `formal_executor.py` L1618-1830 | A-E1 五阶段 ledger |
| predecessor chain | `formal_contracts.py` L41 | A-E1→A-E3→A-E2 |

### 1.2 A-E1 checkpoint cohort

| 比较臂 | fit_kind | route | n | seeds | 角色 | checkpoint 数 |
|--------|----------|-------|---|-------|------|---------------|
| 历史诊断 H0-hsm | `historical` | H0_hsm | shared | 10 formal | 诊断（不参与主选择） | 10 |
| 历史诊断 H0-kde | `historical` | H0_kde_scott1024 | shared | 10 formal | 诊断 | 10 |
| 历史诊断 H1 | `historical` | H1 | shared | 10 formal | 诊断 | 10 |
| F2 winner retrain | `winner_retrain` | F2 | 5,7,10,15,20 | 10 formal | **主比较臂** | 50 |
| V winner retrain | `winner_retrain` | V | 5,7,10,15,20 | 10 formal | **主比较臂** | 50 |

**派生逻辑**：
1. `matrix.py` L48-51：`for route in ["F2", "V"]: for n, seed in product(core_n, formal): add(..., "winner_retrain")`
2. Stage2 winner receipt 解析 `selected:A-E1_{loss,architecture,optimizer}` → 具体配置
3. Baseline comparison (`global_better_rule`) 在 validation 上选择 F2 或 V 作为下游 baseline input
4. **但 test 上两个臂都需要评价**（配对比较需要两臂在同一样本上的预测）

**A-E1 总 cohort**：30 (historical) + 100 (F2+V winner_retrain) = **130 checkpoints**

**冲突点**：协议未明确说 test 只评价 winning route 还是两臂都评价。§5.3 的配对比较逻辑要求两臂；但 "test 只评价一次" 可被解读为只评价最终 winner。见 §2 方案。

### 1.3 A-E3 checkpoint cohort

| 比较臂 | fit_kind | route | n | seeds | 角色 | checkpoint 数 |
|--------|----------|-------|---|-------|------|---------------|
| Joint output | `output_form` | selected:F2_or_V:joint | 5 core_n | 10 formal | 主比较 | 50 |
| Independent output | `output_form` | selected:F2_or_V:independent_capacity_matched | 5 core_n | 10 formal | 主比较 | 50 |
| Shared-n DeepSets | `shared_winner_retrain` | S | shared | 10 formal | fixed-vs-shared 比较 | 10 |

**派生逻辑**：
1. `matrix.py` L58-59：`for output_form, n, seed in product(["joint", "independent_capacity_matched"], core_n, formal)`
2. `matrix.py` L63-64：`for seed in formal: add(..., "shared_winner_retrain")`
3. A-E3 的 loss/architecture/optimizer 由 A-E3_loss + A-E3_architecture screening 选择（screening seeds only）
4. `output_form` 和 `shared_winner_retrain` 使用 formal seeds → 进入 test

**A-E3 总 cohort**：100 (output_form) + 10 (shared) = **110 checkpoints**

**前置依赖**：A-E3 的 route 是 `selected:F2_or_V`，需要 A-E1 baseline 结果。由 `reconstruct_deferred_specs` (D8) 从 A-E1 predecessor trace 解析。

### 1.4 A-E2 checkpoint cohort

| 比较臂 | fit_kind | route | n | seeds | 角色 | checkpoint 数 |
|--------|----------|-------|---|-------|------|---------------|
| Selected size retrain | `selected_size_retrain` | selected:A-E3_baseline | 5 core_n | 10 formal | 训练量 finalist | 50 |
| Selected distribution retrain | `selected_distribution_retrain` | selected:A-E3_baseline | 5 core_n | 10 formal | 分布 finalist | 50 |

**派生逻辑**：
1. `matrix.py` L68-69：`for n, seed in product(core_n, formal): add(..., "selected_size_retrain")`
2. `matrix.py` L74-75：`for n, seed in product(core_n, formal): add(..., "selected_distribution_retrain")`
3. `selected_size_retrain` 的 training_size = -1（由 A-E2_training_size selection 决定）
4. `selected_distribution_retrain` 的 distribution 由 A-E2_distribution selection 决定

**A-E2 总 cohort**：50 + 50 = **100 checkpoints**

**前置依赖**：A-E2 依赖 A-E3 winner（loss/architecture/optimizer/output_form）。由 D8 deferred spec 从 A-E3 predecessor trace 解析。

### 1.5 传统方法（非 checkpoint，但共享 test 样本）

协议 §4.2："所有传统方法与 NN 在 test 上共享同一份样本，使用配对比较。"

| 方法池 | 方法 | 角色 |
|--------|------|------|
| 主方法 | MLE, MPS, WMLE, MDM(offset=0.1), LRE | 主排名 |
| 诊断 | MMLE, LSE, MM, PWM | 诊断 |

传统方法无 checkpoint；它们是确定性算法，给定样本直接产生估计。但必须在 **同一份 test 样本** 上运行以支持配对比较。

---

## 2. Test 启封粒度：per-module vs unified G3

### 2.1 所有权威来源

| 来源 | 原文 | 暗示 |
|------|------|------|
| 协议 §7.1 L190 | "module test \| 256 \| 200 \| **每模块独立 namespace**" | 数据层 per-module |
| 协议 §2.3 L51 | "G3、G4、G5 各自使用独立 test namespace" | 跨阶段隔离 |
| 协议 §2.3 L52 | "**模块启封动作**追加写入 run_ledger" | per-module 动作 |
| 协议 §2.3 L50 | "test 在**模块方案**、代码、配置和模型选择冻结后一次启封" | per-module 闸门 |
| 协议 §9 L236 | "**任一模块** formal 运行前必须同时具备..." | per-module 前置 |
| protocol JSON L46-47 | 每模块独立 design/sample seed | 数据层 per-module |
| search JSON L113 | "A-E1 module test, once after **all three routes** are fit" | A-E1 内部闸门 |
| 实施计划 Steps 8-9 | "生成并冻结 pre-unseal bundle → 请求 APPROVE → **one-shot shared paired test evaluation**" | **统一 G3 评价** |
| Oracle formal plan | "请求独立 APPROVE test unseal" (单次) | 统一审批 |
| `formal_contracts.py` L41 | `_PREDECESSOR_BY_MODULE = {"A-E1": None, "A-E3": "A-E1", "A-E2": "A-E3"}` | 包含 A-E2 则强制三者都在 bundle |
| `formal_state.py` | `run_family_id` 自由字符串 | 粒度由调用者决定 |

### 2.2 冲突

| 维度 | Per-module 独立 | 统一 G3 |
|------|-----------------|---------|
| 数据 namespace | ✓ 每模块独立 seed | — |
| state machine | ✓ 每模块可有独立 state file | ✓ 也可一个 state 覆盖三模块 |
| 审批 gate | 代码允许 A-E1 单独 bundle | 实施计划 + oracle 要求统一审批 |
| 评价时机 | A-E1 可在 A-E3 前启封 | 计划要求三者 selection 完成后统一启封 |
| 配对比较 | 模块内配对 | 跨模块综合在 G6 |

### 2.3 结论

**数据层 per-module 无争议。审批/评价时机存在冲突。**

- 代码 **技术上允许** A-E1 单独启封（无 predecessor 依赖）
- 实施计划和 oracle 审查 **要求统一 G3 审批**
- 协议本身 **未明确禁止** 提前启封 A-E1

**本设计不自行裁决。** 提供三个最小方案供 Codex 选择（见 §6）。

---

## 3. Test 输出必须保留的字段

### 3.1 协议要求

| 协议条目 | 要求 | 必需字段 |
|----------|------|----------|
| §5.1 主指标 | 逐样本 L_param + 三分量 | `l_param`, `e_beta`, `e_eta`, `e_gamma`, `legal` |
| §5.2 失败口径 | 失败 penalty=10, 敏感性 2/5 | `failure_penalty`, `legal` |
| §5.3 配对推断 | 同参数点、同 MC 样本配对差 | `point_id`, `sample_id`, `n`, `repeat_id` |
| §5.3 双层 bootstrap | 参数点聚类 + 训练 seed 第二层 | `point_id`, `seed` |
| §5.2 A9 | 10 seed 均值/SD/最差/方差占比 | `seed`, `l_param` per seed |
| §4.2 配对比较 | NN 与传统方法同一样本 | `sample_id` 共享 |
| §5.1 合法条件 | β>0, η>0, γ<min(x), 收敛 | `beta_hat`, `eta_hat`, `gamma_hat`, `sample_min`, `converged` |
| §8 产物 | 逐估计结果 csv.gz | 全部字段 |

### 3.2 最小必需字段集（per-sample record）

```
point_id          # Sobol 参数点 ID（配对键）
sample_id         # 唯一样本 ID（配对键）
n                 # 样本量
repeat_id         # 重复 ID
seed              # 训练 seed（bootstrap 第二层）
module_id         # A-E1 / A-E3 / A-E2
rule_id           # 冻结 matrix rule
fit_kind          # winner_retrain / output_form / ...
route             # F2 / V / S / ...
candidate_id      # 比较臂标识
method_id         # NN 方法或传统方法 ID
beta_hat, eta_hat, gamma_hat   # 估计值
beta, eta, gamma              # 真值
sample_min                     # 合法条件锚点
legal                          # 是否合法
l_param                        # 复合损失
e_beta, e_eta, e_gamma         # 分量相对误差
converged                      # 算法收敛标志
```

### 3.3 当前实现的差距

当前 `formal_test_consumer.py` 只产生 `evaluate_rows` 的聚合输出（n_total, failure_rate, unconditional_mean_l_param 等）。**不保留逐样本记录。** 无法支持配对比较、bootstrap 或 A9 分析。

---

## 4. Test 数据读取前的 preflight

### 4.1 必须验证的项目

| 类别 | 检查项 | 失败行为 |
|------|--------|----------|
| **State** | state == unsealed_once, test_access_count == 1 | fail-closed, 不读 test |
| **Authority** | bundle SHA == state.pre_unseal_bundle_sha256 | fail-closed |
| **Approval** | approval SHA == state.approval_sha256, decision == "APPROVE test unseal" | fail-closed |
| **Code** | bundle.code_commit == 当前 HEAD（或绑定 commit） | fail-closed |
| **Config** | effective_config_sha256 匹配冻结值 | fail-closed |
| **Selection** | selection_trace SHA == bundle.selection_trace_hashes[module] | fail-closed |
| **Checkpoints** | cohort 中每个 fit 的 checkpoint.pt 存在且 SHA 与 fit_status 一致 | fail-closed |
| **Scaler/Cache** | training dataset cache 存在且 hash 一致；scaler 可从 training 重建 | fail-closed |
| **Namespace** | test design/sample namespace 来自冻结 protocol JSON | fail-closed |
| **Leakage** | leakage_audit 确认 test_access_count == 0, 四角色零交集 | fail-closed |
| **Ceiling** | ceiling_hit_report 存在且绑定 | fail-closed |
| **Matrix** | experiment_matrix.csv 已展开且 SHA 匹配 | fail-closed |

### 4.2 Preflight 时序

```
[所有检查在 test 数据生成/读取之前完成]
  1. 读 state → 验证 unsealed_once
  2. 读 bundle → 验证 SHA
  3. 读 approval → 验证 SHA + decision
  4. 验证 code_commit, config SHA
  5. 验证 selection trace SHA
  6. 验证 cohort 中所有 checkpoint 存在 + SHA
  7. 验证 training cache 存在 + scaler 可重建
  8. 验证 leakage_audit, ceiling_hit_report
  [preflight 通过]
  9. 生成 test 参数点（design namespace）
  10. 生成 test 样本（sample namespace）← 此处 test 数据首次存在
  11. 对 cohort 中每个 checkpoint 运行 inference
  12. 对传统方法运行估计
  13. 计算逐样本指标
  14. 写 result receipt（含逐样本记录 SHA）
  15. consume_test_once
```

**关键**：步骤 1-8 全部在步骤 9-10 之前。任何 preflight 失败都不生成 test 数据。

---

## 5. Exactly-once 保证（并发、崩溃、receipt/state 写入）

### 5.1 现有保证（formal_state.py 已实现）

| 机制 | 保证 |
|------|------|
| 文件锁 (`state_path.lock`) | 同一时刻只有一个进程执行 transition |
| Journal (`state_path.journal`) | 崩溃恢复：replay 或 discard 中间状态 |
| No-replace 语义 | state/receipt 文件一旦写入不可覆盖 |
| Ledger 追加 | transition_ledger.jsonl 只追加，不修改 |
| Ledger chain 验证 | 每次 transition 重建并验证完整链 |
| test_access_count | 0→1 (authorize), 保持 1 (consume)；不允许 >1 |

### 5.2 Cohort 评价的额外风险

| 风险 | 场景 | 缓解 |
|------|------|------|
| 评价中途崩溃 | 130 个 checkpoint 评价到第 80 个时进程死亡 | test 数据已生成（步骤 10），但 receipt 未写。state 仍为 unsealed_once。重启后重新评价全部 cohort（test 数据可从 namespace 确定性重建）。 |
| 并发评价 | 两个进程同时尝试评价 | 文件锁阻止并发 transition；但评价本身（步骤 11-13）不在锁内。需要评价级锁或幂等设计。 |
| Receipt 写入后 consume 前崩溃 | receipt 已写但 state 未 transition | Journal 恢复：consume_test_once 的 journal 在写入前创建，崩溃后 replay。 |
| Test 数据缓存 | 评价过程中 test 数据被缓存到磁盘 | 不应缓存 test 数据。每次从 namespace 确定性重建。崩溃后重建即可。 |

### 5.3 设计约束

- Test 数据 **不持久化缓存**（与 training/validation cache 不同）
- 评价过程 **幂等**：相同 namespace + 相同 checkpoint → 相同结果（确定性）
- 崩溃后 **重新评价全部 cohort**（不是断点续传）
- Receipt 包含 **全部逐样本记录的 SHA-256**（不是逐条写入）
- 文件锁覆盖 **整个评价过程**（不仅仅是 state transition）

---

## 6. 冲突与最小方案

### 冲突 A：Test 评价范围（单 winner vs 全 cohort）

**协议证据**：
- §5.3 配对比较 → 需要多臂
- §5.2 A9 → 需要 10 seeds
- §4.2 传统方法共享样本 → 需要同一样本上多方法
- "test 只评价一次" → 一次启封，但可评价多个模型

**方案 A1：全 cohort 评价（推荐）**
- 一次启封，评价模块内所有 formal-seed checkpoint + 传统方法
- 逐样本记录支持配对比较、bootstrap、A9
- 代价：A-E1 需评价 130 checkpoints × 256×200×5 samples ≈ 33M 次 inference
- 优点：完整支持所有研究问题

**方案 A2：仅 winning route × 10 seeds**
- 只评价 baseline selection 的 winning route（50 checkpoints for A-E1）
- 传统方法仍在同一样本上评价
- 配对比较限于 winner vs 传统方法
- 代价：无法在 test 上确认 F2-vs-V selection 是否泛化
- 优点：计算量减半

**方案 A3：分层评价**
- 主评价：winning route × 10 seeds + 传统方法（配对比较）
- 诊断评价：non-winning route × 10 seeds（确认 selection 泛化）
- 历史诊断：3 historical routes × 10 seeds（仅报告）
- 优点：区分主证据和诊断证据
- 代价：需要定义"主"和"诊断"的 receipt 结构

### 冲突 B：启封粒度

**方案 B1：统一 G3 启封（实施计划方案）**
- 三模块 selection 全部完成 → 一个 bundle 覆盖三模块 → 一次 oracle APPROVE → 按模块顺序评价
- 每模块仍有独立 state file 和 namespace
- 优点：与实施计划和 oracle 审查一致
- 代价：A-E1 完成后必须等 A-E3/A-E2 才能启封

**方案 B2：Per-module 独立启封**
- 每模块 selection 完成后独立启封自己的 test
- A-E1 可在 A-E3 开始前启封
- 优点：更早获得 A-E1 test 证据
- 代价：与实施计划不一致；需要三次 oracle APPROVE

**方案 B3：Per-module 启封 + 统一审批**
- 一次 oracle APPROVE 覆盖三模块
- 但每模块按依赖顺序独立执行启封/评价/消费
- 优点：兼顾审批统一性和执行灵活性
- 代价：approval 需要绑定三模块的 bundle

### 冲突 C：传统方法评价的归属

**方案 C1：同一 consumer 内评价**
- test consumer 同时运行 NN inference 和传统方法估计
- 一份 receipt 包含所有方法
- 优点：样本一致性有保证
- 代价：consumer 复杂度增加；传统方法可能在 Python 后端

**方案 C2：分离评价 + 共享样本**
- test consumer 只生成 test 样本并运行 NN inference
- 传统方法在独立步骤中读取相同 test 样本（从确定性 namespace 重建）
- 优点：关注点分离
- 代价：需要保证两者使用完全相同的样本（namespace 确定性保证）

---

## 7. 对现有 `formal_test_consumer.py` 的影响

| 现有设计 | 问题 | 需要变更 |
|----------|------|----------|
| 单一 `winner_fit_id` 参数 | 不支持 cohort | 改为 cohort 派生（从 selection trace + matrix） |
| `evaluate_rows` 聚合输出 | 不保留逐样本记录 | 改为逐样本记录 + 聚合 |
| 单一 receipt | 不支持多模型/多方法 | 改为 cohort receipt（含 per-model 子记录） |
| 无传统方法 | 不支持配对比较 | 需要集成或分离传统方法评价 |
| 无 preflight 阶段 | checkpoint/scaler 验证不足 | 增加完整 preflight |
| 无评价级锁 | 并发风险 | 增加评价过程锁 |
| caller-supplied winner | 不接受 caller 作为科学事实源 | 从 selection trace + matrix 唯一派生 |

**结论**：现有实现需要 **重新设计**，不是增量修补。但 state machine (`formal_state.py`)、bundle/approval 合同、`evaluate_rows` 指标函数和 `FormalDatasetSpec` 安全边界可以复用。

---

## 8. 过度声明修正

`00-A-执行状态.md` 和 `03-A-实验计划.md` 中的 "G3 test consumer 已实现" 和 "闭合 sealed→unsealed_once→consumed 完整生产路径" 是过度声明。实际只实现了单 checkpoint 评价，不满足协议的 cohort 评价、配对比较和 bootstrap 需求。

建议修正为："G3 test consumer 单 checkpoint 原型已实现（awaiting redesign）；完整 cohort 评价设计待 Codex R1 裁决。"

---

## 9. 不变量确认

- [x] 未启动 A-E1/A-E3/A-E2 formal
- [x] 未执行真实 authorize、unseal 或 test access
- [x] 未修改冻结 matrix、protocol、selection rule、failure penalty、科学指标
- [x] 未修改生产 consumer 代码（本棒只写设计文档）
- [x] 真实 test_access_count 仍为 0

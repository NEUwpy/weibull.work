# E4 Validation Suite 状态交接

> 复制本文件到新窗口，即可恢复 Study/01 的 E4 支线进度。  
> 本文件是当前唯一活跃的状态 + handoff 入口；它不是论文正文，也不是正式实验协议的替代品。

## 快速结论

第一轮 smoke/pilot 已完成并通过 Codex 条件审查。由于 Hermes/GLM API 不稳定，原一次性 formal batch 改为 staged execution。

**Step 1 preflight 已完成 (2026-07-10 Hermes)。** Verdict: APPROVE Step 2 (MC generation only)。

当前阶段：`S4_FORMAL_E4_RUNNING` — Step 2 MC generation 已由 Codex 授权，等待 Hermes 执行。

### 第一轮完成状态

- [x] 审查 Ch1-Ch6 与 E3b 证据链，明确 Ch7 需要哪些验证结果。
- [x] 设计 E4 三轨验证合同（E4a/E4b/E4c）。
- [x] 做小规模 smoke/pilot，验证脚本、数据结构、指标、产物目录和 provenance 字段闭环。
- [x] 写回 report，等待 Codex 审查。

### 第一轮未做（遵守 STOP 条件）

- 未直接跑全量 Formal E4。
- 未把 pilot/smoke 结果放入 `artifacts/formal/`。
- 未写 Ch7 正文结论。
- 未修改 Ch1-Ch6、`00-05`、README 或正式 artifacts。

当前 verdict：**APPROVE FIRST-ROUND WORK / AUTHORIZE FORMAL E4 BATCH / DO NOT AUTHORIZE CH7 YET**。

## 可恢复循环协议

本支线采用 **resume loop**，用于应对 Codex 或 Hermes 上下文窗口满载、中断、API 断线或换新窗口。

每一轮 agent 启动后必须按下面顺序执行：

1. 读本文件。
2. 读 `coworker/plans/2026-07-09-study01-e4-validation-suite.md`。
3. 读上一轮 report/review（如果已经存在）。
4. 用 `git status --short` 确认当前工作树。
5. 判断当前所处阶段，只执行当前 gate 允许的下一步。
6. 写 report 或 review。
7. 更新本文件的“循环状态”和“下一步指令”。
8. 如果上下文即将不足，先更新本文件，再停止。

循环阶段：

| 阶段 | 允许动作 | 退出条件 |
|------|----------|----------|
| `S0_PLAN_READY` | Codex 已写 plan/handoff/status | Hermes 接手 |
| `S1_FIRST_ROUND_RUNNING` | Hermes 做 E4 合同 + smoke/pilot + report | report 写完或 blocker |
| `S2_CODEX_REVIEW` | Codex 审查 report、diff、pilot artifacts | `APPROVE / REVISE / BLOCK` |
| `S3_FORMAL_E4_AUTHORIZED` | 只有 Codex 审查批准后，才能写第二轮 formal E4 handoff | 第二轮 handoff 生成 |
| `S4_FORMAL_E4_RUNNING` | Hermes 跑正式 E4 | formal report 写完或 blocker |
| `S5_CH7_AUTHORIZED` | Codex 验收 formal E4 后，才允许 Ch7 写作 handoff | Ch7 草稿完成 |
| `S6_DONE` | E4 支线完成，Ch7 可进入主线整合 | 无 |

当前阶段：`S4_FORMAL_E4_RUNNING` — Step 2 MC generation 已授权，等待 Hermes 执行。
审查文件：`coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md`

已确认的设计决策：
1. E4b 使用 Option C（references only，不部署 NN selector 到边界）
2. E4c evaluation-only（continuous-space training → E3c）
3. E4a 复用 E3b MLP config ((256,128,64), max_iter=300)
4. E4b 使用 targeted ~20 combo 边界子集

Loop 不等于无条件自动推进。以下情况必须停下等待 Codex 或用户：

- 需要从 pilot 升级为 formal。
- 需要从 E4 拆出 E3c。
- 需要跑大规模计算。
- 需要修改正文、`00-05`、README 或 formal artifacts。
- 发现 sealed E3b provenance、输入泄漏或指标口径问题。
- Hermes 无法明确判断下一步是否仍在当前 plan 边界内。

## 当前论文状态

- 项目入口：`D:\weibull\README.md`。
- Study 入口：`D:\weibull\Study\01-study-MDM最小偏移量优化研究\README.md`。
- 最新主线提交：`ccacd35 docs: 重整Ch1-Ch6主体骨架并同步论文初稿`。
- E3b 封存提交：`bedd65a experiment: E3b向量输出重型MLP——Vector-MLP-L6落在oracle阶梯内+来源闭环+11契约测试`。
- Ch1-Ch5：已归位并进入初稿链。
- Ch6：已有 `draft-Ch6-初稿.md`，主张限定为 formal existing-grid 样本自适应可达性。
- E3c：当前 deferred，不作为 Ch6 前置条件。
- E4：作为独立 gate，现在准备启动第一轮 validation-suite 合同与 smoke。
- Ch7：暂不写正文；等 E4 第一轮报告经 Codex 审查后再决定路线。

## 必读顺序

新窗口或 Hermes 接手时按此顺序读：

1. `README.md`
2. `Study/01-study-MDM最小偏移量优化研究/README.md`
3. 本文件：`Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`
4. `coworker/plans/2026-07-09-study01-e4-validation-suite.md`
5. `coworker/handoffs/2026-07-09-study01-e4-validation-suite-hermes.md`
6. `Study/01-study-MDM最小偏移量优化研究/03-论文骨架.md`
7. `Study/01-study-MDM最小偏移量优化研究/draft-Ch6-初稿.md`
8. `Study/01-study-MDM最小偏移量优化研究/E3c-E4-后续决策备忘.md`
9. 需要查 E3b 证据时读：
   - `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/summary.json`
   - `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/model_comparison.csv`
   - `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/seed_stability.csv`
   - `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/E3b_acceptance_report.md`

## 当前派活文件

| 类型 | 路径 | 状态 |
|------|------|------|
| Codex plan | `coworker/plans/2026-07-09-study01-e4-validation-suite.md` | 已创建 |
| Hermes handoff | `coworker/handoffs/2026-07-09-study01-e4-validation-suite-hermes.md` | 已创建 |
| Hermes report | `coworker/reports/2026-07-09-study01-e4-validation-suite-hermes.md` | 已完成 |
| Codex review | `coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md` | 已完成 |
| Superseded batch plan | `coworker/plans/2026-07-10-study01-e4-formal-batch.md` | 保留为设计参考，不直接派发 |
| Superseded batch handoff | `coworker/handoffs/2026-07-10-study01-e4-formal-batch-hermes.md` | 保留为设计参考，不直接派发 |
| Staged execution plan | `coworker/plans/2026-07-10-study01-e4-staged-execution.md` | 已创建 |
| Step 1 handoff | `coworker/handoffs/2026-07-10-study01-e4-step1-preflight-hermes.md` | 已创建 |
| Step 1 report | `coworker/reports/2026-07-10-study01-e4-step1-preflight-hermes.md` | **已完成** |
| Step 1 Codex review | `coworker/reviews/2026-07-10-study01-e4-step1-preflight-codex.md` | **已完成：APPROVE Step 2** |
| Step 2 handoff | `coworker/handoffs/2026-07-10-study01-e4-step2-mc-generation-hermes.md` | 已创建 |
| Step 2 report | `coworker/reports/2026-07-10-study01-e4-step2-mc-generation-hermes.md` | 待 Hermes 写入 |
| Pilot artifacts | `Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/E4_validation_smoke/` | 已生成 |
| Smoke script | `Study/01-study-MDM最小偏移量优化研究/code/run_E4_validation_smoke.py` | 已创建 |
| MC generation script (untracked) | `Study/01-study-MDM最小偏移量优化研究/code/run_E4_mc_generation.py` | 已盘点 — 可复用于 Step 2 |
| Analysis script (untracked) | `Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py` | 已盘点 — 可复用于 Step 3+ |
| Misplaced partial output (untracked) | `Study/artifacts/formal/E4_robustness/boundary_risk_curves.csv` | 已盘点 — MISPLACED + INCOMPLETE，建议 Codex/user 授权删除 |

## E4 三轨定义

### E4a: Feature Ablation

目的：把 E3b 中仅 fold 1 / seed 42 的消融线索，升级为可审查的正式实验合同。

要回答：

- E3b 的收益是否确实来自样本内部尺度、分位数、形状信息，而不是 `n` 查表的复杂版本？
- full features、`n only`、scale/quantile、shape 等特征组应如何跨 fold、seed、`n` 分层汇总？
- 是否需要保留 endpoint、near-optimal/regret、计算成本等诊断？

### E4b: Expanded-Grid / Boundary Robustness

目的：检查 existing-grid 结论遇到边界参数时是否稳定。

候选边界来自当前协议：

- `n`: 加入 `{5, 50}`
- `beta`: 可加入 `{1.2, 6.0}`
- `gamma/eta`: 可加入 `{0.0}` 或近边界值
- repeats: 正式 E4 倾向 `R=500`，第一轮 smoke 必须远小于该规模

要回答：

- Default / L1 / L2 / E3b-style selector 在边界网格上 J1、失败率、endpoint、near-optimal/regret 如何变化？
- 是否需要重新训练模型，还是能复用 sealed E3b 逻辑？
- 如果没有可复用模型 artifact，应把它列为合同设计问题，不可私自伪装成已封存 selector。

### E4c: Out-of-Grid / Continuous-Space Feasibility

目的：判断连续参数空间泛化是否值得启动为正式后续实验。

要回答：

- 是否要从 E4 拆出 E3c？如果需要连续空间训练数据，就必须明确标成 E3c 或新的 formal extension，不能偷塞进 E4。
- 参数分布、train/test 参数空间切分、repeats、delta grid、failure penalty、模型选择、manifest 字段应如何冻结？
- smoke 是否能证明 pipeline 可跑，而不是证明泛化结论成立？

## 第一轮允许写入范围

Allowed:

- 新增或更新本状态交接文件。
- 新增 `coworker/reports/2026-07-09-study01-e4-validation-suite-hermes.md`。
- 新增最小 smoke 脚本：`Study/01-study-MDM最小偏移量优化研究/code/run_E4_validation_smoke.py`。
- 新增 pilot 产物目录：`Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/E4_validation_smoke/`。
- 如果发现 Study 根目录中有旧的活跃状态/交接文件，可移入 `history/`，但必须在 report 中列明。

Not allowed:

- 不改 `README.md`、`00-05`、`draft-Ch*.md`、`draft-作者备注.md`、`E3c-E4-后续决策备忘.md`。
- 不改 `artifacts/formal/` 中已封存产物。
- 不把 pilot/smoke 结果写成正式证据。
- 不启动全量 Formal E4。
- 不写 Ch7 结论。
- 不把 E4 写成“NN 论文”；主线仍是 MDM offset 的层级最优性、部署可达性和边界。

## 状态文档维护规则

- Study 根目录只保留这一个活跃状态交接文件。
- 旧状态、旧交接、旧上下文文件应进入 `history/`。
- 初稿、README、`00-05`、决策备忘、调研子目录的进程控制文件不是旧状态文件，不因本规则移动。
- Hermes 可以更新执行状态、下一步、报告链接和阻塞项。
- 只有 Codex review 后，才能把 `pilot` 改成 `formal approved` 或把结果写成 Ch7 可用结论。

## 下一步

当前下一步：把 Step 2 MC generation handoff 发给 Hermes。

Step 1 report：`coworker/reports/2026-07-10-study01-e4-step1-preflight-hermes.md`
Step 1 Codex review：`coworker/reviews/2026-07-10-study01-e4-step1-preflight-codex.md`
Step 1 verdict：**APPROVE Step 2**，带 cleanup gate。

Step 2 将执行：
- 脚本：`Study/01-study-MDM最小偏移量优化研究/code/run_E4_mc_generation.py`
- 产出：`boundary_risk_curves.csv` + `offgrid_risk_curves.csv` → `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`
- 预计耗时：~110 分钟 (34 combos × 500 repeats × 26 deltas, 4 workers)
- Step 2 只跑 MC generation，不跑分析脚本，不跑 E4a/E4d。

## 下一步指令

当前下一步：Hermes 执行 `coworker/handoffs/2026-07-10-study01-e4-step2-mc-generation-hermes.md`。

Cleanup rule:

- 若派发时附加精确句子 `Cleanup Study/artifacts approved`，Hermes 可删除误置的未跟踪 `Study/artifacts/` 后再跑 Step 2。
- 若不附加该句，Hermes 不得删除/移动 `Study/artifacts/`，只记录忽略该误置目录并验证正确输出路径独立。

Step 2 handoff 命令：

```powershell
$prompt = Get-Content -Raw .\coworker\handoffs\2026-07-10-study01-e4-step2-mc-generation-hermes.md
hermes --skills coworker -z $prompt
```

### 已确认决策

- **E4b model reuse**：Option C confirmed。E4b formal 仅评估 Default/L1/L2/oracle references，不把 NN selector 部署到 boundary。
- **NN 泛化压力测试**：单独设 `E4d_selector_extrapolation` diagnostic，可训练/复现 E3b-style selector 并在 E4b/E4c risk curves 上评价，但不能写成 continuous-space deployment proof。
- **E4c scope**：evaluation-only confirmed。如需 continuous-space training → E3c。
- **E4a config**：复用 E3b MLP config，smoke 的 tiny MLP 不作为正式可比结果。

### Hermes 第一轮已完成

- Report 路径：`coworker/reports/2026-07-09-study01-e4-validation-suite-hermes.md`
- Codex review 路径：`coworker/reviews/2026-07-10-study01-e4-validation-suite-codex.md`
- Pilot artifacts 路径：`Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/E4_validation_smoke/`
- 当前 Step 1 handoff 路径：`coworker/handoffs/2026-07-10-study01-e4-step1-preflight-hermes.md`

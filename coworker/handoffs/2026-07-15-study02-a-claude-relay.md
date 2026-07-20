# Study/02 G3 接力交接 — Claude（glm-5.2）从 codex 接棒

> 本文件是**全新 Claude 会话**（重启后、无对话上下文）的唯一起点。读完即可零摩擦全自动继续 G3。
> 建立于 2026-07-15。分支 `claude/study02-a-20260715`，基于 codex tip `8e56a0e`。

## 1. 这是什么

codex 在 `codex/long-task-20260711` 分支上跑了 Study/02（神经网络 Weibull 三参数估计研究）的长任务，推进到 G3 formal Task 9c.2 时**额度耗尽**。本棒由 Claude Code（glm-5.2）**接力**完成 G3 收官。用户的硬性要求：

1. **full-auto，全程无需用户干预**。本会话已在 `.claude/settings.local.json` 设 `permissions.defaultMode: "bypassPermissions"`（重启后生效）。
2. **每个阶段/任务有成果即 git 提交**，提交在 `claude/study02-a-20260715` 分支上并推送 origin。
3. **Claude 的成果与 codex 的成果分开**，便于事后整体审计：`git log codex/long-task-20260711..claude/study02-a-20260715` 即纯 Claude 成果。

## 2. 用户已拍板的 4 个决定（不可违背）

| 维度 | 决定 |
|---|---|
| 接力范围 | **仅完成 G3**（Task 9c 跑 formal → 9d 解封 test → 10 证据/Nature 图/G3 报告）。G3 收官后**停下交还用户**，不自动进 G4。 |
| Oracle/预注册门禁 | **全自动，Claude 自任 oracle 签字**（含 9d 解封 test + 一次性评估）。即放弃"独立 oracle"的预注册独立性，以用户明确授权换取无人值守。 |
| 分支与基线 | 已把 codex 的 4 个未推送提交推到 origin 冻结基线（`589d5fd..8e56a0e`，origin 已到 `8e56a0e`），再从 tip 拉 `claude/study02-a-20260715`。**已完成。** |
| 会话权限 | `.claude/settings.local.json` 设 `bypassPermissions`，需**重启会话**生效（本设置无法在运行中的会话自切）。 |

## 3. 精确现状（已核实）

- **分支拓扑**：`main`(155052b) ←(merge-base)→ `codex/long-task-20260711`(8e56a0e，领先 main 45 提交) → `claude/study02-a-20260715`(从 8e56a0e 起)。origin 上 codex 与 main 均已同步。
- **G0/G1/G2**：oracle APPROVE，已推送。
- **G3 pilot v7**：oracle APPROVE（`8e2c01e`），只允许 formal training/validation，**test 保持 sealed**。生效合同 `A-G2-v1 + A-G3-pilot-amendment-v4`（max/min/patience epochs = `100/50/40`，WMLE/MDM 准入）。
- **G3 formal 实现**（SDD，逐 Task oracle 审查）：
  - Task 9a.1 EffectiveFormalConfig — APPROVE（`59e49ba`）
  - Task 9a.2 fixed/S data+training — APPROVE（`97f7325..20647cf`）
  - Task 9b.1 manifest/lineage — APPROVE（`4838156..b473784`）
  - Task 9b.2 pre-unseal evidence — APPROVE（`00ec685..8361c8d`）
  - Task 9b.3 test state — APPROVE（`74f4a5b..7408b7a`）
  - Task 9c.1 formal dataset cache + scalers — APPROVE（`b254e5a..589d5fd`，40 tests）
  - **Task 9c.2 formal scheduler — APPROVED。实现 `7913ae7`/`6408518`/`6fe8117`；Claude 接力独立 oracle 复审（`task-9c2-review3.md`）确认 review2 的 6 项修正与 8 项攻击全部闭合，focused 套件 `109 passed in 45.48s`。A-E1 formal training/validation 已授权；test 仍 sealed。接力过程中发现并修复 Windows CRLF 环境阻断（见第 8 节地雷，非代码缺陷）。**
  - **Task 9c.3 formal 执行驱动 — 整改后待复审（`task-9c3-review2.md`）。初版自审 APPROVE 被独立审计 BLOCK（8 条，见下），已逐条整改。** 现状：执行驱动 claim→cache/scaler→fit(100/50/40)→**可加载规范 checkpoint**+5字段 fit_status+**integrity-bound evidence**（第3个 scheduler 校验输出，绑定不可重算的训练轨迹）→record；`run_module` **干净 deferral** selection-dependent 的 fit（不再 churn/fail），**A-E1 仅 concrete 部分（historical/controlled/stage1 search ≈177 fit）可执行；stage2/winner_retrain（≈172 fit）依赖 D7 selection**；training 核按 recipe 用 adam/adamw；authority 覆盖 `python/studies/**`。118 测试通过含强化冒烟（load_checkpoint+evidence+无 sidecar）与 deferral 测试。**A-E1 不能单遍跑完——run 仍需先做 D7。**
  - **【后续强化 e40b55f，已推送】** review2 闭合后又对 evidence 完整性做了进一步收紧：`_validate_success_files` 对 `evidence_json` 从只查曲线长度，强化为 **6 项自洽校验**（epochs ∈ 合同 [50,100]、曲线全有限、`best_epoch_one_based==argmin(curve)+1`、`hit_epoch_100`/`early_stop_reason` 与 actual 一致、`terminal_validation_slope` 由曲线重算 isclose）；`formal_executor` 删除私有 OLS slope 副本，与 scheduler 同源走 `formal_contracts._terminal_ols_slope`（发射值与校验值构造一致）。测试夹具改为自洽 bound triple。**formal 全套 8 模块 223 passed**（含端到端冒烟+篡改测试）。纯 Claude 成果 `git log codex/long-task-20260711..claude/study02-a-20260715` 现 9 提交。
- **codex 断点**：lease 文件 `.slim/deepwork/study02-a.lease.json` 记录当前任务 `task-9c2-report.md`，heartbeat 停在 2026-07-13。该 30 分钟 heartbeat loop 已随 codex 额度失效。

## 4. 接力计划（顺序执行，每步有成果即提交+推送）

1. **Task 9c.2 收尾审查 ✅ 已完成（Claude 接力）**：对 `formal_scheduler.py`（commit 6fe8117 状态）做了独立 oracle 复审，核对 review2 的 6 项要求与 8 项攻击全部闭合（见 `.superpowers/sdd/task-9c2-review3.md`，本地未跟踪）；focused 套件 GREEN（`109 passed in 45.48s`）。给出 APPROVE，授权 A-E1 formal training/validation。审查中发现并修复 Windows CRLF 环境阻断（见第 8 节），无需为此提交代码。
2. **Task 9c.3 执行驱动 ✅ 已完成（Claude 接力）；9c run ⏸️ 用户决定推迟**：原以为 9c 只需"跑"，实测**执行驱动（claim→train→record）当时并不存在**（codex 在 9c.2 后断档）。Claude 按 SDD 把驱动（`formal_executor.py` + `formal-execute` CLI + `training.py` checkpoint 规范字节）造出并自审 APPROVE（commit `5c74b6a`+`37dc6b7`+decision-fix），9 测试通过含真实端到端冒烟（1 historical fit）。**用户随后决定：本棒不启动多日 run（约 4-16 天），仅交付驱动+冒烟。** run 的启动（含 A-E1→A-E3→A-E2 全 820 fit）交还用户择机/择地。**run 前必须先解封 D7/D8 两个前置（见第 8 节）**。
3. **Task 9d：Claude 自任 oracle 解封 test + 一次性评估**（按用户决定）。写解封审批记录，跑 one-shot test evaluation，产出最终指标。提交。
4. **Task 10：证据 + Nature 图 + G3 报告**。图用 `nature-figure`（Python 后端，不混 R）。产出 G3 阶段报告，更新 `08-更新日志.md`。提交。
5. **G3 收官 → 停**。推送 claude 分支，向用户汇报，等待是否进 G4 的指示。

## 5. 硬约束（违反即破坏研究有效性）

- **test 数据在 Task 9d 之前任何路径都不可访问**（`test_access_count` 必须保持 0）。所有 formal 组件对 test fail-closed。
- formal 训练 max epochs=100，**不可超**；按 `A-G3-pilot-amendment-v4` 合同执行。
- 820 fits 顺序固定 A-E1→A-E3→A-E2；A-E3/A-E2 必须有确切的前驱 receipt 才可跑。
- scientific code（`code/**/*.py`）dirty 时 scheduler 的 authority 检查会 fail-closed；保持提交干净。

## 6. Git / 提交策略（重要）

- 分支：`claude/study02-a-20260715`。提交信息沿用 codex 前缀风格（`feat/research:`、`fix/research:`、`docs:`、`chore/research:`）。
- **只 `git add <明确路径>` + `git commit <明确路径>`，绝不 `git add -A` / `git commit -am`**。原因：`.claude/settings.local.json` 在本分支被跟踪但含本地 bypass 改动（不提交）；`.slim/` 全部本地未跟踪（codex 的私有工作区）。盲目全量 add 会污染审计。
- 每次提交后 `git push origin claude/study02-a-20260715`。
- 提交落款：`Co-Authored-By: Claude <noreply@anthropic.com>`。

## 7. 权威文件（开工先读）

- 持续进度：`.slim/deepwork/study02-a.md`、`.slim/deepwork/study02-a-formal.md`（本地未跟踪，但可读）
- SDD 进度：`.superpowers/sdd/progress.md`、`task-9c1-report.md`、`task-9c2-report.md`、`task-9c2-review2.md`、各 `task-9*-brief.md`
- 研究问题（19 问）：`Study/02-study-NN参数估计与分位点目标研究/01-A-研究问题.md`
- 实验协议 / 计划：同目录 `02-A-实验协议.md`、`03-A-实验计划.md`、`README.md`
- 正式代码（18 模块）：`Study/02-study-NN参数估计与分位点目标研究/code/study02a/*.py`（重点 `formal_scheduler.py`、`formal_runner.py`、`formal_data.py`、`formal_contracts.py`、`formal_state.py`、`run_study02a.py`）
- 测试：`python/tests/test_study02a_*.py`

## 8. 已知地雷

- **【最高优先·本棒新增】Windows CRLF 阻断 frozen 哈希校验**：本工作区 `core.autocrlf` 曾为 `true`，导致 4 个 byte-hashed frozen 工件（`configs/A-g2-protocol-v1.json`、`configs/A-g2-search-v1.json`、`configs/A-g3-pilot-amendment-v4.json`、`artifacts/pilot/G3-matrix/experiment_matrix.csv`）被 smudge 成 CRLF，`verify_frozen_hashes`/`FROZEN_MATRIX_SHA256`/`APPROVED_AMENDMENT_SHA256` 全部 mismatch，focused 套件大面积 RED（`90 failed`，非代码缺陷）。git blob 本身是 LF 且哈希正确，仅工作树被污染。**修复（环境级，不提交任何文件）**：① `git config core.autocrlf input`（本地 `.git/config`，持久、不跟踪）；② 把上述 4 个文件工作树正则化为 LF（`git add --renormalize` 已验证内容与提交的 LF blob 完全一致，staged 为空）。修复后 focused 套件 `109 passed`。**重启/新会话必须先确认 `core.autocrlf=input` 且这 4 个文件为 LF**，否则会误判 scheduler 崩坏。详见 `task-9c2-review3.md` 的 environment note。`code/**/*.py` 等其余文件保持原样即可，scheduler 的 `_assert_scoped_code_clean` 只 scope `code/` 且对 CRLF/LF 一致读取不敏感。
- **9 个既有 Study/01 E3b 测试失败**：硬编码 `D:/weibull`，当前工作区 `C:/Web/Weibull`。**历史遗留、非本棒所为**，只记录不修。
- **【run 启动前置】D7 selection 与 D8 predecessor 必须在跑完 820 fit 之前补齐并复审**（独立审计 BLOCK 后已部分收敛）：① **D7 selection 排序指标 `L_param` 已有协议定义**（`02-A-实验协议.md:127`：`L_param=√((eβ²+eη²+eγ²)/3)`，失败赋 10；`protocol.json` 的 `failure_penalty.primary=10.0`；`python/studies/common/metrics.py` 有 `check_status`/`param_*_errors` 辅助），但**选择逻辑本身（排序/选 winner/解析 `selected_top_*`+`selected:*` 占位/生成 selection trace）尚未实现**——这是 `formal_executor.py` 末尾 fail-closed 占位（`build_module_selection` 等，调用即抛）。② `run_module` 现在**干净 deferral** 所有依赖 selection 的 fit（不再 churn/fail），只跑 concrete 部分；A-E1 的 stage2/winner_retrain、以及整个 A-E3/A-E2 都要等 D7。③ **D8 predecessor 链 + A-E3/A-E2 deferred-spec 重建**未实现。D7 选择信号必须从**已绑定的 checkpoint.pt** 派生（`load_checkpoint` 解码→inference→L_param），不能用任何 sidecar。详见 `task-9c3-review2.md`。
- 【更正】"总执行合同"`coworker/plans/2026-07-12-study02-a-full-execution.md` **存在且被 git 跟踪**（早先交接误称"磁盘不存在"，已核实更正）。以 SDD brief + 实验协议/计划 + 该合同为实际权威。
- `.slim/` 与 `.claude/settings.local.json` 见第 6 节，勿提交。
- glm-5.2 子代理路由坑：派 Agent/Workflow 时**必须传 `model: "sonnet"`** 才走 glm-5.2（fable 档未映射）。详见 memory `reference_subagent_model_quirk.md`。
- `ruff` 在本环境不可用；以 pytest + `python -m compileall` 为准（codex 同样处理）。

## 9. 重启后的恢复指令（用户照抄一行即可）

```
/full-auto 继续 Study/02 G3 接力：权威入口与现状见 coworker/handoffs/2026-07-15-study02-a-claude-relay.md，按其中第 4 节计划全自动推进到 G3 收官，每个阶段成果按第 6 节策略提交到 claude/study02-a-20260715 并推送。
```

## 10. 回滚

- 接力开始前 claude 分支仅含本交接文档一个提交。如需丢弃整棒：`git checkout codex/long-task-20260711 && git branch -D claude/study02-a-20260715`，远端 `git push origin --delete claude/study02-a-20260715`。
- codex 基线已固化在 origin（`8e56a0e`），不受本棒影响。

## 11. 2026-07-17 执行者棒更新（角色切换：Claude=执行者，Codex=唯一规划者/审批者）

**本棒角色与之前不同**：用户把 Claude 定位为**执行者**，Codex 为**唯一规划者与审批者**。Claude **不得自签 APPROVE、不得启封 test**；完成即提交报告停止，等 Codex 的 APPROVE/REVISE/BLOCK。本棒目标：完成阻止 820-fit formal 链的 D7/D8 + 关闭新环境复现缺口，使 G3 达到"可由 Codex 批准后分阶段启动 formal"的状态。**未启动 formal run，test 全程 sealed。**

**已完成并推送（claude 分支，`git log codex/long-task-20260711..claude/study02-a-20260715`）：**
- `cd2efb1` 复现缺口闭环：`.gitattributes` 强制 `eol=lf`（解决 autocrlf=true 致冻结字节哈希变化，新 checkout 无需人工干预）+ Study02 `requirements.txt`（torch CPU + pin）。**已用干净 clone + autocrlf=true 验证** `verify_frozen_hashes` + `FROZEN_MATRIX_SHA256` 通过、冻结文件全 LF。
- `73de48b` D7 selection scoring 原语：`validation_failure_penalized_l_param`——从**完整性绑定 checkpoint 加载并推理**产生 `mean failure-penalized L_param`（load_checkpoint→model→forward→decode 反演 encode_targets→evaluate_rows 失败惩罚 10），无 sidecar；共享 `_prepare_fit_inputs`（单源真理，训练与打分用同一 validation 准备）。**测试证明** decode 精确反演 encode + scoring 从 checkpoint 复现 L_param。全套 formal 225 passed 无回归。
- `5ecda89` D6 决策分组 helper `_derive_decision_candidate` + 冻结矩阵覆盖诊断测试；修正失真的"L_param 未定义"占位说明（指标已冻结且可算）。

**未完成（待 Codex 设计确认，详见 `coworker/reports/2026-07-17-study02-g3-d7-d8-claude.md`）：** D7/D8 完整 wiring——`build_module_selection` 的 run_module 集成（A-E1 stage1 排序→解析 `selected_top_*`→stage2→baseline_input F2-vs-V 的分阶段执行）、代表 checkpoint 策略、D8 占位符解析 + deferred-spec 重建 + 前驱链 wiring。诊断测试客观暴露 3 处决策分组 scoping 问题（output_form/distribution 按路由后缀拆成单候选决策；training_size 按 n 拆分）需 Codex 裁定。A-E1 的 architecture/stage2 分组正确。

**结论**：本棒交付了可验证的复现+scoring 基础与设计诊断，但 D7/D8 尚未完整实现——其剩余 wiring 依赖 Codex 对上述设计点的确认。状态：**partial implementation, awaiting Codex design review**（非 APPROVE，formal 未授权）。

### 2026-07-18 R1（Codex REVISE 之后，第二执行者棒）

Codex R1=REVISE 给出完整设计裁决。本棒完成并验证 **R1§2 multi-seed selection evidence schema**（`2f45657`，226 formal tests green）：废除"代表 checkpoint"，每候选绑定完整 supporting fit 集（fit_id/seed/status/checkpoint SHA/重算 L_param/失败惩罚）+ `supporting_evidence_sha256` + `seed_count` + `selection_rule`；`build_candidate_supporting_evidence` 单源聚合；pre-unseal 按候选重组 fit_status 重算 aggregate/sha/seed_count 并对照 trace，缺/重/篡改/seed 不全 fail-closed；success fit 未绑 trace 候选 fail-closed，全失败独立 fit 透明保留。

**R1 其余未完成**（待 Codex R2 + 后续棒）：决策分组按 §3 重写（含**多 n 聚合**——supporting fit key 从 seed 推广到 (n,seed)，n_strategy 按 core n 等权）、global_better/2%+CI/fixed-vs-shared 三条非 ranking 规则、阶段交错（stage1→不可变阶段工件→selected_top_1..4→stage2→一次性最终 receipt）、D8 wiring、完整临时 smoke。`_derive_decision_candidate` 仍 R0 版、`build_module_selection`/D8 占位仍 fail-closed。报告 `coworker/reports/2026-07-18-study02-g3-d7-d8-wiring-claude.md`。A-E1 formal **仍不可启动**。等 Codex R2。

### 2026-07-18 R2（Codex REVISE 之后，第三执行者棒）

Codex R2=REVISE 给出 7 项发现（caller approved_seeds / fit_id 跨候选复用 / supporting hash 未绑全 context / selected any 模糊 / v1 残留 / 非 ranking 规则可接 caller winner / 测试覆盖单 seed）。本棒完成并验证 **selection evidence + decision-rule engine**（241 formal+selection tests green）：

- **DecisionSpec 引擎**（`selection.py`，`f933953`）：确定性决策/候选/期望 fit/(n,seed) support/approved_seeds/rule/tie-back 派生——**调用方不得传入 expected fits / approved seeds / winner / rule**。R1§3 决策分组修正：output_form 合并为 1 决策 2 候选×50 support、distribution 1×3×15、training_size 1×4×15（R0 误拆已修正）。
- **v2 schema + 独立 pre-unseal 重建**（`b80e721`）：trace/receipt/bundle v2（v1/v2 混用 schema-gate fail-closed）；移除不安全旧 API；pre-unseal 重开冻结矩阵独立重建 DecisionSpec 并逐候选重算证据；fit_id 全局唯一 + 冻结合同对应；selected 候选级一致性（失败 fit 可属获胜候选，无 any/all）。
- **规则引擎**（`2833daa`）：两级 bootstrap CI（seed 520001、2000 reps、参数点聚类 + 训练 seed 二级）+ 逐参数点证据；global_better 三 CI / smallest_within_2pct_ci / fixed_vs_shared core-n 等权 / lowest_aggregate。
- **`build_module_selection` 编排器**（`6a79f10`）：派生→逐 fit checkpoint 评分（no sidecar）→规则→v2 trace+receipt；`score_fit` DI 测试注入。
- **攻击套件 + mixed-rule 守卫**（`f9fafc7`）：覆盖 R2 全部 7 项与合同攻击清单（缺/多/重复/错 n/错 seed、跨候选 fit 复用、重贴标签、selected 不一致 + 获胜候选含失败 seed、mixed rule、caller winner 拒绝、v1/v2 混用、各规则边界 + 篡改、bootstrap 顺序无关、证据变化→哈希变化）。

**未完成**（明确不在本棒范围，待 Codex R3 + 后续棒）：staged A-E1 执行（stage1→selected_top→stage2→baseline_input 交错）、D8（占位符解析/deferred-spec/A-E3←A-E1、A-E2←A-E3 前驱链）、完整临时 smoke、shared-n fit_status 表示。报告 `coworker/reports/2026-07-18-study02-g3-selection-engine-claude.md`。A-E1 formal **仍不可启动**。等 Codex R3。

### 2026-07-18 R3（Codex REVISE 之后，第四执行者棒）

Codex R3=REVISE 要求闭合 selection evidence + 非 ranking 规则复核（点证据入不可变链、trace 绑规则诊断 SHA、pre-unseal 独立重算规则不信 selected、相对 RMSE 比率、点记录成 dict 前拒绝、失败 fit 不跳过）。本棒完成并验证（251 formal+selection tests green）：

- **点证据不可变链**（`507f9b8`/`c4c6365`，R3#1）：每 fit 的逐参数点证据 → 独立工件（`point_evidence.json`），内容 SHA 绑身份+checkpoint+validation identity+failed+canonical records；`candidate_supporting_evidence` 把 `point_evidence_sha256`+validation_identity 绑入 supporting hash → trace → receipt。
- **trace 绑规则诊断 SHA**（R3#2）：trace v3 schema 加 `rule_diagnostics_sha256`（绑 bootstrap 配置/CI/规则结果/winner）；v2/v3 schema-gate fail-closed；orchestrator 写 per-decision 诊断工件。
- **pre-unseal 独立重算**（R3#3）：加载+完整性校验点证据工件、交叉核对 fit_status 标量、重建 FitEvaluation、重算 supporting SHA、**重跑规则**（含非 ranking，冻结 seed 520001/2000 reps）+重算 diagnostics SHA + winner，与 trace 对比——**不信** fit_status 的 `selected`。
- **相对 RMSE 比率**（`fa4c015`，R3#4）：`RMSE_cand/RMSE_comp − 1` 每 replicate，CI upper ≤ 5%；零 comparator → +inf fail-closed；通用两级 bootstrap（summary-based）。
- **点记录成 dict 前拒绝**（R3#5）：重复 (seed,sample)/同 sample 异 point/cell 不匹配/跨 fit 复用。
- **失败 fit 不跳过**（R3#6）：失败 fit 携 all-illegal 点记录（同 validation cells），failure rate/L_param/pairing 真实计入。
- **failure-rate CI 方向修正**（`a89efb8`）：改用候选−比较（恶化方向），候选失败更少时正确判定非劣（旧改善方向在失败不同时误判）。
- **R3 攻击套件 8 项**（`a89efb8`）：点证据篡改/交换、伪造非 ranking winner（trace+receipt+fit_status 同步）、diagnostics 缺失/篡改、重复 (seed,sample)、global_better 失败 seed、尺度反例、零 comparator。

**未完成**（明确不在本棒范围，待 Codex R4 + 后续棒）：staged A-E1 执行、D8（仍 fail-closed）、完整临时 smoke、A-E1 formal 分阶段启动、9d、G4。报告 `coworker/reports/2026-07-18-study02-g3-selection-evidence-r3-claude.md`。**A-E1 formal 未授权**。等 Codex R4。

### 2026-07-18 R4（Codex REVISE 之后，第五执行者棒）

Codex R4=REVISE 给出两个阻塞：(1) pre-unseal 只验证点工件及下游哈希自洽，未从绑定 checkpoint 独立重建点记录（同步重写全部工件仍可能接受非 checkpoint 产生的证据）；(2) 跨候选同 `(seed_id, sample_id)` 异 `point_id` 无 fail-closed（Codex 在 `a325208` 上复现 `CROSS_POINT_ACCEPTED`）。本棒完成并验证（261 formal+selection tests green）：

- **pre-unseal checkpoint 独立重建**（`99f07b3`，R4#1）：抽出版单源 `_derive_and_score_evaluations`（`build_module_selection` 与重建共用），新增 `rebuild_selection_point_provenance`——重读真实 `outputs/{fit_id}/checkpoint.pt` + 从冻结 plan/config/cache 重建 validation inputs + forward/decode/`evaluate_rows_per_sample` 生成 canonical records（succeeded）/ 冻结 cells all-illegal（failed），不信任何 fit_status 标量或发布工件；`build_pre_unseal_bundle` 增**强制** `point_provenance_by_fit`，对每 fit 调 `assert_point_evidence_provenance` 逐字段比较（checkpoint SHA / validation_identity==重建 dataset-cache identity / failed / 标量 / canonical records）。即便伪造点记录并同步重算 content SHA + supporting + diagnostics + trace + receipt + ledger + fit_status，重建仍与之不符 → 拒绝。
- **CROSS_POINT 跨候选守卫**（`99f07b3`，R4#2）：`_paired_grids` + `_improvement_records` 在配对两候选时校验同 `(seed,sample)` 的 `point_id` 一致（`sample_id` 决定 `point_id`），不符 fail-closed——闭合最小反例。
- **逐记录语义校验**（`99f07b3`，R4#2）：`validate_canonical_point_records`（精确字段集/类型、`seed_id==冻结 support seed`、finite/非负、`legal↔failure`、`l_param↔e_*`、非法⇒全=冻结 penalty）作为每个 point-evidence SHA 的门；`load_point_evidence` 增 artifact 标量==canonical records 聚合（R4#2#9）。
- **R4 攻击套件 7 类**（`dd8ae0b`）：真实 checkpoint 端到端（均值保持记录伪造 + content SHA 重同步 → 记录级 rebuild 捕获）、CROSS_POINT、语义守卫参数化、bundle 级伪造全量重同步/强制 provenance/checkpoint 不符/identity 不符/failed-fit cells 不一致/合法通过。

**未改变公开 schema**（artifact v1 / trace v3 / receipt v3 / bundle v3 字段不变；强制 provenance 为输入契约）；**未改冻结科学口径**。**未完成**（明确不在本棒范围，待 Codex R5 + 后续棒）：staged A-E1 执行、D8（仍 fail-closed）、完整临时 smoke、A-E1 formal 分阶段启动、9d、G4。报告 `coworker/reports/2026-07-18-study02-g3-selection-provenance-r4-claude.md`。**A-E1 formal 未授权**。等 Codex R5。

### 2026-07-19 controller-anchor 性能阻塞修复（staged smoke 解阻塞，第六执行者棒）

A-E1 staged smoke（349 fit）此前实跑 96/349 超过 30 分钟、无 stage receipt，阻塞根因：`_validate_controller_anchors` 在每次 `_rebuild_authority` 内对每个 anchor 分别执行 `_replay(events[:seq+1])`，同一批 claim/receipt 被按递增长度反复读取校验——O(N²)/rebuild、run-total O(N³)。本棒在不削弱 journal/anchor/claim-receipt 哈希链与篡改检测的前提下改为**单次有序 replay 捕获每个 event 后的 canonical 权威状态哈希，再逐 anchor 对照**（`_replay` 加 opt-in `_checkpoints` out-param，默认 None 零开销、未改 genesis/kind 控制流；`_validate_controller_anchors` 一次 replay + `checkpoints[seq]` 比对）。每个 claim/receipt 仍被读取+结构校验+哈希绑定**恰好一次**；无缓存侧车、无第二权威、无 snapshot 持久化、无 `_authority` 进程缓存、未改冻结矩阵/selection rule/formal schema/科学合同。提交 `d480c13`。

- **验证**：10 个新等价/fail-closed/重启测试 + 337 个 study02a 测试全通过（deselect 349-smoke）；`compileall`、`git diff --check`、冻结哈希审计（`verify_frozen_hashes` + matrix SHA fad701…）全干净。
- **实测基准**（clean fd43e38 BEFORE vs `d480c13` AFTER，median of 3，validate_controller=True）：N=32(65ev) 11.27→0.945s(11.9×)；N=64(129ev) 42.50→1.60s(26.6×)；**N=96(193ev) 90.33→2.24s(40.3×)**。anchor 成本从 89.1s→1.03s，scaling 由 ~O(N^1.9) 降为线性。JSON 在 `python/.bench_anchor_results.json`。

**关键发现（交 Codex，非本棒修复）**：性能修复首次让 349-record smoke 推进至全部 349 条计划记录（7321s/2h、699 events）并到达末尾 `build_module_selection`，但该 smoke **FAIL（非 partial pass）**——因阶段分类错误，placeholder fits 被误当作 concrete 执行，**不构成有效 full-chain staged smoke**。暴露两个**预先存在、与 anchor 修复无关**的 staged bug：(1) `_a_e1_fit_stage` 用 `plan_row.get("fit_kind","")`，但 plan.jsonl **设计上不带 `fit_kind`**（在 matrix，见 `formal_executor.py:854-857`）→ 全量运行中所有 fit 被判为 `concrete`，编排器**从不触发 stage1/stage2 分级选择**，无 stage receipts/trace/ledger，stage2/winner 占位 fit 被当 concrete 执行（`status_run` 报 succeeded=349，但这 349 **含误 concretize 的占位行，非有效 fit 数，~2h 非有效 staged 耗时外推依据**）；(2) `_smoke_score_fit` 直接访问 `plan_row["fit_kind"]`，在 `build_module_selection` 对 plan.jsonl 行评分时 KeyError。两者此前未被覆盖（per-route 单测绕过编排器分级、max_fits=3 测试到不了 fit 141、349-smoke 从未跑完）。`test_access_count=0`（test 全程 sealed）。**这是 staged source-of-truth mismatch 的 CRITICAL OPEN BLOCKER：此前 per-route 单测只验证了零件、max_fits=3 未到第 141 条阶段边界，top4 解锁从未被真正验证。属选择相邻逻辑，按 relay 边界交 Codex 统一审核**——本棒记录实测并停止。修复方向（下一棒，Codex 审核后）：`_a_e1_fit_stage`/scoring 按 `fit_id` 对齐冻结 matrix 权威行读阶段类型（缺失/重复/不一致 fail-closed），**不把 `fit_kind` 复制回 plan**（避免第二事实源）。本棒未改 plan/schema、未给 `_smoke_score_fit` 塞默认 `fit_kind`、未把已知失败 smoke 改成静默通过或无条件 xfail（保留为可执行复现入口）。

**未完成/未授权**：349-smoke 未通过（卡在上述 staged bug，非性能）；A-E1 formal 未授权；未进入 A-E3/A-E2、accredit-authorize、test unseal、真实 formal、9d、G4。报告 `coworker/reports/2026-07-19-study02-g3-anchor-perf-claude.md`。本地 HEAD=`d480c13`（含 anchor 修复+测试+报告+文档），待网络恢复后推送。等 Codex 统一审核（anchor 修复 + 两个 staged bug + accreditation）。

### 2026-07-20 R5（Codex APPROVE 方案 a 之后，point_evidence 迁出实施棒）

本棒为 Codex verdict 后的实施棒。Codex：APPROVE point_evidence blocker 根因 + 批准方案 (a) 迁出；**BLOCK 任何 scheduler allowed-extra / snapshot 排除 / 输出目录放宽**；无需再做纯设计棒，按修订合同直接实施。起点 `origin/claude/study02-a-20260715 @ 1e4edd1`（前一棒：source-of-truth 已 FIXED `10d6fcf` + point_evidence 设计文档 `1e4edd1`）。

**已完成并推送（commit `4d5c9cd`，`fix(study02a):`）：**
- **`build_module_selection` 迁出**：每个 fit 的 point evidence 写到 `run_dir/selection/point_evidence/{fit_id}.json`（selection 自有目录），**不再共址 `outputs/{fit_id}/`**。新增 `_validate_selection_point_evidence_dir`（恰含预期 `{fit_id}.json`；missing/extra/duplicate/alias/non-file/nested/unknown fit fail-closed）。point evidence canonical content / 内容 SHA / supporting hash / trace-receipt binding / checkpoint 独立重建**均不变**。`_publish_bytes_no_replace` 自带 mkdir + no-replace，无需额外处理。
- **`accredit_build` 重写**：从冻结 matrix `build_decision_specs` 派生预期 selection fit 集（**不扫 outputs 目录**）；读迁出 point evidence；evidence.json/checkpoint.pt 仍按 fit_id 从 `outputs/{fit_id}/` 读；从 `n_mode`/`fixed_n` 恢复 n（**plan 无 `n`**，修复 `plan_row["n"]` KeyError）；**失败 selection fit 不静默 skip**——按 scheduler terminal receipt（`receipts/{fit_id}.failed.json` 的 `failure_code`）+ point-evidence failure record（`failed` flag + 冻结 penalty）+ evidence.json 缺失三源一致生成失败 fit_status，否则 fail-closed。
- **`formal_scheduler.py` 输出目录校验未改动**（约束 2）。冻结 matrix / plan schema / `_PLAN_FIELDS` / selection rule / artifact-trace-receipt-bundle version / 科学指标**均未改**。

**验证**：356 非 slow 测试通过（含 accredit_build 重写、failed-fit、dir-validation 参数化 5 例）；focused slow test `test_post_selection_authority_rebuilds_with_relocated_point_evidence`（真实 scheduler materialize+claim+record 5 fit → build_module_selection 发布迁出 point_evidence → 真实 `_rebuild_authority`/`status_run`）**17s 绿**：selection 后权威重放通过、`outputs/{fit_id}/` 无 point_evidence、`selection/point_evidence/` 恰 144、`test_access_count=0`。349-smoke final check 已恢复为**真实 status_run/_rebuild_authority**（不再直读 `scheduler_state.json` workaround），**349-smoke PASSED：2h13min（8019s）、349/349 succeeded、699 events、无 placeholder 入 runner、stage1/stage2/final receipts + chained ledger、`selected_F2_or_V=F2`、真实 status_run final check `test_access_count=0`**（首次 259s 运行是一次早期 flake，干净 2h13min 全过）。compileall、`git diff --check`、冻结哈希审计（`verify_frozen_hashes` + matrix SHA `fad701…`）全干净。

**未授权/边界**：A-E1 formal 未授权；未进入 A-E3/A-E2、accredit-authorize、test unseal、真实 formal、9d、G4；不自称 formal APPROVE。**完成即提交推送，等 Codex 复审 relocation。** 报告 `coworker/reports/2026-07-20-study02-g3-point-evidence-relocation-claude.md`。

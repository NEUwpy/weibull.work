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
- **codex 断点**：lease 文件 `.slim/deepwork/study02-a.lease.json` 记录当前任务 `task-9c2-report.md`，heartbeat 停在 2026-07-13。该 30 分钟 heartbeat loop 已随 codex 额度失效。

## 4. 接力计划（顺序执行，每步有成果即提交+推送）

1. **Task 9c.2 收尾审查 ✅ 已完成（Claude 接力）**：对 `formal_scheduler.py`（commit 6fe8117 状态）做了独立 oracle 复审，核对 review2 的 6 项要求与 8 项攻击全部闭合（见 `.superpowers/sdd/task-9c2-review3.md`，本地未跟踪）；focused 套件 GREEN（`109 passed in 45.48s`）。给出 APPROVE，授权 A-E1 formal training/validation。审查中发现并修复 Windows CRLF 环境阻断（见第 8 节），无需为此提交代码。
2. **Task 9c：跑 formal training/validation**。按 **A-E1 → A-E3 → A-E2** 顺序，经 formal_scheduler 调度，跑满 **820 fits**（上限 900），test **全程 sealed**。确定性、可断点续跑、append-only ledger。这是重计算（可能数小时～数天）。提交 fit 产物/ledger。
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
- 进度文档引用的"总执行合同"`coworker/plans/2026-07-12-study02-a-full-execution.md` **磁盘上不存在**（从未落盘或已删）。以 SDD brief + 实验协议/计划为实际权威。
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

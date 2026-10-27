# Task Plan — Study02 G3 staged A-E1 production orchestration R1

Goal:

在不启动正式训练的前提下，完成真实冻结 A-E1 矩阵所需的 staged production orchestration：stage1 architecture ranking 产生 top4，stage2 解析 top4 并选择 architecture/optimizer，winner-retrain 产生 F2/V route 证据，最终派生 baseline route 与 `selected:A-E1_*` aliases。通过一次完整 temporary synthetic smoke 证明所有真实 A-E1 placeholders 可解析且证据链可重建，为后续 A-E3/A-E2 concrete D8 接线提供唯一 predecessor authority。

Known facts:

- Controller baseline：`db54398acd9b3d7e1553479aa58aa8a23f7613a8`；工作树另有 R1 未提交的 `formal_executor.py`、对应测试和 executor report，审查见 `coworker/reviews/2026-07-18-study02-g3-d8-r1-codex.md`。
- R1 通用 trace/receipt/ledger validator、pre-unseal provenance wrapper 与部分 predecessor checks 可以复用，但尚未获批提交。
- 冻结 A-E1 决策：每 route 的 stage1 architecture（n=10）-> top4；每 route 的 stage2 top4×optimizer；winner retrain 使用 formal seeds/core n；F2-vs-V baseline 使用已冻结 `global_better_rule`。stage2 loss 固定为矩阵中的 `transformed_train_z_huber`。
- test sealed；A-E1 formal 未授权；`.claude/settings.local.json` 是用户修改，必须排除。

Boundaries:

- Allowed:
  - 修改 Study02 formal executor/runner/scheduler/contracts/selection/CLI 及直接相关测试。
  - 为 staged resolution 增加最小、版本化、append-only 的内部证据/ledger 合同；最终公开 selection trace/receipt/bundle schema 不变。
  - 在 pytest `tmp_path` 中用 deterministic synthetic scoring/checkpoints 贯通真实冻结 A-E1 matrix；不得训练完整模型。
  - 修正或重构 R1 未提交代码，使其服务于真实 production call path。
- Not allowed:
  - 不启动 staged A-E1 真实 fit、formal、9d、G4；不读取或物化 test。
  - 不改冻结矩阵、配置、fit cap、科学指标、选择规则、failure penalty 或 bootstrap。
  - 不发明与矩阵/已批准 decision grouping 冲突的 alias；无法唯一推导时停止报告。
  - 不修改/提交 `.claude/settings.local.json`、凭证、Study01 或无关文件。
  - 不提交、不推送、不 self-approve；Codex APPROVE 后负责精确暂存、提交、推送。

Required behavior:

- production orchestration 必须从 run authority/冻结矩阵计算 pending stage，不允许调用者直接传 winner/top4/baseline。
- stage1 只消费具体 architecture fits；生成不可变、hash-bound、append-only resolution evidence 后才能 claim stage2。
- stage2 的 `selected_top_N` 必须解析为相应 route stage1 的第 N 名 architecture；stage2 winner 必须确定性解出 architecture 与 optimizer，loss 使用冻结矩阵固定值。
- winner-retrain rows 的 `selected:A-E1_loss/architecture/optimizer` 必须由 route-specific stage2 authority解析；不得使用字符串猜测或 sidecar 标量。
- F2-vs-V baseline 必须从两个 route winner-retrain 的完整冻结 support 用 `global_better_rule` 派生，得到唯一 `selected:F2_or_V`；最终 A-E1 aliases 取 winning route 的 stage2 loss/architecture/optimizer。
- 阶段证据必须绑定 module/run/code/effective-config、输入 trace/fit evidence、解析 mapping 和输出 hash；崩溃恢复不得覆盖旧证据或重复消费。
- 所有真实 A-E1 placeholders 在 temporary smoke 中可解析；缺 fit、失败 fit、篡改 hash、错 route/n/seed、重复 stage receipt、陈旧 mapping 和恢复重跑均 fail-closed。
- run_module/runner/CLI 至少有一个真实生产调用点；不能只新增未调用 helper。
- `test_access_count=0` 且 test state 不变。

Stop conditions:

- 权威文档与冻结矩阵无法唯一确定 alias 或派生 baseline 语义。
- 实现必须改变公开最终 artifact schema 或冻结科学口径。
- 出现活动写入者/正式实验、用户文件冲突或不可恢复环境问题。

Verification:

- 新增真实冻结 A-E1 matrix temporary staged smoke：concrete stage1 -> immutable top4 -> stage2 -> winner retrain -> F2/V baseline -> final aliases，断言所有真实 placeholders 被解析且输出顺序/哈希确定。
- 覆盖上述失败/恢复路径；不得以仅 synthetic exact decision-id fixture 代替真实矩阵测试。
- 运行直接相关 executor/scheduler/selection/runner/contracts/CLI/evidence 测试；materialize guard 必须在隔离 clean snapshot 或等价 clean-code 条件下验证。
- `compileall`、`git diff --check`、frozen hash 与 test-access audit。

Report:

- 写入 `coworker/reports/2026-07-18-study02-g3-staged-ae1-r1-claude.md`。
- 列出 changed files、真实 staged 数据流、全部命令/结果、失败与恢复测试、跳过项、偏离、阻塞及 `git status --short`。
- 完成后停止，等待 `coworker/reviews/2026-07-18-study02-g3-staged-ae1-r1-codex.md`。

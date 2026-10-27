# Study02 准备工作收口计划

## Goal

在不启动 formal、不启封或消费 test 的前提下，修复 R11 后剩余的生产与证据缺口，使当前 `main` 达到“可申请一个全新 A-E1 formal 授权”的状态。

## Known facts

- 起点为 `main == origin/main == e3cb002cfa0f90407ce6320b2ba4540926287629`，起点工作树干净，无活动 Study02 lease/process。
- 两个旧 A-E1 run 永久 blocked/aborted，不得续接或拼接为正式证据。
- 冻结协议/搜索配置为 `A-G2-v1` / `A-G2-search-v1`；G3 矩阵为 820 fits，test 仍 sealed。
- R11 staged ledger reader 缺少其文档所声称的语义顺序、唯一性、前驱与最终别名 cross-binding 校验。
- 统一 G3 sealed builder 只有库函数，无生产 CLI；旧单模块 authorize 和旧 consumer 暴露与统一三模块状态机冲突。
- 当前建议的未来仓库外运行根为 `C:\weibull-runs\study02`；本任务不创建 run。启动前必须重新检查容量。

## Boundaries

Allowed:

- 修复 staged ledger 语义校验并增加直接 happy/tamper 测试；
- 为 A-E1/A-E3/A-E2 提供可重建、可语义验证的 accreditation diagnostics；
- 增加 unified sealed-only `formal-g3-accredit-build` 生产入口；
- 永久阻断旧 per-module authorize，移除 runner 对旧 consumer 的 API 暴露；
- 做 `02-A-实验协议.md` §9 唯一一处适用阶段编辑性勘误；
- 更新当前状态、计划、报告、review、README 与更新日志；
- 在本地 `main` 建 checkpoint commit，以便 clean-tree production-bound 测试运行；最终直接推送 `origin/main`。

Not allowed:

- 启动/恢复 A-E1、A-E3、A-E2 formal；
- 生成、发布或伪造 approval；
- authorize、unseal、生成/读取/消费 formal test；
- 修改冻结 JSON、矩阵、参数范围、指标或选择规则；
- 复用旧 aborted run；
- 使用 worktree、分支或 PR。

## Required implementation

1. A-E1 staged ledger 必须严格接受且只接受：

   `stage1:F2 -> stage2:F2 -> winner_retrain:F2 -> stage1:V -> stage2:V -> winner_retrain:V -> baseline_input:none -> final_aliases:none`。

   同时校验 hash chain、阶段/route 唯一性、`stage1_record_sha256`、`stage2_record_sha256`、`baseline_record_sha256`，以及 top4、stage2、winner retrain、baseline、final aliases 的语义一致性。

2. 为 A-E3 两条路线的 `selected_top_N -> concrete architecture` 和 A-E2 size/distribution resolution 增加直接成功/篡改测试；修复被同名覆盖的测试。
3. runner 不得暴露旧 `consume_g3_test`；旧 `formal-accredit-authorize` 必须 fatal/不可达；`formal-consume-test` 继续 fatal。
4. diagnostics 支持三模块。统一 builder 必须重放三模块 authority、重建/语义验证 diagnostics、解析 415 cohort、只落盘 sealed manifest/bundle/state。
5. unified build CLI 只接路径和 run 定位参数。`code_commit` 只能从三 run replay authority 唯一派生，三 run 必须一致，当前 clean HEAD/scoped code 必须匹配，调用者不可注入。

## Phases

1. 实现上述代码与聚焦测试；执行者报告 diff、测试、跳过项和偏离。
2. Codex 独立 implementation review；修订至 `APPROVE`。
3. 本地 `main` checkpoint commit，运行 clean-tree production-bound 与完整相关 non-slow 验证。
4. 写 consolidated R9-R11/closeout report、launch contract、最终 review，并同步权威文档。
5. docs checkpoint commit，完整 clean-tree 验证，独立 closeout `APPROVE`。
6. 确认远端无不兼容前进，推送 `main`，核验远端 SHA 与干净工作区；到此停止，不启动实验。

## Stop conditions

- 出现活动 lease/process 或其他写入者；
- 实现需要改变冻结科学合同；
- 需要任何实际 approval/formal/test 权限；
- 远端 `main` 不再可安全快进推送；
- 独立 reviewer 给出 `BLOCK`。

## Verification

- 聚焦 G3/CLI/diagnostics/攻击测试；
- 全部 Study02 non-slow tests；
- clean-tree production-bound tests；
- `compileall`、`validate-config`、冻结 hash、`git diff --check`；
- CLI/API 不可达性检查；
- state 保持 sealed、`test_access_count == 0`；
- 无 formal artifacts/run/lease/process 被创建；
- 最终 `main == origin/main` 且工作区干净。

## Reports

- 实施报告：`coworker/reports/2026-07-26-study02-preparation-closeout-implementation.md`
- 最终审查：`coworker/reviews/2026-07-26-study02-preparation-closeout-codex.md`

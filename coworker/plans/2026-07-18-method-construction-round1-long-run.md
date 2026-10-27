# 第一轮六方法第一层长任务计划

## Goal

在独立分支上依次完成 MLE、WMLE、MDM、LSE、MM、LRE 的第一层建设。每个方法独立验真、实现、测试、报告和提交；六个方法全部处理后一次性交给 Codex 审核。

本计划覆盖此前“每个方法等待 Codex 放行后再继续”的节奏，但不降低方法级证据标准。

## Baseline and papers

- 基线：`f13f4d4`；Phase 0 Stage A/B/C 已 APPROVE；`05-状态.md` 是唯一状态源，目前只有 MDM 可公开选择。
- MLE：主锚 `182-105`，非正则边界 `182-090`，`182-101` 仅交叉核对。
- WMLE：`182-088`。
- MDM：`182-046`。
- LSE：主锚 `182-104`，`182-096` 仅比较核对。
- MM：主锚 `182-102`，`182-096` 仅比较核对。
- LRE：主锚 `182-107`，位置参数边界 `182-106`。本轮不实现或声称 Park (2017) 的样本相关系数方法。
- MLE、WMLE、MDM、LRE 是现有实现重新验真；LSE、MM 是运行时占位，需要完整建设。

## Execution contract

1. 从 `README.md` 开始，读取 `02-规则.md`、`05-状态.md`、总路线图、Stage C 报告与 R2 审核，再读取当前方法的论文和实现。
2. 在 `opencode/method-construction-round1` 分支工作。若分支已存在，读取进度账本和提交历史后续跑；不得重置、清理或覆盖用户工作。首次启动时把本计划、handoff 和初始进度账本纳入一个启动提交。
3. 顺序固定：MLE → WMLE → MDM → LSE → MM → LRE。每个方法完成证据核对、代码、独立测试、理论、流程和计算器调用合同后，写独立报告并创建一个范围清晰的提交，然后自动进入下一方法。
4. 每个方法开始和结束时更新 `coworker/reports/2026-07-18-method-construction-round1-progress.md`。会话中断后，以该文件和 `git log f13f4d4..HEAD` 为恢复依据。
5. 不因完成计划、分析或单个方法而停止。只有六个方法均处理完、最终验证和总报告完成，或出现全局硬阻塞时才结束。

## Per-method gate

每个方法必须同时具备：

- 论文公式、参数化、适用样本和边界条件到真实代码位置的映射；
- 独立后端执行分支，不是别名、占位或其他方法回退；
- 独立测试，包含可信外部/手算/论文基准、合法参数、失败路径和方法身份；“能返回数字”不算充分；
- 共享计算器 API 可正确调用该方法，但不绕过状态门控公开；
- 与真实实现一致的理论页和程序流程；
- 方法失败时无伪结果、无身份替换、无静默回退。

现有实现与论文一致时保留；只有证据证明不一致时才修复。不得为了通过测试降低判据或让测试复述被测实现。

## Boundaries

### Allowed

- 六个目标方法的后端、注册、独立测试、共享 API 合同、理论页和流程证据。
- 为保持方法身份和公共合同所需的最小共享代码改动。
- 方法级报告、进度账本和提交。

### Not allowed

- 不处理其余 16 个方法，包括 MMLE；不进入第二层或第三层。
- 不编辑 `05-状态.md`，不手工编辑生成缓存，不提前开放任何新方法。最终报告只提交状态变更建议，由 Codex 审核后更新。
- 不改变计算器四栏视觉及双向参数工作流：默认 3P=2/1000/1000；参数生成样本；仅点击估计才拟合；2P 强制 `gamma=0`；失败保留原参数、样本和图像。
- 不伪造 2P/3P、论文样例或收敛结果；不增加回退。
- 不修改 `Study/`、`_archive/`、更新日志、部署和无关依赖。
- 不在 `main` 直接施工，不推送、不合并。

## Block handling

- 方法局部阻塞：穷尽本地论文和现有实现后，在该方法报告中写 `BLOCKED`、精确缺口和已完成工作；不要发明公式。提交安全的证据/测试/报告后继续下一个独立方法。
- 全局阻塞：基线或工作树不安全、共享合同冲突导致后续方法均无法继续、必需依赖/测试环境整体不可用。此时更新进度账本和总报告后停止。
- 普通实现困难、测试失败或需要迭代不算阻塞；继续诊断修复。

## Verification

每个方法提交前运行其聚焦测试、API 身份测试、计算器状态测试、方法状态缓存检查和 `git diff --check`。修改共享代码时追加完整 Python 测试与 TypeScript 检查。

最终至少运行：

```powershell
python -m pytest python/tests -q
npm run test:calculator-state
npm run test:method-status
npm run check:method-status
npx tsc --noEmit
npm run build
git diff --check f13f4d4..HEAD
```

## Reports and completion

每个方法写入：

- `coworker/reports/2026-07-18-method-construction-round1-mle-opencode.md`
- `coworker/reports/2026-07-18-method-construction-round1-wmle-opencode.md`
- `coworker/reports/2026-07-18-method-construction-round1-mdm-opencode.md`
- `coworker/reports/2026-07-18-method-construction-round1-lse-opencode.md`
- `coworker/reports/2026-07-18-method-construction-round1-mm-opencode.md`
- `coworker/reports/2026-07-18-method-construction-round1-lre-opencode.md`

每份报告包含改动文件、论文映射、测试精确结果、跳过项、偏离、阻塞和第一层状态建议。

最终写 `coworker/reports/2026-07-18-method-construction-round1-final-opencode.md`，汇总方法结论、提交列表、完整验证、未解决项及建议的 `05-状态.md` 变更。把最终报告和最后一次进度更新作为收口提交；结束时保持分支工作区干净，停止并等待 Codex 对 `f13f4d4..HEAD` 一次性审核。

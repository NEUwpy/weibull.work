# Coworker Live Loop 设计

> 日期：2026-07-18
> 状态：待用户书面复核
> 首个目标仓库：`C:\Web\Weibull`
> 首个目标分支：`claude/study02-a-20260715`

## 1. 目标

在现有 `coworker` 协议上增加一个可恢复的自动执行闭环：Codex 保持唯一规划者和审批者，通过本机 Claude Code CLI 驱动 Claude 作为执行者；Claude 完成实现和验证后，Codex 审查真实代码、提交与证据，并将 `REVISE` 自动投递回同一个 Claude session，直到 `APPROVE`、`BLOCK` 或触发明确的人类门禁。

用户只需要提供顶层目标、必要的高风险授权和无法由项目事实解决的产品决策，不再承担 handoff、review 和修订意见之间的人工复制。

## 2. 非目标

- 不共享或伪造两个模型的隐藏推理；共享的是任务合同、文件、提交、命令结果、报告和审查结论。
- 不让 Claude 自签 `APPROVE`，也不让执行者修改审查标准。
- 不自动合并 `main`、force-push、reset、clean 或删除工作树内容。
- 不在第一版建设常驻网络服务、远程队列或通用多供应商 agent 平台。
- 不以自动化为由绕过 sealed test、昂贵 formal run、凭证访问或其他项目门禁。

## 3. 现有基础与首轮接管状态

项目已经具备稳定的协作证据结构：

- `coworker/plans/`：Codex 批准的执行合同。
- `coworker/handoffs/`：执行者入口。
- `coworker/reports/`：Claude 的变更与验证证据。
- `coworker/reviews/`：Codex 的 `APPROVE / REVISE / BLOCK`。
- `.agents/skills/coworker/`：跨 agent 的角色与报告协议。

截至设计时，首轮接管必须基于以下已核实状态：

- 当前分支为 `claude/study02-a-20260715`。
- 本地与远端均已到 R4 收尾提交 `3032eb5`；本棒还包含 `99f07b3` 和 `dd8ae0b`。
- `.claude/settings.local.json` 存在用户本地修改，必须保留且不得混入提交。
- R4 report 已写入并要求 Codex R5 审查；staged A-E1、D8、formal、9d 和 G4 不得被视为已授权。

因此首次 live-loop 运行是 **review-first**：Codex 先执行 R5、审查当前 R4 增量，再决定 `APPROVE`、`REVISE` 或 `BLOCK`；在该审查完成前不得自动派发下一阶段实现。

## 4. 总体架构

系统包含五个边界清晰的部件。

### 4.1 Codex Controller

运行在用户当前 Codex 任务中，负责：

- 读取仓库权威入口、当前状态、计划、报告、Git 增量和验证证据。
- 生成或确认本轮 plan/handoff。
- 启动、监控和恢复 Claude worker。
- 独立执行最终审查并写入 `coworker/reviews/`。
- 决定继续修订、进入下一阶段、暂停或请求用户决策。

Controller 不把审查职责委托给 Claude，也不依据 Claude 自述直接批准。

### 4.2 Local Runner

位于 `.agents/skills/coworker/scripts/`，提供面向 Codex 的稳定命令接口：

- `start`：启动新的 Claude headless session。
- `resume`：向既有 Claude session 投递 Codex review。
- `status`：读取 PID、心跳、退出状态和最近输出，不阻塞 Codex。
- `collect`：验证并收集 Claude JSON 结果、session ID、report 路径和命令结果。
- `cancel`：只终止由当前 runtime 记录明确标识的 worker；不做广域进程清理。

Runner 使用本机可执行的 `claude` 路径，优先通过 `Get-Command claude` 解析，不硬编码用户目录。长任务以隐藏子进程运行，stdout/stderr 重定向到本地 runtime；Codex 通过短轮询保持可见进度。

### 4.3 Claude Worker

Claude 通过 `claude -p --output-format json` 启动，并在后续修订中使用相同 `session_id` 恢复。Worker 获得：

- 角色：executor。
- plan、handoff、report、当前 review 的路径。
- 当前分支、允许范围、禁止范围、停止条件和验证要求。
- 明确指令：不得调用其他 reviewer、不得自批、不得越过人类或 Codex 门禁。

Claude 负责实现路径选择、文件编辑、验证、报告和项目合同允许的精确提交/推送。

### 4.4 Coworker Evidence Plane

跨 agent 的长期事实继续落在现有 `coworker/` 文件和 Git 历史中。提示词只传递角色与路径，避免每轮复制整份上下文。

Codex 审查输入至少包括：

- 批准的 plan/handoff。
- 审查基线与目标提交。
- `git diff` 和变更文件列表。
- Claude report 中列出的命令及其精确结果。
- Codex 自己复跑或抽查的验证结果。
- 上一轮 review 及逐项闭合情况。

### 4.5 Runtime State Plane

易失运行状态保存在被 Git 忽略的 `coworker/runtime/`：

```json
{
  "schema_version": 1,
  "task_id": "study02-g3-r4",
  "repo": "C:/Web/Weibull",
  "branch": "claude/study02-a-20260715",
  "baseline_sha": "<40-hex-sha>",
  "claude_session_id": "<uuid>",
  "worker_pid": 12345,
  "round": 2,
  "state": "AWAITING_CODEX_REVIEW",
  "plan": "coworker/plans/<task>.md",
  "handoff": "coworker/handoffs/<task>-claude.md",
  "report": "coworker/reports/<task>-claude.md",
  "review": "coworker/reviews/<task>-codex.md",
  "started_at": "<ISO-8601>",
  "heartbeat_at": "<ISO-8601>",
  "last_exit_code": 0
}
```

runtime 不保存认证信息，不进入提交；需要长期保留的结论必须写入 report/review/status 或 Git 历史。

## 5. 状态机

```text
IDLE
  -> PREFLIGHT
  -> REVIEW_FIRST | PLAN_READY
  -> WORKER_STARTING
  -> WORKER_RUNNING
  -> RESULT_COLLECTING
  -> AWAITING_CODEX_REVIEW
       -> APPROVED
       -> REVISION_READY -> WORKER_RUNNING
       -> REPLAN_READY -> PLAN_READY
       -> PAUSED
       -> BLOCKED
       -> HUMAN_GATE
```

关键规则：

- 每次转换都原子写入 runtime，崩溃后从最后一个稳定状态恢复。
- 同一仓库同一工作树同时只允许一个 live-loop controller；使用锁文件和 PID 生存检查防止重复派发。
- `APPROVED` 只表示当前 plan/gate 获批，不自动等同于整个研究阶段完成。
- Controller 只有在顶层目标仍覆盖下一阶段且不存在新的人类门禁时，才能自动创建下一 gate。

## 6. 正常数据流

### 6.1 初次派发

1. Controller 执行 preflight：仓库路径、分支、HEAD、upstream、dirty files、Git 配置、Claude CLI 可用性和现有 runtime。
2. 记录用户已有修改的路径与哈希；这些路径默认不在 worker 提交范围。
3. 若已有待审查提交或 report，进入 `REVIEW_FIRST`。
4. 否则确认 plan/handoff 后调用 Runner `start`。
5. Runner 通过 stdin 传入提示，避免 PowerShell 引号和长命令行问题，并捕获 Claude JSON 输出。

### 6.2 执行与收集

1. Claude 读取权威入口及引用文件，实施计划内工作。
2. Claude 运行要求的检查，写 report，并按项目合同进行精确提交；禁止 `git add -A`、`git commit -am` 和隐式包含用户改动。
3. Runner 保存 session ID、退出码、stdout/stderr 和心跳。
4. Controller 验证 report 存在、JSON 可解析、声明提交可定位、工作树没有意外污染，然后进入审查。

### 6.3 审查与修订

1. Codex 独立审查真实 diff、失败路径、测试范围、证据链和文档同步。
2. Codex 写入结构化 verdict：
   - `APPROVE`：当前 gate 完成。
   - `REVISE`：列出有优先级、文件定位和验证要求的具体发现。
   - `BLOCK`：说明违反的硬边界或必须重新规划的原因。
3. `REVISE` 时，Runner 用相同 session ID 调用 `resume`，只传 review 路径、尚未闭合项和新的边界事实。
4. Claude 写增量修复和修订报告；Codex再次审查。

默认每个 gate 最多四轮 review。达到四轮时，Codex必须选择：

- 若仍可在原目标内明确重规划，则自动生成替代 plan 并开始新的 gate；
- 若存在真实需求冲突、风险授权或无法裁决的技术分歧，则进入 `HUMAN_GATE`；
- 不得仅因“轮数已满”草率批准。

## 7. 权限与门禁

### 7.1 Claude 可自主执行

- 计划边界内的实现选择和局部重构。
- 计划要求的测试、静态检查和临时验证。
- report/status 更新。
- 已在 plan 明确授权的分支提交和推送。

### 7.2 仅 Codex 可决定

- plan 是否满足用户目标。
- review finding 是否闭合。
- 当前 gate 的 `APPROVE / REVISE / BLOCK`。
- 是否在原顶层目标内进入下一普通阶段。

### 7.3 必须暂停找用户

- 目标、研究口径或产品需求存在会改变设计的歧义。
- 删除、覆盖、重写历史、force-push、合并主分支等难恢复操作。
- 初始授权未覆盖的 sealed test 解封、长时间/高成本 formal run 或外部资源消耗。
- 需要新凭证、扩大文件/仓库范围或对外发布。
- Codex 与 Claude 在事实核验后仍无法收敛，且选择会改变范围或科学结论。

用户可以在最初目标中预授权特定门禁；Controller 将授权原文和适用范围写入 plan，避免重复询问。

## 8. Git 与工作树安全

- 启动前保存 HEAD、upstream、`git status --short`、tracked diff 和 untracked 清单的指纹。
- 不使用 reset、clean、checkout 丢弃、全量 add 或 force-push。
- Claude 只能精确暂存计划内路径；用户已有 dirty file 默认排除。
- 检测到外部进程在 worker 运行期间修改同一文件时，暂停并报告冲突，不自动覆盖。
- worker 每轮使用增量提交保留审计链；修订通过新提交闭合，不改写历史。
- Study02 第一版继续使用 `claude/study02-a-20260715`，不触碰 `codex/long-task-20260711` 基线。

## 9. 故障与恢复

| 故障 | 自动行为 |
|---|---|
| Claude 返回非零或无效 JSON | 保留 stdout/stderr，标记 `PAUSED`；若 session ID 已获得则优先恢复一次 |
| Claude 限额或临时 API 错误 | 指数退避并保留 session；超过可配置时间窗口后暂停，不丢任务状态 |
| Codex 限额中断 | 保持 `AWAITING_CODEX_REVIEW`；Claude 不得继续下一阶段 |
| 电脑或 Codex 重启 | 校验 PID、分支、HEAD 和 runtime 后，从最后稳定状态恢复 |
| worker 无心跳 | 先检查进程与输出增长；确认僵死后只终止记录的 PID |
| report 缺失或验证声明不可复现 | 自动形成 `REVISE`，不接受口头完成声明 |
| 工作树出现范围外修改 | 暂停；区分用户修改、worker 污染和生成物后再处理 |
| session 无法恢复 | 基于 plan/report/review 创建新 worker session，并把旧 session 标为 superseded |

## 10. 可观测性

Codex 在不泄露敏感输出的前提下向用户报告：

- 当前 task/gate/round/state。
- Claude 正在执行的任务摘要。
- 最近心跳和耗时。
- 已完成的提交与验证数量。
- 当前等待的是 Claude、Codex review 还是人类门禁。

本地 runtime 日志按 task 分目录，并设置大小上限；长期证据只进入 `coworker/` 的正式文档。

## 11. 安全与凭证

- 不复制或记录 Claude、Codex 的 auth 文件、API key、token、缓存或完整用户配置。
- Runner 只继承启动 Claude 所需的当前用户环境，不把环境变量写入日志或 prompt。
- report/review 中禁止粘贴可能含密钥的完整环境或配置输出。
- 所有路径在执行前解析为绝对路径，并验证位于目标仓库或明确允许的 runtime 目录内。
- 角色提示中禁止递归派发：executor 不得启动 Codex/Claude 子循环；只有 Controller 能调用 Runner。

## 12. 第一版文件范围

计划中的实现文件限定为：

- 修改 `.agents/skills/coworker/SKILL.md`：增加 live-loop 触发、角色保护和渐进式引用。
- 新增 `.agents/skills/coworker/references/live-loop.md`：状态机与 Controller 行为。
- 新增 `.agents/skills/coworker/scripts/coworker-live.ps1`：`preflight/start/resume/status/collect/cancel`。
- 新增针对 Runner 的测试和 fake Claude fixture。
- 修改 `.gitignore`：忽略 `coworker/runtime/`。
- 更新 `.agents/skills/coworker/references/dispatch.md` 和 `coworker/README.md`：记录自动模式入口。

第一版不增加 Claude Stop hook。完成性由 Controller 对 report、提交和验证证据的检查强制执行；这避免 hook 自身再次启动 Codex、形成递归或让 Claude 会话无法退出。若实际测试证明 Claude 经常绕过报告门禁，再单独设计 hook 增强。

## 13. 验证策略

### 13.1 静态与单元验证

- PowerShell 语法和严格模式检查。
- 状态转换合法性、原子写入和 schema 兼容测试。
- 仓库路径、PID、锁文件和允许范围校验。
- Claude JSON 成功、失败、缺字段和损坏输出解析。
- review round、session resume 和 superseded session 逻辑。

### 13.2 集成验证

使用 fake Claude executable 模拟：

- 正常完成并返回 session ID。
- 首轮 `REVISE`、同 session 修订、次轮 `APPROVE`。
- 限额错误、崩溃、无心跳、超时和无法恢复。
- report 缺失、提交不存在、工作树出现范围外修改。
- 重复 Controller 竞争同一锁。

### 13.3 本机冒烟

1. 在临时 Git 仓库运行只读 Claude 探针，验证启动、JSON、session 恢复和日志。
2. 在临时 Git 仓库运行一个可回滚的小编辑任务，验证 report、精确暂存和 Codex review 循环。
3. 在 Weibull 运行 `review-first` dry-run，只生成 preflight 和拟议 review 输入，不启动新的 Study02 实现。
4. 用户确认 dry-run 后，才把当前 R4 的 Codex R5 审查作为首个真实 live-loop gate。

## 14. 验收标准

设计实现完成需满足：

- 用户给出一次顶层目标后，至少一次 `Claude implementation -> Codex REVISE -> same Claude session fix -> Codex APPROVE` 无需人工复制文本。
- Codex 能在 Claude 失败、Codex 中断或机器重启后从 runtime 和 Git 证据恢复。
- Claude 无法通过自述或自签绕过 Codex review。
- 用户已有 dirty files、auth/config 和非计划文件不被提交或覆盖。
- 每个 verdict 都能追溯到 plan、提交、report 和验证证据。
- 当前 Study02 首轮接管不会在 R5 批准 R4 增量前启动 staged A-E1、D8、formal、9d 或 G4。

## 15. 已知限制

- Claude worker 是由 CLI 创建和恢复的 headless session，不等同于用户手工打开的 Claude Code 交互窗口。
- Codex 与 Claude 共享可审计产物，不共享隐藏推理或当前 GUI 私有转录。
- 同一工作树仍不适合两个执行者并行编辑重叠文件；live-loop 锁只约束本系统，外部编辑依靠指纹检测。
- 自动化能显著减少 Codex 的实现消耗，但 Codex 每轮独立审查仍会使用额度。

# Coworker 工作区

## Live-loop runtime

`coworker/runtime/` is ignored local transport state for the Codex-controlled
Claude Code loop. It may contain a task state machine, Claude session ID,
recorded worker PID, heartbeat, stdout/stderr, and the most recent result. It is
not formal project evidence and must not contain credentials or environment
dumps. Keep durable plans, handoffs, worker reports, and Codex verdicts in the
tracked directories below.

本目录用于 Codex、Hermes、OpenCode、Claude Code 之间的任务流转：规划、分发、回收报告和验收。

它不是项目规则入口。项目唯一权威入口仍是根目录 `README.md`；通用多 agent 工作法由 `.agents/skills/coworker/SKILL.md` 定义，项目特定角色和边界写在 README。本目录只保存具体任务的可追溯材料。

## 目录约定

| 路径 | 用途 |
|------|------|
| `plans/` | Codex 写给人和 agent 的执行计划、边界、STOP 条件、验证命令。 |
| `handoffs/` | 实际发给 Hermes、OpenCode 或 Claude Code 的任务单。 |
| `reports/` | 执行 agent 回传的改动文件、验证结果、失败点和偏离说明。 |
| `reviews/` | Codex 或二审 agent 的 `APPROVE / REVISE / BLOCK` 验收记录。 |
| `templates/` | 可复用的分发、二审、最终验收模板。 |

## 命名约定

使用可排序的短文件名：

```text
YYYY-MM-DD-<short-slug>-<role>.md
```

示例：

```text
2026-06-25-metric-refactor-plan.md
2026-06-25-metric-refactor-hermes-handoff.md
2026-06-25-metric-refactor-opencode-review.md
2026-06-25-metric-refactor-codex-verdict.md
```

## 基本流转

1. Codex 先读 `README.md` 和任务相关当前文档，不从 `docs/history/` 或 `docs/oldrules/` 继承当前规则。
2. Codex 在 `plans/` 写执行计划，必要时在 `handoffs/` 写可直接投递的任务单。
3. 将任务单发给执行 agent，例如：

```powershell
$prompt = Get-Content -Raw .\coworker\handoffs\<task>-hermes-handoff.md
hermes --skills coworker -z $prompt
```

或：

```powershell
$prompt = Get-Content -Raw .\coworker\handoffs\<task>-opencode-handoff.md
opencode run $prompt
```

4. 将执行结果保存或摘要到 `reports/`。
5. Codex 根据 diff、验证命令和报告在 `reviews/` 写最终验收。

## 边界

- 不在这里存放凭证、token、私密配置或外部服务密钥。
- 不让多个执行 agent 在同一工作树同时编辑同一批文件。
- `handoffs/`、`reports/`、`reviews/` 是任务证据，不自动成为项目长期规则。
- 如果某个结论应成为长期规则，更新 `README.md` 或 README 指向的当前规则文档，而不是只留在本目录。

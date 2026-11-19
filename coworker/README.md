# Coworker 工作区

本目录保存分仓恢复说明及产品验收记录。

## 协作约定

- 编程、重构、修 bug、审查 diff 或在 Codex / Hermes / OpenCode / Claude Code 之间交接任务时，使用 `coworker` skill。
- 默认协作角色：Codex 负责需求对齐、规划审查和最终验收；Hermes / MiMo 或 Claude Code / MiMo 优先执行；OpenCode / DeepSeek 可作二审、备选执行或独立 bug-finding。
- 审查时以实际 diff、验证命令和项目规则为准，不以历史手稿覆盖当前代码事实。

[coworker 技能](../.agents/skills/coworker/SKILL.md)

## 工作记录

具体多 agent 任务的计划、分发、执行报告和验收记录放在 `coworker/`。

- `plans/`：当前分仓、基线及源库切换的恢复依据。
- `reports/`、`reviews/`：当前功能和方法建设的验收证据。

2026-11-01，过期科研流转记录、旧模板及完整运行态已移至`D:/weibull-backups/software-cleanup-20261101/retired/coworker`。当前11份材料保留对应链接；本机迁出副本和原Git历史可恢复旧记录。

后续只保留对当前产品有用的结论。临时任务传输、会话、进程信息、stdout等留在忽略的`runtime/`或项目外；不得放凭证和环境转储，不把完整执行日志重新加入软件Git。

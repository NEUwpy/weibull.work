Role: long-running executor
Plan: `coworker/plans/2026-07-18-method-construction-round1-long-run.md`
Progress: `coworker/reports/2026-07-18-method-construction-round1-progress.md`
Final report: `coworker/reports/2026-07-18-method-construction-round1-final-opencode.md`

从 `README.md` 开始，使用 `coworker` skill，执行计划中的六方法第一层长任务。

工作要求：

- 在 `opencode/method-construction-round1` 分支施工；不得直接改 `main`，不得推送或合并。
- 首次启动时先提交现有计划、handoff 和进度账本，作为可恢复基线。
- 按 MLE → WMLE → MDM → LSE → MM → LRE 顺序连续工作。
- 每个方法独立核论文、实现、测试、写报告并提交；提交后立即继续，不等待 Codex 中途审核。
- 持续更新进度账本。若这是续跑会话，先读进度账本和 `git log f13f4d4..HEAD`，从第一个未完成方法继续，不重做已提交工作。
- 不编辑 `05-状态.md` 或生成缓存，不提前开放方法；最终只给出状态变更建议。
- 方法局部阻塞时记录证据并继续下一方法；只有计划定义的全局阻塞或全部完成时才停止。
- 六个方法处理完后运行最终验证，把总报告和最终进度作为收口提交，确认工作区干净，然后停止等待 Codex 一次性审核。

不要只输出计划或建议。直接执行并持续推进到上述终点。

# Study/02 主研究 B 正式实验任务合同

Goal:

完成 Study/02 面向 \(x_{0.95}\) 的正式实验 B0–B6：实现并比较 NN 参数路线 P、NN 直接分位点路线 D 与传统路线 T，回答 B1–B7，形成可复现证据、`04-B-证据索引.md` 和 `05-B-正式实验报告.md`，直至 Codex 对精确 tip APPROVE。

Known facts:

- 权威入口：根 `README.md` 与 Study/02 `README.md`；
- 科学合同：Study/02 `01-B-研究问题.md`、`02-B-实验协议.md`；
- 进度续接点：Study/02 `03-B-执行计划与状态.md`；
- 前置参数基线：Study/02 `06-A-前置研究报告.md`；
- B 尚未启动，不得把 A 的 validation/confirmation/formal test 当作 B test；
- coworker 选定版本：2.4.0，项目与全局源码已解析为 identical，机械测试 12 passed。

Boundaries:

- Allowed：创建 B 所需最小代码、配置、测试、聚合工件和图表；运行预注册训练与评估；在外部 run root 保存大型产物；修复普通代码或数据错误；按阶段提交。
- Not allowed：改变主目标 \(x_{0.95}\)；扩展到删失/截断/多目标分位点；超过 12-fit 搜索或 100 个新增 NN fit；访问 A formal test；扩建 formal scheduler/authority/unseal/consume/capsule/攻击防护；上传数据；产品集成；合并 main；推送远端。

Executor autonomy:

- 选择符合现有项目模式的最小实现，优先复用 `code/study02a/` 与 `python/studies/common/metrics.py`；
- 阶段内自行调试、重跑失败的非正式 pilot、补充必要测试；不得用 validation/test 结果扩大搜索或改变判定；
- 发现不影响科学结论或基本复现的问题时记录为 recommendation，不升级为阻塞。

Stages:

- [x] B0 文档和边界冻结；
- [ ] B1 最小实现、测试与微型 pilot；
- [ ] B2 D 路线 12-fit 选择；
- [ ] B3 全量训练、checkpoint 清单与哈希冻结；
- [ ] B4 core test 与确认性比较；
- [ ] B5 压力层、真实数据和不确定性；
- [ ] B6 证据索引、正式报告、clean-checkout 复现与终审。

Stop conditions:

- 触发 `02-B-实验协议.md` 的硬停止条件；
- 发现工作树存在与本任务冲突且无法隔离的用户改动；
- 需要新的用户权限、外部私有数据或显著扩大研究范围。

Verification:

- 每阶段相关单元测试与微型端到端检查通过；
- 配置、checkpoint、摘要和行级产物有 SHA256/manifest；
- 统计分析严格使用预注册数据角色、主指标、配对层级和多重比较规则；
- B6 从 detached clean worktree 验证测试、配置解析、工件哈希和最小复现入口；
- Codex 独立检查实际 diff、结果和 provenance 后才能 APPROVE。

Report:

每阶段只通过 mailbox 报告 changed files、exact tip、checks/results、external run path、skipped checks、deviations、blockers 和下一阶段建议。中间协调记录留在 `coworker/runtime/`；只有最终研究成果进入 Study/02。

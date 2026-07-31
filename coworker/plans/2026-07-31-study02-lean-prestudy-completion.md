# Study/02 前置研究精简完成计划

> 长任务入口。当前状态以本文件的清单、Study/02 `00-A-执行状态.md` 和 coworker mailbox `STATUS.md` / `TRANSCRIPT.md` 共同恢复；不另建复杂控制面。

## 目标

用最小、可复现、足够严谨的代码与实验回答前置研究 A 的全部 19 个问题，并形成问题—证据—边界矩阵。保留 A-E1 r5、A-E3 r2 的既有成果，停止扩建原 formal 安全/授权流水线。

## 固定事实

- 分支：`codex/study02-lean-prestudy-20260731`
- 起点：`996434b2111ba328adda41d8593d7304a7a32250`
- A-E1 r5：349 fits，V 路线，已批准并冻结。
- A-E3 r2：266 fits，`huber + m12 + joint + fixed`，已由 Claude 审计并经 Codex APPROVE。
- 19 个研究问题保持不变；改变的是实验组织与实现规模。
- formal test namespaces 永久 sealed、不参与模型选择，也不再使用 lease、authority、unseal、consume、hash-chain、攻击防护等生产级控制面；精简路线用独立的 `confirmation` 留出评估集（区别于 training/validation/calibration，选择冻结后评估一次）为 19 个结论提供独立确认。

## 最小复现契约

每个新增实验组只需：

- 一个清晰配置；
- 一个可从命令行运行的入口；
- 固定 seed、数据角色与参数范围；
- 行级结果、聚合摘要、失败记录和必要图表；
- Git SHA、执行命令、依赖及输入配置记录；
- Codex 对结论和复现证据的阶段审查。

优先复用 `python/studies/common/`、现有 Study/02 数据/训练/评价代码和 A-E1/A-E3 checkpoint。只有两个以上新增实验确有共同需求时才提取新共享层。

## 阶段与进度

- [x] P0 计划重构：同步 README、Study README、`00-A`、`01-A`、`02-A`、`03-A`；明确旧 formal 引擎只读冻结、新的精简实验契约和恢复入口。✅ 已完成（tip `1a859258`），Codex 已接受 P0。
- [x] P1 E0 既有证据整理：复用 A-E1/A-E3，回答 A1、A4、A7、A8、A17、A18。✅ 完成（tip `133b8805`，Codex 已接受 P1；A4/A8 残留为 partial，留待后续最小补检）
- [x] P2 E1 训练设计敏感性：回答 A5、A6、A13。✅ 代码 tip `828abeba`；pilot 2/2、full 21/21、confirmation 完成；摘要与行级源表已入库。
- [x] P3 E2 比较与泛化：回答 A2、A3、A9、A10、A19。✓ 只读复用 60 个 A-E3 checkpoint；111,200 条 confirmation，60 个配对比较，7/7 预检通过。
- [x] P4 E3 等变性与稳健性：回答 A14、A15、A16。✓ 1,600 个配对数据集、20,800 条记录；NN 五种等变变换均过 1e-6，四类污染边界已量化。
- [x] P5 E4 工程可信度：回答 A11、A12。✓ 2,500 NIST 拆分；3,200 calibration；5,600 confirmation；真实迁移与区间域边界已量化。
- [ ] P6 收口：19/19 问题均绑定可复现证据、适用边界和失败/不支持结果；从干净 checkout 复跑必要入口；同步权威状态文档。

## 边界

允许：

- 修改上述权威文档、Study/02 代码、必要测试和精简实验产物索引。
- 在 `C:\weibull-runs\study02\lean` 保存较大运行产物；仓库只跟踪复现所需配置、代码、摘要和合理体量结果。
- 在 P0 经 Codex 审查后，自主实现并运行完成 P1–P6 所需的最小实验。
- 每个阶段形成一个连贯提交并通过 mailbox 报告 exact tip、命令、结果和下一阶段建议。

不允许：

- 修改、删除或重跑 A-E1 r5、A-E3 r1/r2 formal artifacts。
- 提前开展 Study/02 主研究或把 validation 结果冒充 held-out test 结论。
- 新增或扩展 formal scheduler、lease、authority、unseal/consume、hash-chain、capsule 或攻击面测试。
- 为了“以后可能复用”建设新框架。
- 合并 main、发布、部署、上传数据或执行其他外部副作用。

## 停止并请求用户决策

- 研究问题、主指标、参数范围或数据角色需要实质改变。
- 必须访问当前范围外的私有/外部数据。
- 预计新增训练显著超过 120 fits 或单阶段预计超过 24 小时，且无法通过复用/缩减设计解决。
- 结果暴露出会改变论文主线的重大科学矛盾。
- 发生不可恢复的数据或 Git provenance 问题。

普通代码错误、实验失败、无显著差异或局部不支持结论不是停止理由；应如实记录并继续完成问题矩阵。

## 审查与恢复

- Claude 是 executor，Codex 是 reviewer；最终 `APPROVE` 仅在 P6 和 19/19 完成后发出。
- 阶段报告默认存 mailbox archive；只在阶段成果需要长期引用时写 tracked report。
- 每次提交前更新本清单和 `00-A-执行状态.md` 的当前阶段、最近提交、下一动作。
- 窗口中断后：读取本文件 → `00-A-执行状态.md` → mailbox `STATUS.md` / `TRANSCRIPT.md` → `git status` / `git log`，从第一个未勾选阶段恢复。

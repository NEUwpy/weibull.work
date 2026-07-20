# Study/02 A G2 协议冻结报告

## 结果

G2 已把 19 个问题对应的参数空间、样本量、输入路线、目标变换、网络搜索、传统方法池、指标、四角色隔离、模块 test、真实数据、产物和 Git 规则冻结为可执行协议。

## 核心决策

- 主方案采用连续 Sobol 参数设计、参数组合互斥和严格等变的 `min + IQR/range` 锚点。
- 历史 H0/H1 重建与统一训练协议下的 F0eq/F1eq/F2/V/S 归因完全拆分。
- core 为 `beta=[1.2,4]`、`eta=[100,10000]`、`rho=[0,1]`；低/高 beta 和位置扩展独立报告。
- screening 3 seeds 与 formal 10 seeds 完全不相交。
- A-E1 → A-E3 → A-E2 的模型选择依赖、平局规则、fit cap 和矩阵展开规则进入机器配置。
- NIST 6061-T6 的 101 个完整疲劳寿命观测冻结为 A11 主真实数据源。

## 机器配置

- `Study/02-study-NN参数估计与分位点目标研究/configs/A-g2-protocol-v1.json`
- `Study/02-study-NN参数估计与分位点目标研究/configs/A-g2-search-v1.json`
- 最终 SHA-256 写入同目录 `.sha256` 文件。

## 验证

- A1-A19：19/19 覆盖。
- JSON：可解析。
- role/module seed：20 个设计/样本 namespace 全部唯一。
- screening/formal NN seed：交集为 0。
- MLP/DeepSets stage-1：各 12 个架构；stage-2：top 4 × 3 optimizer。
- Markdown/JSON：UTF-8、无尾随空格。
- `git diff --check`：通过。
- Oracle：Round 4 APPROVE。

## 边界

- G2 没有实现训练代码，也没有运行 pilot 或启封 test。
- A11/A12 的非阻塞统计细节按协议在 G5 formal 快照前补齐。

## 阶段关闭

- 内容提交：`ebef84ab0acc7a95e5b628b0730c7e9e677a67c0`。
- 远端分支：`origin/codex/long-task-20260711`。
- 远端 SHA 已核验与本地一致，G2 关闭并转入 G3。

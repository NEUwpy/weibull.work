# Study02 R9-R12 准备工作收口报告

## 结论

截至 2026-07-26，Study/02 的 R9-R12 准备工作已在代码 checkpoint `1bdd9906e87b53cd0cd1ad81bcfbb8ed8197a5a1` 收口。当前代码与证据合同达到“可以申请一个全新的 A-E1 formal training/validation 授权”的状态。

这不是 formal 授权，也不是实验完成：没有启动或恢复 formal，没有生成 approval，没有 authorize/unseal，没有生成、读取或消费 formal test。test 仍为 `sealed`，19 个前置研究问题仍没有 formal 结论。

## R9-R12 累积收口

| 轮次 | 代码 checkpoint | 收口内容 |
|------|-----------------|----------|
| R9 | `9c6188d` | staged ledger hash chain、显式 alias mapping、run-root selection evidence |
| R10 | `4ded6c0` | exact receipt、run-root evidence、A-E3 S/shared、A-E1 baseline 与最终 cohort 扫描 |
| R11 | `e3cb002` | `selected_top_N` 到 concrete architecture、staged cross-binding、统一 bundle v2 |
| R12 | `1bdd9906e87b53cd0cd1ad81bcfbb8ed8197a5a1` | 严格八记录 A-E1 staged reader、三模块 diagnostics/provenance 重建、统一 sealed-only builder、旧入口永久阻断、精确 sealed-genesis state 复用门与攻击测试 |

旧 A-E1 r1 `A-E1-formal-20260721-154250` 和 r2 `A-E1-formal-r2-20260722-233648` 仍永久 `blocked/aborted`。R9-R12 没有改变这一判定，也没有把旧 checkpoint 或局部产物拼接成正式证据。

## 四轮审查与修订

1. 第一轮检查生产调用方向、wrapper 参数传递、旧单模块 build/authorize 与 consumer 暴露、A-E3 `shared_n` 作用域及 orchestration 过度 mock；修订为单向 library 调用、旧入口 fatal、仅 A-E3/S 允许 shared。
2. 第二轮检查 A-E1 baseline 的独立 checkpoint replay、当前 scoped code/HEAD 绑定、逐 fit point provenance 和重复构建冲突；补齐 coherent tamper 防护、真实 guard 与 exact rerun/fail-closed 语义。
3. 第三轮检查 CLI 残留双实现、checkpoint 重建结果与 selection trace/diagnostics 的完整一致性、sealed state 字段集合及 guard 直接测试；删除死代码，并为 A-E1/A-E3/A-E2 增加自洽重链攻击。
4. 第四轮检查 Python `False == 0` 与宽松时间戳漏洞；counter 改为 exact non-boolean integer zero，时间戳改为相等且 canonical UTC ISO-8601 `Z` roundtrip，并覆盖 bool、float、字段、绑定和时间攻击。

四轮修订均未改变冻结 JSON、820-fit 矩阵、参数范围、指标、选择规则或 test sealed 边界。

## checkpoint 后验证

- clean-tree 三个 production-bound attack tests：`3 passed`。
- real、unmocked scoped-code clean 与 live HEAD guard：通过。
- 完整相关 non-slow：`247 passed, 5 deselected`。
- 没有活动 formal run、lease 或 formal 进程；没有 formal/approval/unseal/test 产物。

### slow 验证边界

5 个 slow 测试拆分状态如下：

| 测试范围 | 状态 |
|----------|------|
| one-fit end-to-end | 通过 |
| downstream defer | 通过 |
| post-selection authority rebuild | 通过 |
| real staged execution | 本收口未完成 |
| staged full-chain smoke | 本收口未完成 |

全 slow 合跑在 10 分钟达到超时后已终止。两个重 staged 测试没有在本收口预算内完成，因此记为“未完成”，不是测试失败；它们也不是本次“可申请新 A-E1 training/validation 授权”判定的必过项。不得把 3/5 写成 5/5，也不得把 timeout 写成研究或实现失败。

## 资源快照

- 当前 C 盘可用空间：31.57 GB。
- 冻结磁盘估计：4,225,761,280 bytes，已含 2x 余量。
- 冻结时间投影：1,373,822.99 秒，约 381.6 小时。

这些数字只是 2026-07-26 的准备快照。任何新 run 启动前必须重新测量容量、运行时间风险和 `<80%` 磁盘使用门，不能据此快照直接启动。

## 尚未回答、尚未执行

- `01-A-研究问题.md` 的 19 个问题均尚无新的 formal evidence 或 formal 结论。
- 尚未选出可用于主研究的正式参数路线基线。
- 没有新 A-E1 run；A-E3、A-E2 均未开始。
- 没有 approval、authorize、unseal 或 test consume。
- 没有生成 formal test 数据，也没有读取任何 formal test 数据。
- 准备闭合不等于 G3 完成，更不等于 Study/02 主问题已有答案。

## 唯一下步

下一步仅为按照 `coworker/plans/2026-07-26-study02-a-e1-formal-launch-contract.md` 申请一个全新的 A-E1 formal training/validation 显式授权。授权与启动是两个分开的动作；未获授权时不得执行候选命令或创建 run/lease/仓外目录。

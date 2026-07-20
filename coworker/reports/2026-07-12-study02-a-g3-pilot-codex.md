# Study/02 A G3 pilot 执行报告

## 结论

`G3-pilot-20260712-07` 已通过数据、输入、方法准入、存储和稳健运行时间闸门；formal test 始终为 `sealed`。当前结论为 **READY_FOR_ORACLE_REVIEW**，只有 oracle `APPROVE` 后才可启动 formal training。

Pilot 只验证管线和资源可行性，不回答 19 个研究问题，也不产生方法优劣结论。

## 冻结范围与版本

- 32 个 pilot-only scrambled Sobol core 参数点，每点 `n={5,20}` × 4 repeats，共 256 个样本；sample namespace `320204`。
- 九条输入路线：H0/H1、F0eq/F1eq/F2、V、S。
- G3 experiment matrix：820 fits，低于 900 上限；所有 test state 为 `sealed`。
- v7 code commit：`0e2ac19c5e7127e43ba6c48d5cf7c8f61d4577f4`。
- 生效修订：`A-G3-pilot-amendment-v4`，SHA-256 `164e72658669dbb57f6dab8b1fc80099bd319f1fa327d5dda60cb61cb929ee38`。
- 协议修订只把 `search.training.max_epochs` 从 500 降为 100；min epochs=50、patience=40、820 fits、10 formal seeds 与 720 h 闸门均不变。正式结果必须报告 epoch-100 ceiling-hit 比例，未经新审查不得延长。

## 实现与测试

- S 路线为 mask-aware `z` 集合 + 独立 `n` 通道，`n` 不作为伪集合元素。
- 准入合同包含 core 合法性、确定性、尺度等变、平移等变和失败状态传播。
- common runner 在求解器前拒绝非有限、过短或常数样本。
- 2,304 次 route-sample 检查无特征失败。
- 宽回归命令：`python -m pytest python/tests --ignore=python/tests/test_study01_e3b_contract.py -q`。
- 结果：152 passed in 121.11 s。忽略项是既有 Study01 E3b 文件硬编码 `D:/weibull`，与 Study02 修改无关；精确命令、输出、理由和校验和均在 v7 validation manifest 与 ledger 中。

## 传统方法准入

- 准入：WMLE、MDM-0.1。
- MLE 尺度等变失败；LRE、MMLE 平移等变失败。
- MPS、LSE、MM、PWM 为 `NotImplementedError` 占位，标记 `implementation_not_admitted`。
- 未准入方法保留逐合同状态和残差；formal 结论必须注明传统方法池因实现合同缩小，不能外推到全部传统估计法。

## 资源闸门

### 存储

- 预计 formal 结果行 768,000；以 512 compressed bytes/row、2 MiB/checkpoint 和 2×余量估计约 4,225,761,280 bytes。
- 当时可用磁盘约 59.40 GB；80% 闸门约 47.52 GB；`storage_gate_pass=true`。

### 稳健运行时间

- 25,000 条实际生成的 core-continuous F2 样本，`n=10`，最大 MLP 候选 m09。
- 每个 batch 先 warm-up，再按预注册交错顺序测 5 次，以中位数汇总。
- batch 32/128/512 的中位数分别为 0.004679、0.008125、0.015770 s/update。
- 4-worker 实测 speedup 为 1.032、0.931、0.853；按 `max(1,q25)` 回退为有效 worker=1，不假设线性加速。
- 100 epoch 上限下，投影 optimizer updates=78,791,300；2×余量后的保守墙钟为 1,373,822.99 s，约 381.6 h。
- 固定上限 2,592,000 s（720 h）；`runtime_gate_pass=true`。
- `resource_gate_pass=true`。

## 失败与替代轨迹

- v1：缺少 formal 总字节估计。
- v2：仅有单样本准入与非代表性 smoke 时间。
- v3：补完整准入和代表性基准，发现 runner 退化失败传播缺陷。
- v4：修复 runner，准入 WMLE/MDM；单次计时不稳定且资源门失败。
- v5：预注册五次重复和并发实测；500 epoch 投影失败。
- v6：200 epoch 在当次负载下仍失败。
- v7：100 epoch、ceiling-hit 审计规则、原矩阵和 seeds 不变；资源门通过。

v1-v7 全部保留，v3-v6 有显式 supersession，run ledger 只追加不覆盖。

## 下一闸门

1. oracle 审查 v7 与 `A-G3-pilot-amendment-v4`。
2. 若 `APPROVE`，提交并推送完整 pilot 证据包，再实现 formal 数据集、S collate/training、阶段化 selection trace 与 ceiling-hit 统计。
3. selection、泄漏审计和 calibration 冻结前，不得启封 formal test。

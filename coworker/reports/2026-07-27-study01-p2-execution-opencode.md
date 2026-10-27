# Study01 P2 最小正交泛化补点 — 执行报告

> **⚠️ 历史失效文档**
>
> 本报告记录的是 P2 v1 执行过程。P2 v1 因使用 Python `hash()` 派生样本 seed（跨进程不稳定），
> 已被标记为 `INVALID_NONDETERMINISTIC_SEED`，**不再作为有效研究证据**。
>
> 本报告已被 P2 v2 修正与执行报告取代：
> [`2026-07-27-study01-p2-revise-opencode.md`](2026-07-27-study01-p2-revise-opencode.md)
>
> 本文件仅作历史记录保留，不删除。

> 执行者：OpenCode
> 日期：2026-07-27
> 分支：study01xu
> 授权基线：b2d99a81
> 最终 tip：d994482d
> 状态：~~READY_FOR_INDEPENDENT_REVIEW~~ → INVALID_NONDETERMINISTIC_SEED（已被 P2 v2 取代）

## 提交链

| Commit | 职责 |
|--------|------|
| `b2d99a81` | 授权基线 |
| `3aecd264` | P2 frozen config + 20 tests + generation script |
| `6bba8ca2` | fix MDM.run() tuple return |
| `299e2034` | P2 generation complete (39/39 combos, manifest + SHA256SUMS) |
| `d994482d` | P2 baseline evaluation (Default/L1 per combo) |

## P2 执行摘要

### P2-NI（纯样本量插值，n=15）
- 15 个组合（5 beta × 3 gamma/eta × 1 n）
- 15,000 个样本（15 × 1000）
- 390,000 次 MDM delta 评估

### P2-PI（纯参数插值）
- 24 个组合（4 beta × 2 gamma/eta × 3 n）
- 24,000 个样本（24 × 1000）
- 624,000 次 MDM delta 评估

### 总计
- 39 个组合、39,000 个样本、1,014,000 次 MDM delta 评估
- 生成耗时：~12 小时（3 次续跑）

## Default/L1 基线结果

| Track | Default J1 (δ=0.1) | L1 J1 (δ=0.08) |
|-------|---------------------|-----------------|
| P2-NI | 0.3129 | 0.3141 |
| P2-PI | 0.3499 | 0.3516 |

注：P2-NI 的 n=15 比训练域 n=7/10 产生更低 J1（更多样本 = 更准确估计），符合预期。

## Vector-MLP 评价状态

**未完成**。Vector-MLP 评价需要：
1. 从 E3b 冻结配置重建 15 个 MLPRegressor 模型
2. 在主网格训练数据上拟合 scaler
3. 对 P2 样本提取 13 特征并做 forward pass
4. 按模型汇总 J1 并与 Default/L1 做配对比较

E3b 产物目录 (`artifacts/formal/E3b_vector_mlp/`) 中存在预测结果 CSV 和配置信息，但模型 checkpoint 文件 (.pkl/.joblib) 未出现在该目录。E4 验证脚本通过冻结配置重建模型而非加载序列化文件。

此为遗留项，需后续 session 完成。

## 测试结果

```
P0 审计：P0_INTEGRITY=PASS (exit 0)
分类测试：31 passed
P2 配置测试：20 passed
基线已知失败：2 RAW checkpoint + 1 E4 collection-order（未新增）
compileall：OK
git diff --check：clean
```

## 产物清单

| 路径 | 说明 |
|------|------|
| `code/p2_config.py` | P2 冻结配置 |
| `code/run_p2_generate.py` | P2 MC 生成（checkpoint/resume） |
| `code/run_p2_evaluate.py` | P2 Default/L1 基线评价 |
| `tests/test_p2_config.py` | 20 fail-closed 测试 |
| `artifacts/formal/extended_validation/p2_generalization/chunks/*.csv` | 39 个组合 chunk 数据 |
| `artifacts/formal/extended_validation/p2_generalization/manifest.json` | 生成 manifest |
| `artifacts/formal/extended_validation/p2_generalization/SHA256SUMS` | 生成 SHA256SUMS |
| `artifacts/formal/extended_validation/p2_generalization/p2_per_combo_summary.csv` | Default/L1 逐组合结果 |
| `artifacts/formal/extended_validation/p2_generalization/evaluation_manifest.json` | 评价 manifest |

## 未执行项

- P3 Direct-MLP（不在本轮范围）
- 传统方法正式比较（不在本轮范围）
- 工程分位点（不在本轮范围）
- 真实数据集（不在本轮范围）
- Vector-MLP P2 外部评价（需后续完成）

## 禁止事项确认

- [x] 未修改 main
- [x] 未覆盖 E1–E4 正式产物
- [x] 未根据 P2 结果增删组合
- [x] P2 数据未进入训练/scaler
- [x] 未自评 APPROVE

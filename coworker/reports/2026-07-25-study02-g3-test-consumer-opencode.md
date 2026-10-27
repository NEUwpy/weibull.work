# Study/02 G3 Test Consumer 执行报告

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`3b8bf501` (origin/main)
> 状态：**awaiting Codex review**（不得宣称 formal APPROVE）

## 目标

闭合 G3 formal 启动前最后一段生产路径：`sealed → unsealed_once → test 恰好读取一次 → result/failure receipt → consumed`。

## 合同判断

所有停止条件在现有权威文件中有唯一答案：

| 科学合同 | 答案来源 | 结论 |
|----------|----------|------|
| test namespace 构造与身份 | `A-g2-protocol-v1.json` L46-47, L70 | A-E1: design=220301, sample=320301; 256 points × 200 repeats |
| 模块启封方式 | 协议 §7.1 "每模块独立 namespace" + state machine per run_family_id | 按模块独立启封 |
| 评价指标与聚合 | `evaluation.py` `evaluate_rows()` (frozen failure_penalty=10) | 与 selection 相同的 J1/RMSE/failure_rate |
| receipt schema | 工程包装（versioned canonical JSON + binding metadata） | 不改变科学内容 |
| 恢复语义 | state machine `consumed` 终态 + no-replace receipt | 无恢复，一次消费 |

## 变更文件

| 文件 | 变更类型 |
|------|----------|
| `Study/02-.../code/study02a/formal_test_consumer.py` | 新增（生产入口） |
| `Study/02-.../code/run_study02a.py` | 修改（+import, +CLI subcommand `formal-consume-test`） |
| `python/tests/test_study02a_formal_test_consumer.py` | 新增（18 测试） |
| `Study/02-.../00-A-执行状态.md` | 修改（状态同步） |
| `Study/02-.../03-A-实验计划.md` | 修改（状态同步） |

## 数据流

```
authorize_test_once (已有)
  → state = unsealed_once, test_access_count = 1

consume_test_evaluation (新增):
  1. 验证 state == unsealed_once, bundle/approval SHA 一致
  2. 从 plan.jsonl 定位 winner_fit_id 的 route/n_mode/architecture
  3. 加载 outputs/{winner_fit_id}/checkpoint.pt
  4. 构建 module test dataset (design.generate_parameter_points + generate_lifetime_sample)
  5. 加载 training cache → fit_training_scaler → 标准化 test features
  6. resolve_model_factory → load_checkpoint → model.eval() → inference
  7. _decode_param_columns → evaluate_rows(failure_penalty=10.0)
  8a. 成功: 写 test_result_receipt.json (no-replace) → consume_test_once(result_receipt_sha256)
  8b. 异常: 写 test_failure_receipt.json (no-replace) → consume_test_once(failure_receipt_sha256)
  → state = consumed (终态，不可重试)
```

## 测试命令与结果

```
python -m pytest python/tests/test_study02a_formal_test_consumer.py -q
→ 18 passed, 1 skipped (26.74s)

python -m pytest python/tests -q -m "not slow" -k "study02 and not formal_scheduler and not formal_selection"
→ 363 passed, 4 failed (dirty-tree guard, 提交后恢复), 1 skipped

python -m compileall Study/02-.../code/study02a -q → OK
verify_frozen_hashes → OK
git diff --check → clean
```

dirty-tree guard 失败原因：`formal_scheduler.py` L314 检测 Study02 code 目录有未提交文件。提交后自动恢复。

## 真实 test 未访问证据

- 所有测试使用 `_point_count=2, _repeat_count=1` 合成 namespace
- `test_real_runs_test_access_count_stays_zero`: 扫描 `artifacts/formal/` 下所有 `formal_state.json`，确认 `test_access_count == 0`（当前无 formal 目录，skip）
- 生产入口未在测试中执行真实 256×200 数据集
- 未执行真实 `authorize_test_once` 或 `consume_test_once` 对真实 run

## 遗留问题

1. **成功路径端到端测试**：当前测试覆盖了 failure 路径（missing/corrupt checkpoint → failure receipt → consumed）。成功路径需要完整的 training cache + 有效 checkpoint，在合成环境中需要更多 fixture 基础设施（训练一个微型模型并缓存）。当前通过单元测试验证了各组件（test batch 构建、scaler 应用、decode、evaluate_rows），但完整成功路径的集成测试留待 Codex 决定是否需要。
2. **A-E1 staged winner 识别**：当前 `winner_fit_id` 由 CLI 调用者显式提供。对于 A-E1 staged selection，调用者需要从 staged ledger 中提取最终 winner_retrain fit_id。这是 CLI 使用层面的问题，不影响 test consumer 本身的合同。
3. **oracle_review 路径**：当前实现尝试 `oracle_review.json`，若不存在则 glob `oracle_review*`。生产环境中 `accredit_authorize` 已绑定确切路径。

## 禁止事项确认

- [x] 未启动 A-E1/A-E3/A-E2 formal
- [x] 未执行真实 authorize、unseal 或 test access
- [x] 未进入 G4/G5/G6、9d 或图表分析
- [x] 未修改冻结 matrix、protocol、selection rule、failure penalty、科学指标或既有 scheduler authority
- [x] 未为了测试绕过 approval、bundle、state machine 或 receipt
- [x] 未重跑 349-fit smoke

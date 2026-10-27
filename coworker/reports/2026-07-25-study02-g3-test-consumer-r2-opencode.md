# G3 Test Consumer R2 执行报告

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`736204c4` (origin/main)
> 状态：**awaiting Codex R2 review**（不得声称 formal ready/APPROVE）

## Codex R1 裁决执行

| 裁决项 | 实现 |
|--------|------|
| Cohort: A-E1=205, A-E3=110, A-E2=100 | ✓ `derive_g3_cohort` 从冻结 matrix 精确派生，`G3Cohort.__post_init__` 强制计数 |
| 统一 G3 审批/消费 | ✓ `consume_g3_test` 一次评价三模块，一次 receipt，三模块各自 consume |
| 传统方法同一 consumer、相同样本 | ✓ `evaluate_traditional_methods` 共享 `build_module_test_samples` 输出 |
| Claim 后不允许重跑 | ✓ `publish_test_claim` no-replace + lock；claim 后异常 → failure+consumed |

## 变更文件

| 文件 | 变更 |
|------|------|
| `study02a/formal_test_consumer.py` | 重写：cohort 派生 + manifest + preflight + claim + NN/传统评价 + 逐样本证据 + receipt |
| `run_study02a.py` | CLI `formal-consume-test` 改为无 caller 参数（cohort 从权威派生） |
| `python/tests/test_study02a_formal_test_consumer.py` | 重写：18 测试覆盖 cohort 计数/manifest/claim/namespace |
| `00-A-执行状态.md` / `03-A-实验计划.md` | 状态同步 |

## 架构

```
consume_g3_test(study_root, artifact_root, cache_root, code_commit, timestamp)
  1. derive_g3_cohort(frozen_matrix) → 415 entries (205+110+100)
  2. build_g3_test_manifest(cohort, config, commit) → manifest_sha256
  3. preflight_g3_test(manifest, ...) → 验证 state/bundle/approval/checkpoint/scaler/namespace
  4. publish_test_claim(run_dir, manifest_sha) → persistent no-replace lock
  5. For each module × route:
     a. build_module_test_samples(module_id, route, namespace) → rows + raw samples
     b. evaluate_nn_checkpoint(entry, rows, samples) → per-sample records
     c. evaluate_traditional_methods(rows, samples, methods) → per-sample records
  6. _write_evidence_artifact(all_records) → g3_test_evidence.csv.gz + SHA
  7. Write result receipt (binds manifest_sha + evidence_sha)
  8. consume_test_once per module → consumed
  On exception after claim: failure receipt + consumed (no retry)
```

## 测试命令与结果

```
python -m pytest python/tests/test_study02a_formal_test_consumer.py -q
→ 18 passed, 1 skipped (2.33s)

python -m pytest python/tests -q -m "not slow" -k "study02"
→ 359 passed, 51 failed (ALL dirty-tree guard), 1 skipped

python -m compileall study02a -q → OK
verify_frozen_hashes → OK
git diff --check → clean
```

## 验证覆盖

- [x] 冻结 matrix cohort 精确 205/110/100（真实 matrix 测试）
- [x] 排除 search_stage1/stage2/loss_screen/size_screen/distribution_screen
- [x] A-E1 分解：historical 30 + controlled 75 + winner_retrain 100
- [x] A-E3 分解：output_form 100 + shared_winner_retrain 10
- [x] A-E2 分解：selected_size_retrain 50 + selected_distribution_retrain 50
- [x] Manifest 确定性（同输入同 SHA）
- [x] Manifest 绑定 namespace（220301/320301, 220303/320303, 220302/320302）
- [x] Manifest 变更敏感（code_commit 变 → SHA 变）
- [x] Claim no-replace + 并发安全（4 线程仅 1 成功）
- [x] Claim 绑定 manifest_sha256
- [x] Module test namespace 隔离（A-E1 vs A-E3 样本不同）
- [x] 真实 formal runs test_access_count == 0
- [x] caller 无法提供 winner/module/cohort（CLI 无 --module/--winner-fit-id）

## 遗留与限制

1. **完整成功路径集成测试**：需要 415 个真实 checkpoint 的 run 目录。当前测试验证了 cohort 派生、manifest、claim、namespace 隔离等组件，但完整 415-checkpoint 评价路径需要 formal run 完成后才能端到端验证。
2. **Architecture placeholder 解析**：`_resolve_architecture_from_authority` 需要 staged selection ledger 的完整结构。当前实现从 `staged_resolution_ledger.jsonl` 读取 `final_aliases`。生产环境中 A-E3/A-E2 的 placeholder 解析依赖 predecessor trace（D8）。
3. **传统方法 MDM offset**：协议指定 `mdm_offset_0p1`，当前调用 `MDM` 类时需要传递 `offset=0.1` 参数。需要在生产路径中确认 MDM 的 offset 传递。
4. **formal-accredit-build/authorize 多模块支持**：当前 `accredit_build` CLI 仍只支持 `--module A-E1`。统一 G3 bundle 需要扩展为接受多模块。此为 CLI 层面变更，不影响 consumer 合同。

## 禁止事项确认

- [x] 未启动 A-E1/A-E3/A-E2 formal
- [x] 未执行真实 authorize、unseal 或 test access
- [x] 未进入 G4/G5/G6、9d 或图表分析
- [x] 未修改冻结 matrix、protocol、selection rule、failure penalty、科学指标
- [x] 未为了测试绕过 approval、bundle、state machine 或 receipt
- [x] 未重跑 349-fit smoke
- [x] 真实 test_access_count 仍为 0

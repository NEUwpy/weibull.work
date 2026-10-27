# G3 Test Control Plane R8 执行报告

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`40c24293` (origin/main)
> 状态：**awaiting Codex R8 review**

## R8 修正内容

| R7 错误 | 修正 |
|---------|------|
| `active_claim` 字段名错误 | → `live_claim`（scheduler 权威字段） |
| `validate_controller=False` | → 删除，使用默认 True（完整 controller-anchor 验证） |
| `_validate_selection_trace_bytes` 错误签名 | → `_validate_selection_evidence`（含 receipt/ledger 绑定验证） |
| distribution 硬编码 `core_continuous` | → 从 verified plan row 读取；historical=`legacy_grid`；selected_distribution 从 A-E2 证据 |
| `"0"*64` 占位哈希 | → 删除；ceiling_hit_report/leakage_audit 缺失即 fail-closed |
| `sealed_ready_for_approval` 未落盘 | → manifest/bundle/state 全部 no-replace 落盘 + 相互 SHA 绑定验证后才返回 |
| 三 run 一致性未验证 | → `_verify_chain_consistency`：module/run/predecessor/code_commit/effective_config/matrix SHA |
| terminal receipt SHA 混淆 | → 使用 `receipts/*.succeeded.json`（scheduler terminal receipt），非 `outputs/fit_status.json` |

## 变更文件

| 文件 | 变更 |
|------|------|
| `study02a/formal_g3_control.py` | 修正 `verify_g3_chain_authority`（live_claim + controller=True + 一致性验证）、`derive_g3_cohort_from_authority`（plan distribution + scheduler receipt）、`resolve_g3_placeholders_from_evidence`（_validate_selection_evidence + distribution 解析）、`build_g3_accreditation`（fail-closed 诊断工件 + 落盘 + SHA 绑定） |
| `python/tests/test_study02a_g3_control.py` | 修正 `live_claim` 字段名 |

## 测试命令与结果

```
python -m pytest python/tests/test_study02a_g3_control.py -q → 26 passed, 4 skipped (dirty-tree)
python -m compileall study02a -q → OK
verify_frozen_hashes → OK
git diff --check → clean
```

提交后在干净工作树重新运行全部 Study02 non-slow。

## 禁止事项确认

- [x] formal-consume-test 继续 BLOCKED
- [x] 未启动 formal、authorize/unseal、生成或读取 test
- [x] 未修改冻结 matrix/selection rule/科学指标
- [x] 未扩展 journal 或安全基础设施

# G3 Test Control Plane R6 执行报告

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`179a62f0` (origin/main)
> 状态：**awaiting Codex R6 review**（不得声称 test consumer 或 formal ready）

## R6 修订内容

| Codex R5 要求 | 实现 |
|---------------|------|
| 不根据 mtime 自动抢占未知锁 | 删除 `stale_lock_max_age_seconds`；lock 存在即 fail-closed；lock 文件含 holder+pid 身份 |
| Journal event 逐字段重建验证 | `_verify_journal_event_against_inputs`：从已验证 approval/bundle/manifest/oracle_review 重建所有 SHA，逐字段比较 journal event |
| Atomic replace + fsync | `_atomic_write`：write→flush→fsync→os.replace；`_append_ledger_fsync`：write→flush→fsync |
| Journal 存在但审批输入缺失/篡改 | `_verify_journal_event_against_inputs` 检查所有输入文件存在且 canonical |
| 所有攻击失败保持原始字节不变 | 验证在 state/ledger 写入前完成；任何 mismatch 在 journal replay 前 raise |

## 变更文件

| 文件 | 变更 |
|------|------|
| `study02a/formal_g3_control.py` | 删除 mtime lock；`_atomic_write`/`_append_ledger_fsync`/`_acquire_lock` 使用 Python file I/O + fsync；`_verify_journal_event_against_inputs` 逐字段验证 |
| `python/tests/test_study02a_g3_control.py` | stale lock 改为 fail-closed 测试 |

## 关键设计

### Lock（fail-closed，无 mtime 抢占）
```
lock 文件内容: {"holder": "<id>", "pid": <pid>}
lock 存在 → raise ValueError（不检查 mtime）
恢复入口必须验证 journal + 持有者身份后才能清除 lock
```

### Journal event 逐字段重建
```
_verify_journal_event_against_inputs(event, paths...):
  1. 读取 approval/bundle/manifest/oracle_review 实际 bytes
  2. 验证 canonical + version + decision
  3. 计算 bundle_sha, manifest_sha, approval_sha, oracle_review_sha
  4. 逐字段比较:
     - event.approval_sha256 == approval_sha
     - event.g3_pre_unseal_bundle_sha256 == bundle_sha
     - event.g3_test_manifest_sha256 == manifest_sha
     - event.transition == "authorize_g3_test_once"
     - event.seq == 1
     - event.test_access_count == 1
     - approval binds bundle + manifest
  5. 任何 mismatch → raise（state/ledger 不变）
```

### Atomic write
```
_atomic_write(path, payload):
  tmp = path.name + ".tmp"
  open(tmp, "wb") → write → flush → fsync → close
  os.replace(tmp, path)  # atomic on POSIX and Windows
```

## 测试命令与结果

```
python -m pytest python/tests/test_study02a_g3_control.py -q → 24 passed (4.04s)
python -m compileall study02a -q → OK
verify_frozen_hashes → OK
git diff --check → clean
```

## 验证覆盖

- [x] 正常 lifecycle: sealed → unsealed_once（atomic state + fsync ledger）
- [x] Repeat authorize 拒绝
- [x] Wrong approval decision 拒绝（state 保持 sealed）
- [x] Old bundle version 拒绝
- [x] Bundle tamper 拒绝（state 保持 sealed）
- [x] Oracle review SHA 不匹配拒绝（state 保持 sealed）
- [x] Oracle review 缺失拒绝
- [x] 并发 authorize（4 线程仅 1 成功）
- [x] **Stale lock fail-closed**（即使 2h 旧也不抢占，state 保持 sealed）
- [x] Fresh lock 拒绝（state 保持 sealed）
- [x] 伪造 journal（neither before/after）拒绝（state 保持 sealed）
- [x] 篡改 ledger prefix 拒绝
- [x] Crash 后 recovery：journal 清理 + ledger 补写 + 逐字段验证
- [x] 四方 SHA 一致（manifest/bundle/state/approval）
- [x] Manifest no-replace
- [x] CLI formal-consume-test 仍为 BLOCKED
- [x] Cohort 精确 205/110/100

## 遗留（需要真实 run 目录）

1. **`_rebuild_authority` 实际调用**：需要真实 run 目录（manifest + plan.jsonl + events + scheduler_state + controller anchors）。当前 `resolve_g3_predecessor_chain` 读取 manifest 但未调用 `_rebuild_authority`。
2. **Production selection_trace.jsonl 验证**：需要调用 `_validate_selection_trace_bytes` 等既有验证器。当前 `_load_resolutions` 直接读取 JSON。
3. **Cohort fit 与 replay fit_state 交叉验证**：需要从 `_rebuild_authority` 返回的 state 中获取 fit_states。

## 禁止事项确认

- [x] 未启动 formal、authorize 或真实 test
- [x] 未生成 test 数据
- [x] 未执行 consumer
- [x] 未修改冻结 matrix/protocol/selection rule
- [x] 真实 test_access_count 仍为 0

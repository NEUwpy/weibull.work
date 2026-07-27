# G3 Test Control Plane R5 执行报告

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`8ea0830b` (origin/main)
> 状态：**awaiting Codex R5 review**（不得声称 test consumer 或 formal ready）

## R5 修订内容

| Codex R4 要求 | 实现 |
|---------------|------|
| 复用 formal_state.py journal 模型 | `_recover_g3_journal` 重写：exact-schema 验证、ledger prefix (size+SHA)、before/after state SHA 检查、truncate+fsync+rewrite |
| 删除无条件信任 journal | 旧版 `{"after_state_bytes", "event_line"}` 已删除；新版记录 `{event, ledger_size_before, ledger_sha_before}`，recovery 验证三方一致性 |
| Stale lock 受控恢复 | 检查 lock 文件 mtime 年龄；超过 `stale_lock_max_age_seconds`（默认 3600s）才清除；新鲜 lock 拒绝 |
| Oracle review 工件验证 | `authorize_g3_test_once` 新增 `oracle_review_path` 参数；验证 approval.oracle_review_artifact_sha256 == 磁盘文件 SHA |
| 攻击测试 | 伪造 journal（neither before/after）、篡改 ledger prefix、crash 遗留 lock（新鲜/过期）、oracle review SHA 不匹配、oracle review 缺失 |
| 所有失败保持 sealed + ledger 不变 | 每个攻击测试验证 state["state"]=="sealed" |

## 变更文件

| 文件 | 变更 |
|------|------|
| `study02a/formal_g3_control.py` | journal 模型重写（formal_state.py 模式）+ stale lock + oracle_review_path |
| `python/tests/test_study02a_g3_control.py` | 24 测试（+6 攻击测试：forged journal、tampered ledger prefix、stale/fresh lock、oracle review mismatch/missing） |

## Journal 恢复模型（与 formal_state.py 一致）

```
journal = {event, ledger_size_before, ledger_sha_before}

recovery:
  1. 验证 journal exact schema
  2. 验证 ledger prefix: len >= size_before, SHA(prefix) == sha_before
  3. if state_sha == before_state_sha:
       要求 ledger 未变（len == size_before）→ 删除 journal（crash before state write）
  4. if state_sha == after_state_sha:
       检查 ledger suffix 是否已包含 event → 完成或 truncate+rewrite
  5. else: raise（corruption）
```

## 测试命令与结果

```
python -m pytest python/tests/test_study02a_g3_control.py -q → 24 passed (3.36s)
python -m compileall study02a -q → OK
verify_frozen_hashes → OK
git diff --check → clean
```

## 验证覆盖

- [x] 正常 lifecycle: sealed → unsealed_once（journal 创建→state→ledger→journal 删除）
- [x] Repeat authorize 拒绝
- [x] Wrong approval decision 拒绝（state 保持 sealed）
- [x] Old bundle version 拒绝
- [x] Bundle tamper 拒绝（state 保持 sealed）
- [x] Oracle review SHA 不匹配拒绝（state 保持 sealed）
- [x] Oracle review 缺失拒绝
- [x] 并发 authorize（4 线程仅 1 成功）
- [x] Stale lock（>3600s）受控恢复后成功
- [x] Fresh lock（<3600s）拒绝（state 保持 sealed）
- [x] 伪造 journal（before/after 均不匹配）拒绝（state 保持 sealed）
- [x] 篡改 ledger prefix 拒绝
- [x] Crash 后 recovery：state 已 unsealed_once + journal 清理 + ledger 补写
- [x] 四方 SHA 一致（manifest/bundle/state/approval）
- [x] Manifest no-replace
- [x] CLI formal-consume-test 仍为 BLOCKED
- [x] Cohort 精确 205/110/100

## 遗留

1. **`_rebuild_authority` 真实调用**：当前 `resolve_g3_predecessor_chain` 读取 manifest 但未调用完整 `_rebuild_authority`（需要真实 run 目录含 plan/events/scheduler_state/controller anchors）。生产路径需要在真实 run 上集成。
2. **Resolution 通过既有验证器**：当前 `_load_resolutions` 直接读取 staged ledger 和 selection trace JSON。生产路径应调用 `_validate_selection_trace_bytes` 等既有严格验证器。
3. **Cohort fit 与 replay fit_state 一致性**：当前验证 checkpoint/receipt 存在且 SHA 非空。生产路径应从 `_rebuild_authority` 的 replay state 中获取 fit_states 并交叉验证。

## 禁止事项确认

- [x] 未启动 formal、authorize 或真实 test
- [x] 未生成 test 数据
- [x] 未执行 consumer
- [x] 未修改冻结 matrix/protocol/selection rule
- [x] 真实 test_access_count 仍为 0

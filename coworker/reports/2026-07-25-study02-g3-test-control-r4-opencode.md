# G3 Test Control Plane R4 执行报告

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`21bb1b8e` (origin/main)
> 状态：**awaiting Codex R4 review**（不得声称 test consumer 或 formal ready）

## R4 修订内容

| Codex R3 要求 | 实现 |
|---------------|------|
| 删除默认猜测/异常吞掉/空 SHA | `_resolve_field` 未解析即 raise；`_resolve_training_size` 无默认值；`_resolve_distribution` 无 fallback；`_load_resolutions` 不吞异常；cohort 要求非空 checkpoint+receipt SHA |
| Manifest 先于 bundle；读实际 bytes | `authorize_g3_test_once` 新增 `manifest_path` 参数，从磁盘读取并验证 manifest/bundle/approval 实际 bytes |
| 并发互斥 + 崩溃恢复 | `authorize_g3_test_once` 使用 O_CREAT|O_EXCL 文件锁 + journal（state 写前创建，ledger 写后删除）；`_recover_g3_journal` 重放 |
| State/ledger 一致性 | journal 保证 state+ledger 原子性；崩溃后 journal replay 确保 ledger 包含 event |
| 旧版拒绝 | bundle_version/approval_version/state_version 精确匹配，否则 raise |
| formal-consume-test BLOCKED | 保持 SystemExit（R3 已实现） |

## 变更文件

| 文件 | 变更 |
|------|------|
| `study02a/formal_g3_control.py` | 严格化 resolution + 并发锁 + journal 崩溃恢复 + manifest_path 验证 |
| `python/tests/test_study02a_g3_control.py` | 新增并发 authorize（4线程仅1成功）+ 崩溃恢复 journal replay 测试；所有 authorize 调用增加 manifest_path |

## 测试命令与结果

```
python -m pytest python/tests/test_study02a_g3_control.py -q → 18 passed (3.33s)
python -m pytest python/tests/test_study02a_formal_test_consumer.py -q → 18 passed
python -m compileall study02a -q → OK
verify_frozen_hashes → OK
git diff --check → clean
```

## 验证覆盖

- [x] 并发 authorize：4 线程仅 1 成功，3 被锁拒绝
- [x] 崩溃恢复：journal 存在时 replay state+ledger，journal 删除
- [x] Manifest 从磁盘读取并验证 self-SHA
- [x] Bundle/approval 从磁盘读取并验证 canonical + self-SHA
- [x] 四方 SHA 一致（manifest/bundle/state/approval）
- [x] 未解析 placeholder 立即 raise（无默认值）
- [x] 缺失 checkpoint/receipt 立即 raise（无空 SHA）
- [x] 缺失 staged ledger / selection dir 立即 raise（无异常吞掉）
- [x] 旧版 bundle/approval/state 拒绝
- [x] Repeat authorize 拒绝
- [x] Wrong approval decision 拒绝
- [x] Bundle tamper 拒绝
- [x] CLI formal-consume-test 仍为 BLOCKED

## 禁止事项确认

- [x] 未启动 formal、authorize 或真实 test
- [x] 未生成 test 数据
- [x] 未执行 consumer
- [x] 未修改冻结 matrix/protocol/selection rule
- [x] 真实 test_access_count 仍为 0

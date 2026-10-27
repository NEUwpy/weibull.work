# G3 Test Control Plane R3 执行报告

> 执行者：OpenCode (qwen3.8-max-preview)
> 日期：2026-07-25
> 起点：`6346dc74` (origin/main)
> 状态：**awaiting Codex R3 review**（不得声称 test consumer 或 formal ready）

## R3 目标执行

| 目标 | 实现 |
|------|------|
| CLI fail-closed | `formal-consume-test` 立即 SystemExit("BLOCKED")，不执行任何评价 |
| G3 test-execution manifest (v2) | `build_g3_test_manifest` + `publish_g3_test_manifest`（no-replace, canonical） |
| Predecessor chain 解析 | `resolve_g3_predecessor_chain`：从 A-E2 manifest → A-E3 → A-E1，禁止目录扫描 |
| 统一 G3 bundle (v1) | `build_g3_pre_unseal_bundle`：绑定三模块 run IDs/authority SHA + manifest SHA + matrix SHA |
| 统一 G3 approval (v1) | `publish_g3_approval`：绑定 bundle SHA + manifest SHA + matrix SHA |
| 统一 G3 state (v1) | `initialize_g3_formal_state` + `authorize_g3_test_once`：sealed → unsealed_once |
| FROZEN_MATRIX_SHA256 | 使用 `fad701af...`（formal_contracts.py L30），非 protocol SHA |
| Cohort 派生 | `derive_g3_cohort_resolved`：205/110/100，resolved 字段，拒绝 selected:*/-1 |
| 旧版拒绝 | bundle_version != `study02-g3-pre-unseal-v1` → 拒绝 |

## 变更文件

| 文件 | 变更 |
|------|------|
| `study02a/formal_g3_control.py` | 新增：G3 控制面（predecessor chain, manifest, bundle, approval, state） |
| `run_study02a.py` | `formal-consume-test` 改为 fail-closed SystemExit |
| `python/tests/test_study02a_g3_control.py` | 新增：16 测试 |
| `00-A-执行状态.md` / `03-A-实验计划.md` | 状态同步 |

## Schema 版本

| 文档 | 版本 | 旧版处理 |
|------|------|----------|
| G3 manifest | `study02-g3-test-manifest-v2` | v1 无迁移路径（从未生产使用） |
| G3 bundle | `study02-g3-pre-unseal-v1` | `study02-pre-unseal-v3` 被拒绝 |
| G3 approval | `study02-g3-test-unseal-approval-v1` | `study02-test-unseal-approval-v1` 被拒绝 |
| G3 state | `study02-g3-formal-state-v1` | `study02-formal-state-v1` 被拒绝 |

## 测试命令与结果

```
python -m pytest python/tests/test_study02a_g3_control.py -q → 16 passed (3.72s)
python -m pytest python/tests/test_study02a_formal_test_consumer.py -q → 18 passed
python -m compileall study02a -q → OK
verify_frozen_hashes → OK
git diff --check → clean
```

## 验证覆盖

- [x] CLI `formal-consume-test` 拒绝执行（returncode != 0, "BLOCKED"）
- [x] Predecessor chain 正确解析（A-E2 → A-E3 → A-E1）
- [x] Wrong predecessor module 拒绝
- [x] A-E1 有 predecessor 拒绝
- [x] Cross-run predecessor（不存在的 run）拒绝
- [x] Manifest/bundle/approval/state 四方 SHA 一致
- [x] sealed → unsealed_once 成功（synthetic approval）
- [x] Repeat authorize 拒绝
- [x] Wrong approval decision 拒绝
- [x] Old bundle version 拒绝
- [x] Bundle tamper（self-SHA mismatch）拒绝
- [x] Manifest no-replace
- [x] FROZEN_MATRIX_SHA256 正确绑定
- [x] Cohort 精确 205/110/100（真实冻结 matrix）

## 遗留

1. **`_rebuild_authority` 集成**：当前 predecessor chain 解析读取 manifest 但不调用完整 `_rebuild_authority`（需要真实 run 目录含 plan.jsonl、events、scheduler_state）。生产路径需要在真实 run 上调用。
2. **Cohort resolved 字段**：`_load_resolutions` 从 staged ledger 读取 aliases。生产环境需要完整的 staged selection 产物。
3. **统一 G3 state 的 consume 路径**：R3 只实现到 unsealed_once。consume 路径（评价 + receipt）留待后续。
4. **formal-accredit-build/authorize 多模块 CLI**：当前 CLI 仍为单模块。统一 G3 的 CLI 入口需要新增 `g3-accredit-build` / `g3-accredit-authorize` 子命令。

## 禁止事项确认

- [x] 未启动 formal、authorize 或真实 test
- [x] 未生成 test 数据
- [x] 未执行 consumer
- [x] 未修改冻结 matrix/protocol/selection rule
- [x] 真实 test_access_count 仍为 0

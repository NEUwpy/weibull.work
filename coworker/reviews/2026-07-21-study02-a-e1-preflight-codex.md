# Study02 A-E1 Formal — Codex Preflight Review

**Verdict history: 原始 APPROVE 已被 Codex R2 REVISE 覆盖。当前 verdict：REVISE（operational wiring awaiting review）。A-E1 formal 未经授权。**

审查日期：2026-07-21 · 修订：R2

---

## 1. 审查范围

- 仓库：`D:\weibull`，main @ `c50ad0c1`
- Study02 合入：merge commit `6c955b6e`（原分支 tip `8e9abd33`）
- 工作树：`D:\weibull-preflight-study02`，分支 `codex/study02-a-preflight-20260721`
- 脏文件（仅 main 工作树）：`08-更新日志.md`（study01 变更，未触碰）

---

## 2. 已确认事实

| 项目 | 结果 |
|------|------|
| compileall | OK |
| 非 slow 测试 | 364 passed（含 CLI dispatch + guard 测试） |
| 349-fit sealed smoke | PASSED（2h13min，不再重跑） |
| test_access_count | 0 |
| frozen configs | 全部 hash 验证通过 |
| effective_config_sha256 | 匹配 `APPROVED_EFFECTIVE_CONFIG_SHA256` |
| CLI 子命令 | 9 个全部可用 |
| 磁盘 | ~596 GB free |

所有 pre-formal 组件已 Codex APPROVE：
- staged A-E1 source-of-truth（`10d6fcf`）
- point_evidence 迁出（`4d5c9cd`+`e9f455a`+`28b1d18`）
- anchor 性能（`d480c13`）
- alias-chain 目录校验（`cd4d04a`）
- accreditation authority preflight（`cd4d04a`）

---

## 3. Operational wiring（`7fff842c` + 后续修复）

### 3.1 CLI dispatch

`formal-execute --module A-E1` → `run_a_e1_staged()`
A-E3/A-E2 → `run_module()`（不变）
CLI kwargs（run-id/artifact-root/cache-root/owner-id/max-fits）原样传递，有测试断言。

### 3.2 连续 failure 守卫

`run_a_e1_staged()` 增加 `_MAX_CONSECUTIVE_FAILURES = 8`，与 `run_module()` 一致：
- 7 次连续失败：不触发（测试通过）
- 8 次：抛 RuntimeError（测试通过）
- 中间一次成功：计数器清零（测试通过）

### 3.3 状态文档

`00-A-执行状态.md`、`03-A-实验计划.md` 已同步为 main、merge、APPROVE 口径。`03-A` 的 G3 行已清理为简洁摘要。

---

## 4. 启动路径（最终建议）

使用仓库外持久目录，避免大量训练产物混入 Git：

```
artifact root: D:\weibull-runs\study02\artifacts
cache root:    D:\weibull-runs\study02\cache
```

正式启动命令（运行前需确保路径存在）：
```
python Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py formal-execute ^
  --module A-E1 ^
  --run-id A-E1-formal-20260721-<HHMMSS> ^
  --artifact-root D:\weibull-runs\study02\artifacts ^
  --cache-root D:\weibull-runs\study02\cache
```

**真实耗时未知**（synthetic smoke 用 mock score_fit + fast 2-epoch warmup，不能外推 real 100-epoch formal 训练耗时）。首次正式 run 后以实际测量为准。

**断点恢复：** scheduler 检测已完成 receipt 自动跳过。中断后重跑相同命令即可续接。

---

## 5. 边界重申

- 不启动 A-E3/A-E2
- 不执行 accredit-authorize / test unseal
- 不进入 9d / G4
- 不修改冻结 matrix/plan/schema/selection rule/scientific metrics
- 不改 scheduler 输出合同

---

## 6. 当前状态

**A-E1 formal 未授权。等待用户明确启动指令。**

Codex Controller, 2026-07-21 R2

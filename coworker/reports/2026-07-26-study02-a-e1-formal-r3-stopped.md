# A-E1 Formal R3 停止报告

> 日期：2026-07-26
> Run ID：`A-E1-formal-r3-20260726`
> 状态：**blocked/aborted**（authority drift，不可续跑）
> 授权 commit：`39d630507128706286b103717eb2717ccdeb4666`
> 漂移后 HEAD：`db593d12`（无关 Study01 merge）

## 停止原因

Scheduler authority 要求 `code_commit == git HEAD`。Run 在 `39d63050` 上 materialize，
但无关的 Study01 merge commit `db593d12` 推入 main 后 HEAD 前移，导致
`_rebuild_authority` 检测到 authority drift 并 fail-closed。

Codex 独立确认：
- `39d63050..db593d12` 未修改任何 Study02 文件
- `scoped_code_sha256` 前后均为 `a64e10855fc2b1209f341152035794f6d88b0b5374159ff435c13e7d1d2b25a8`
- drift 仅由 `code_commit` 字段引起
- `test_access_count = 0`（test 始终 sealed）

## Run 产物（保留，不删除/覆盖/迁移）

```
C:\weibull-runs\study02\artifacts\A-E1\A-E1-formal-r3-20260726\
├── manifest.json          (authority 绑定 39d63050)
├── plan.jsonl             (349 fits)
├── scheduler_state.json   (3 succeeded, 346 pending)
├── events/                (genesis + 3 claim + 3 succeeded)
├── receipts/              (3 terminal receipts)
└── outputs/
    ├── G3-fit-0000/       (checkpoint.pt + fit_status.json + evidence.json)
    ├── G3-fit-0001/
    └── G3-fit-0002/
```

## 时间线

| 时间 | 事件 |
|------|------|
| 18:49 | 创建 artifact/cache 目录 |
| 18:49 | validate-config 通过 |
| 18:49 | materialize run（349 fits, plan_sha256=bbb93ab0...） |
| 18:50 | 执行 3 fits 测速（G3-fit-0000/0001/0002 succeeded, 0 failed） |
| 18:50 | status 确认：3 succeeded / 346 pending / test_access_count=0 |
| 18:51 | 启动完整 run → authority drift（HEAD 已变为 db593d12） |
| 18:51 | 停止，保留现场 |

## 后续

- 等待工作树收口形成新的 clean、pushed HEAD
- 新授权绑定最终 HEAD commit
- 新 run ID：`A-E1-formal-r4-<timestamp>`，从零 materialize
- 不复用 r3 的 3 个 fits
- 可创建绑定授权 commit 的稳定 formal 分支防止长运行期间漂移
- test 始终 sealed；不进入 A-E3/A-E2、approval、unseal、consumer

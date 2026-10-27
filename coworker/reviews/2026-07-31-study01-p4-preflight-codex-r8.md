# Study01 P4 preflight Codex review — R8

- Verdict: **REVISE**
- Previous review commit: `18bb8044`
- Executor tip reviewed: `9db3c6fada547e56208b85743892ef4f32169f9a`
- Local == remote: yes
- Formal authorization: **not granted**

P2真实 adapter 小夹具已经证明路径注入方案可行，P4-R10 不再存在所谓
技术阻塞。当前只需把同一方案完成到 E4c 和 `main()`，并关闭两个仍未
接入生产的门。

## Remaining items

| ID | Status | Required closure |
|---|---|---|
| P4-R2 | **PARTIAL** | `resume` 已捕获但 pre-seal 仍未重查。让 manifest 记录 start mode，并将 `tracks/seeds/resume/output_dir/approved_parent` 作为参数或 run-context 传入 pre-seal 后逐项比较。补一组参数化负向测试，不能只保留早先的 HEAD/script/dirty 三项。 |
| P4-R6 | **PARTIAL** | production 现在传入 24,000/15,000 预期数，P2 adapter 夹具通过。再补稳定 `sample_key_set_sha256`（对规范化排序键序列取哈希）；P2 两轨 receipt 必须无条件加入 allowlist，而不是 `if receipt_path.exists()` 后才封存。测试 SHA256SUMS 确实含两个 receipt。 |
| P4-R8 | **OPEN** | completed seal 已拒绝，但 root 层仍以 `rel.startswith("checkpoint_")` 接受任意 checkpoint 名；现有精确 checkpoint 集只应用于 track 子目录，而生产 checkpoint 实际写在 root。把精确枚举应用于真实 root 路径，拒绝 track 子目录 checkpoint。覆盖 manifest 前逐个读取现存 checkpoint 并用该 track 的 run context 调用 `verify_checkpoint_config`。同时核对 manifest 的 `input_sha256`、`row_count_contract`、output_dir 和 resume mode。 |
| P4-R10 | **OPEN** | 新增的是 P2 adapter 测试；E4c adapter 与 `main()` 仍未测试。复制同一 tmp-path/hash monkeypatch 方法生成最小 E4c CSV，真实调用 `_execute_track_extrap`。然后完成 `main()` 四轨测试：测试内临时授权和 Git receipt 是允许的；只 patch 昂贵训练/估计边界及缩小后的合同常量，不 patch authorization、lock、adapter dispatch、row/key gates、pre-seal、cleanup 或 seal。断言 lock 最终移除、四轨结果和两个 receipt 均在 SHA256SUMS。 |

## Independent verification

- `HEAD == origin/study01-p4-formal-compare == 9db3c6fa...`
- `git diff --check 18bb8044..9db3c6fa`: passed.
- P4 suite: `110 passed`; Study01 suite: `240 passed, 1 warning`.
- Formal constants remain sealed.
- Test source confirms real P2 adapter is called.
- Test source also confirms `_execute_track_extrap` and `main()` remain
  unexercised, while the old orchestration test still patches both adapters and
  the production gates.

## Boundary

Finish these four bounded items in the existing module/tests. Do not add another
framework, run real formal data, authorize, merge main, or change scientific
contracts. Stop only after one clean pushed report covering all items.

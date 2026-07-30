# Study01 P4 preflight Codex review — R7

- Verdict: **REVISE**
- Previous review commit: `20fc7980`
- Executor tip reviewed: `31aa26f90c6f9193567891923aeedaeef80859fe`
- Local == remote: yes
- Formal authorization: **not granted**

R6关闭了重复哈希冲突和嵌套 unknown-file 的两个具体探针，但生产接线与
生产适配器测试仍不完整。报告所称 P4-R10 “技术阻塞”不成立：测试夹具
可以在内存中把 `cfg.INPUT_SHA256` 绑定为临时文件的真实哈希，也可以在
测试进程内临时设置授权常量；这不会修改提交中的正式配置，更不会启动
正式实验。

## Exact remaining closure

| ID | Status | Required closure |
|---|---|---|
| P4-R2 | **PARTIAL** | pre-seal 已比较 tracks/seeds/approved parent，但未比较捕获的 `resume`，并且新增绑定仍无相应负向测试。补齐 `resume` 及 config/input/output/tracks/seeds/parent 的参数化负向测试。 |
| P4-R6 | **PARTIAL** | verifier 支持 `expected_key_count`，但 production `_execute_track_p2()` 调用没有传该参数，因此正式路径仍不执行预期样本数门。按 P2-PI=24,000、P2-NI=15,000 从冻结合同传入；receipt 增加稳定键集摘要，并测试 receipt 被 production adapter 写入且进入最终 seal。 |
| P4-R8 | **OPEN** | 当前仍允许任意根级 `checkpoint_*` 和 track 内任意 `checkpoint_*`，未验证 checkpoint 名称/context；也允许带 `SHA256SUMS` 的 completed 输出重新 resume。manifest validator 仍不核对 `input_sha256`、`row_count_contract`、output_dir/resume state。改成精确 allowlist：合法 checkpoint 名称由 track×learning method×fold×seed 枚举，所有现存 checkpoint 在覆盖 manifest 前调用 `verify_checkpoint_config`；任何 completed seal 拒绝 resume；manifest 明确记录并验证 output_dir、resume/input hashes/row contract。 |
| P4-R10 | **OPEN** | 新 commit 没有增加 adapter/main 测试。请给 production code 增加最小的输入路径注入点（默认仍是冻结正式路径），测试用 `tmp_path` 生成 P2/E4c 小 CSV，并把 `cfg.INPUT_SHA256` monkeypatch 为这些文件的真实 SHA256。真实调用 `_execute_track_p2`、`_execute_track_extrap`；只 patch `generate_sample`/模型训练/方法估计等昂贵边界。随后测试 `main()`：在测试进程内 monkeypatch `P4_FORMAL_AUTHORIZED=True`、approved parent、formal output path 和 Git receipts，保留真实参数门、lock、四轨分发、row/key gates、pre-seal、checkpoint cleanup、result files 与 recursive seal。正式源码常量必须仍为 False。 |

## Independent verification

- `HEAD == origin/study01-p4-formal-compare == 31aa26f9...`
- `git diff --check 20fc7980..31aa26f9`: passed.
- P4 suite: `107 passed`.
- Study01 suite: `237 passed, 1 warning`.
- Static production call: `_verify_p2_sample_hashes(df_track, ns)` leaves
  `expected_key_count=None`.
- Existing orchestration test still patches both P2/E4c adapters and all
  production verification gates named in R6.

## Boundary

This is a finite testability correction, not a request for another framework.
Use one small path resolver/dependency seam and compact fixtures. Do not read the
full 39k/7k artifacts in unit tests. Do not authorize/run P4, merge main, change
scientific contracts, or edit the manuscript. Stop clean and pushed with the
formal gate False.

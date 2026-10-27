# Study01 P4 preflight Codex review — R6

- Verdict: **REVISE**
- Previous review commit: `f480cde7`
- Executor tip reviewed: `ef89e6a43439c9e6f48feb4162335bcc46c4656a`
- Local == remote: yes
- Worktree before review: clean
- Formal authorization: **not granted**

R5新增了 sealed P2 receipt、manifest lineage 和更多授权绑定，方向正确；
但执行报告把上轮明确的阻断项自行降成了“acknowledged, not blocking”。
阻断等级只能由 reviewer 改变。以下可复现缺口仍需关闭。

## Remaining blockers

| ID | Status | Required closure |
|---|---|---|
| P4-R2 | **PARTIAL** | `auth_hashes` 已捕获 output/tracks/seeds/resume/approved parent，但 pre-seal 仅新增 output_dir 比较，仍未重查 tracks、seeds、resume 与 approved parent；相应负向测试也没有增加。将这些绑定全部机械比较，并为 config、每类输入、output、tracks、seeds、resume、approved parent 各提供参数化负向覆盖。最小授权子提交仍须在下一阶段单独审查，不能由当前实现自证。 |
| P4-R6 | **OPEN** | 缺失/短哈希现在会拒绝，receipt 也进入 seal；但重复键遇到第二行时立即 `continue`，不再比较同键哈希是否一致。独立探针以同一键的 `a…a`/`b…b` 两个哈希得到 `status=all_verified`。此外，若整个 `sample_sha256` 列不存在，`_execute_track_p2()` 会完全跳过哈希门并继续。必须强制列存在、逐行哈希格式合法、同键所有行哈希一致、验证键数等于该 track 的预期物理样本数；receipt 记录 expected/observed/verified、源文件 SHA、键集摘要和 namespace，并由 seal 覆盖。 |
| P4-R8 | **OPEN** | unknown-file 门只检查顶层：任意文件放在合法 track 子目录即被接受；独立探针证明 `param_interp/unknown.bin` 可通过。任意以 `checkpoint_` 开头的根文件也可通过，且会在终点被删除而不一定被读取/验证。validator 仍未核对 manifest 的冻结 input SHA、output_dir、row contract、resume state，也未在覆盖 manifest 前逐个验证现存 checkpoint。冻结并实现精确 fresh/partial/completed 状态：completed seal 必须拒绝 resume；partial 只允许可枚举的精确文件名/目录和原子临时规则；每个 checkpoint 在 manifest 更新前验证名称、schema、track/model/fold/seed 与 run context；任何层级未知文件均拒绝。 |
| P4-R10 | **OPEN** | R5没有修改此项。测试仍 patch 掉 `_execute_track_p2`、`_execute_track_extrap`、`verify_pre_seal_state`、精确 row-count 门和 sample-key 门，因此没有验证两个输入适配器，也没有验证声称的 production gates。补两个仓库外小型文件夹具，真实进入 P2/E4c adapter；只 patch 昂贵训练/估计边界。再从 `main()`（测试中临时注入合法授权上下文）进入四轨闭环，保留真实 authorization binding、lock、row counts、key alignment、pre-seal、checkpoint cleanup、results 和 recursive seal。测试规模可缩小合同值，但 production verifier 本身不得被 patch。 |

## Independent verification

- `HEAD == origin/study01-p4-formal-compare == ef89e6a4...`
- `git diff --check f480cde7..ef89e6a4`: passed.
- P4 suite: `103 passed`.
- Study01 suite: `233 passed, 1 warning`.
- `P4_FORMAL_AUTHORIZED=False`; formal output absent.
- Duplicate-hash probe: conflicting duplicate accepted as `all_verified`.
- Nested-file resume probe: `param_interp/unknown.bin` accepted.

## Scope and stop condition

Revise only the four findings in P4 code/tests/report and minimum truthful status.
Do not authorize or run P4, merge main, change scientific contracts, or edit the
manuscript. A future report must not relabel an explicit reviewer blocker as
non-blocking; either provide the required evidence or explain a genuine technical
blocker.

Stop clean and pushed with `P4_FORMAL_AUTHORIZED=False`, then send one complete
finding-to-commit-to-test report.

# Study01 P4 preflight Codex review — R5

- Verdict: **REVISE**
- Previous review commit: `cb151826`
- Executor tip reviewed: `2f40f33ac6aac26b995dda698f7accf5609c3ffb`
- Local == remote: yes
- Worktree before review: clean
- Formal authorization: **not granted**

R4修复了 Windows 递归封存路径、开始/结束 HEAD 检查，并把 P2
哈希循环从前 100 个扩大到全部带有效哈希的键。专项 97 项和 Study01
全量 227 项测试均通过。但 R4 明确要求的四个闭环仍未全部实现，当前
tip 不能作为 P4 正式授权父提交。

## Finding closure

| ID | Status | Independent finding |
|---|---|---|
| P4-R2 | **PARTIAL** | `verify_pre_seal_state()` 现在重查 HEAD、dirty、脚本、配置和 5 个输入文件，这是实质进展；但 `auth_hashes` 仍只含 script/config/start_head，未封存并重查授权参数（output_dir、tracks、seeds、resume）或批准父提交，新增负向测试也只覆盖 HEAD/script/dirty，未覆盖 config、5 个输入、输出路径及参数漂移。独立授权阶段仍必须限制为“已批准 tip 的最小授权子提交”，且该子提交需另行审查。 |
| P4-R6 | **OPEN** | `_verify_p2_sample_hashes()` 返回 receipt，但 `_execute_track_p2()` 丢弃返回值，manifest/最终 seal 中没有收据。更严重的是，空值、`nan` 或非 64 位哈希被 `continue` 静默跳过，故函数可在只验证部分样本后返回 `status=all_verified`。独立探针以 2 个键（1 个有效哈希、1 个空哈希）得到 `verified_samples=1,total_unique_keys=1,status=all_verified`。必须要求每个预期 P2 唯一样本键恰有一个有效且一致的 SHA256，并把每轨 count、键集摘要/源文件哈希、namespace 和验证状态写入 manifest 或单独 sealed receipt。 |
| P4-R8 | **OPEN** | `_validate_resume_manifest()` 只核对 6 个字段，不验证 output_dir、批准父提交、冻结输入哈希、row contract、checkpoint 文件集合/上下文或允许的 partial-state allowlist；随后 `_run_formal()` 仍直接覆盖旧 manifest，没有保留其 hash/lineage。独立探针证明：合法 6 字段 manifest 旁放置任意 `unknown.bin` 仍被接受。必须冻结 fresh/partial/completed 三类允许状态，恢复前拒绝未知/最终产物/临时文件，逐个验证 checkpoint 上下文，并在原子更新 manifest 时保留 previous_manifest_sha256/resume lineage。 |
| P4-R10 | **OPEN** | 新测试确实调用了真实 `_run_formal()` 和真实 `seal_recursive()`，但它 monkeypatch 掉 `_execute_track_p2`、`_execute_track_extrap`、`verify_pre_seal_state`、精确行数验证和样本键验证。因此两个独立输入适配器、P2 哈希门、pre-seal 门和正式 row contract 仍未进入生产路径测试；测试也直接调用内部 `_run_formal()`，未经过 `main()` 的授权/锁/参数门。报告已承认两个适配器无独立 fixture。需补仓库外最小 P2/E4c 文件夹具，真实调用两个适配器；再由 `main()` 或等价授权入口跑四轨最小闭环，只 patch 昂贵训练/估计计算，不 patch 掉待验证的门、行数、键对齐、checkpoint 清理与 seal。 |

## Independent verification

- `HEAD == origin/study01-p4-formal-compare == 2f40f33a...`
- `git diff --check cb151826..2f40f33a`: passed.
- P4 suite: `97 passed`.
- Study01 suite: `227 passed, 1 warning`.
- `P4_FORMAL_AUTHORIZED=False`; `APPROVED_PARENT_COMMIT=None`.
- Formal output directory does not exist.
- Partial-hash probe: accepted 1/2 keys and reported `all_verified`.
- Resume probe: accepted an unknown file beside the manifest.

## Allowed R5 revision scope

Only close P4-R2/R6/R8/R10 in P4 code, tests, report and minimum truthful status
text. Do not authorize or run P4, merge main, alter methods/metrics/seeds/sample
spaces/failure contracts, tune from outputs, or edit the manuscript.

Required final report:

```text
finding ID -> fixing commit -> changed files -> exact production-path and negative evidence
```

Stop clean and pushed with `P4_FORMAL_AUTHORIZED=False`. After a future
`APPROVE`, authorization must still be a separate minimal child commit bound to
the exact approved parent and independently checked before any formal launch.

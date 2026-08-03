# Study01 P4 preflight Codex review — R9

- Verdict: **REVISE**
- Previous review commit: `c11b98ec`
- Executor tip reviewed: `75660e16e5d59c42ac9b793184bd759c7e557d26`
- Local == remote: yes
- Formal authorization: **not granted**

P2/E4c 两个真实 adapter 小夹具均已建立，P4-R6 可视为关闭。现在只剩
授权/恢复的机械完整性和已多轮要求的 `main()` 最小闭环；请一次完成后
再发报告，不再分轮递交“下一步可以做”的部分结果。

## Final pre-authorization closure

| ID | Status | Required closure |
|---|---|---|
| P4-R2 | **PARTIAL** | 代码已比较 9 项绑定。补一个参数化 pre-seal 测试覆盖 config、五个输入中的任一项、output_dir、tracks、seeds、resume、approved parent；测试应证明每类漂移 fail closed。 |
| P4-R8 | **OPEN** | root checkpoint 名称现在精确，但 manifest 被覆盖前仍未验证 checkpoint 内容/context。对每个现存 checkpoint 在 `_validate_resume_manifest` 内构造对应 track run context 并调用 `verify_checkpoint_config`。同时让 manifest 明确记录 `output_dir` 与 `resume_mode`，恢复时核对它们，以及现有 `input_sha256`、`row_count_contract` 与冻结配置完全一致。上述验证全部发生在计算/覆盖 manifest 之前；为 checkpoint context、input hash、row contract、output path、resume mode 各加负向测试。 |
| P4-R10 | **OPEN** | 完成报告已承认尚缺 `main()`。按既定方案在 `tmp_path` 内完成：monkeypatch 内存授权常量、approved parent、Git receipts、formal path、1 fold×1 seed 小合同和昂贵计算边界；保留真实 `main → authorization → lock → _run_formal → 四个真实 adapters → row/key gates → pre-seal → checkpoint cleanup → result/seal → lock removal`。四轨输入均用临时真实文件及其真实 SHA256。断言六方法、四轨、两份 P2 receipt 和全部结果进入 SHA256SUMS，且 `run.lock` 最终不存在。 |

## Independent verification

- `HEAD == origin/study01-p4-formal-compare == 75660e16...`
- `git diff --check c11b98ec..75660e16`: passed.
- P4 suite: `111 passed`; Study01 suite: `241 passed, 1 warning`.
- Formal constants remain False/None; formal output absent.
- `_validate_resume_manifest` only validates checkpoint names; it does not read
  checkpoint content before manifest replacement and does not compare manifest
  input hashes/row contract/output/resume.
- No test calls `main()`.

## Boundary

Keep the existing single module and fixtures; no new framework or real formal
run. Do not authorize, merge main, change scientific contracts, or edit the
manuscript. Stop clean and pushed only after all three rows above are complete.

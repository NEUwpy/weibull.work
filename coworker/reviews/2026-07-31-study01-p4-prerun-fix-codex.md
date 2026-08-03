# Study01 P4 pre-run fix — Codex review

- Verdict: **REVISE**
- Reviewed tip: `336c52f74bce5bbd5368190064000f6a69e2f207`
- Scope: `818b4721..336c52f7`

## Substantive review

The implementation is approved in substance.

- The pre-seal check previously treated the runner's own untracked formal
  output as an external worktree change. The new exclusion is limited to the
  exact output directory; the start gate remains globally clean and changes
  outside the output directory are still detected.
- The P4 CSV LFS rule is justified by the expected file sizes and was
  independently confirmed for both root and per-track CSV paths; JSON and
  manifest files remain outside LFS.
- Independent checks passed: `124` P4 tests, `254` Study01 tests with one known
  warning, `git diff --check`, and the actual CJK Git-path decoding behavior.
- No scientific contract, method, seed, sample, metric or failure rule changed.

No additional implementation hardening or tests are requested.

## Required closure

The durable executor report is currently untracked, so the claimed clean
worktree is false and the existing formal authorization gate would reject the
run. Also distinguish these two facts in that report:

- actual parent of `336c52f7`: `818b4721691444b79a6309c3bcbd84086e31ada6`;
- previously approved P4 implementation tip: `2210025c1275c966f29136d864f28ba8d97d5313`.

Commit only the corrected executor report, push, and confirm clean
`local == remote`. No code changes and no full test rerun are required. Stop
and report the exact new tip for approval before creating the authorization
commit.

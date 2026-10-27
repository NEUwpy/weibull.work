# Study01 P4 preflight Codex review — R10

- Verdict: **REVISE**
- Previous review commit: `b9b3161d`
- Executor tip reviewed: `c7a2676d16ed98dee47f4f5e4afc088e32f3a5e3`
- Local == remote: yes
- Formal authorization: **not granted**

四轨 `main()` 小闭环已经能够运行，resume manifest/checkpoint 的主体也已
闭合。当前只剩三处很小但直接影响“生产门是否真的经过测试”的问题。

## Final corrections

1. **P4-R10 — 不得绕过 pre-seal。**  
   `test_main_four_track_closed_loop` 的 docstring 声称不 patch pre-seal，
   但第 1976–1979 行实际上把 `verify_pre_seal_state` 替换成空函数。当前
   夹具已经提供 clean/head/script/config/五输入/output/tracks/seeds/parent/
   resume 所需上下文，删除该 monkeypatch，让真实 pre-seal 在 `main()`
   闭环中通过。

2. **P4-R2 — 补齐尚缺的负向覆盖。**  
   新增 config SHA 漂移、五个冻结输入逐一漂移、resume/manifest mode
   漂移测试。保留现有 output/tracks/seeds/parent 测试即可。

3. **P4-R8 — track 文件必须位于直接子目录。**  
   当前 validator 只看 `top_dir` 与 `f.name`，所以
   `param_interp/arbitrary/results.json` 仍会作为合法文件通过。要求合法
   track 产物的 `f.parent == output_path / track`；增加嵌套同名文件拒绝
   测试。checkpoint 仍只允许 root 精确枚举名。

## Independent verification

- `HEAD == origin/study01-p4-formal-compare == c7a2676d...`
- `git diff --check b9b3161d..c7a2676d`: passed.
- P4 suite: `119 passed`; Study01 suite: `249 passed, 1 warning`.
- Formal source constants remain sealed; no formal output exists.
- Main test calls real `main()` and real adapters/row/key/seal, but currently
  replaces the complete pre-seal gate with `pass`.

## Boundary and stop

Only make these three corrections and truthful report updates. Do not authorize,
run formal data, merge main, change contracts, or add infrastructure. After all
three pass, send one clean pushed report for final integrity review.

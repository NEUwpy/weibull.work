# Study01 P1c：E4d fail-closed / provenance gate 执行报告

> 日期：2026-07-22
> 分支：`study01xu`
> 任务边界：只实现正式 E4d 运行前的数据合同与溯源门；不实现 5 folds × 3 seeds，不修改模型、基线或正式实验产物。

## 1. 完成内容

1. 在 `run_E4_formal_validation.py` 增加 `study01-e4d-preflight-v1` 合同：
   - main-grid 正式权威输入固定为 `shared_data/chunks/chunk_####_mdm.csv`，按 `generate_mc_data.py` 冻结 work-unit 顺序发现并拼接 45 个分片；缺失、额外、重复 identity 或 combo 顺序错配均终止；
   - 被 `.gitignore` 排除且当前不存在的 `mc_scan_raw.csv` 不再是正式运行前置条件，只保留未启用的兼容路径声明；
   - main-grid、boundary、offgrid 的完整 `sample key + delta` 必须唯一；
   - 每个样本必须精确覆盖冻结的 26 点 `DELTA_GRID`；
   - 每个冻结 combo 必须覆盖合同规定的全部 `repeat_id`；
   - main-grid combo 必须精确等于 `config.py` 的冻结主网格；
   - boundary/offgrid 复用 P1b 的 combo 元数据与确定性样本重建合同；
   - main-grid 训练 combo、boundary、offgrid 三组不得重叠；provenance 明确声明只有 main-grid 提供训练标签，E4 truth 仅用于评价。
2. gate 在任何正式 track 输出前运行。合同失败抛出 `PreflightError` 并以非零状态退出；`PreflightError` 不会被 E4d 的通用异常处理降级成 `skipped_error`。
3. 消除输入“先按路径解析、后重新按路径哈希”的 TOCTOU：每个 CSV/JSON 只读取一批 bytes，用同一批 bytes 同时解析并计算 SHA256；loader 返回带私有 sentinel、绑定具体 parsed object identity 的 opaque capability，45 chunks loader 同样绑定合并后的 main DataFrame。validator 只消费这些 capability，普通 records、伪 SHA256 或绑定另一对象的 capability 均不能生成 gate。manifest 中明确分开：
   - `generation_time.input_files.main_grid_chunks`：45 个有序 chunk 的逐文件 SHA256、大小、行数、identity 与冻结 unit；
   - 其余 input records：MC manifest、boundary、offgrid 的同 bytes SHA256；
   - `generation_time.code_files`：当前 E4 analysis、E4 MC generation、main MC generation、Study01 config、Study01 utils、共享 sample、MDM 实现。
4. validator 返回带模块私有 identity sentinel 的 `_ValidatedE4dGate` capability；writer 拒绝普通 dict。gate 构造时用 `git -C PROJECT_ROOT` 严格冻结当前 checkout 的 short hash + dirty 状态，失败/unknown 直接终止；provenance 只能经 gate 的 deep-copy/JSON-safe export 或 `attach_e4d_gate_to_manifest()` 注入 manifest，调用者不能覆盖 generation commit，main manifest 与 gate commit 必须一致。旧 `utils.get_git_info()` 不再用于 E4d，但 `utils.py` 本身纳入 code SHA256。
5. `E4d_selector_extrapolation.csv` 使用同目录 `mkstemp` 唯一临时文件原子写入；CSV 写入或 `os.replace` 失败均在 `finally` 清理临时文件，正式路径保持不存在或保留原内容。
6. 修复 `python/tests/test_study01_e4_failclosed.py` 的 `D:\weibull` 硬编码，测试路径现在从测试文件所在 checkout 相对解析；测试预导入后同时恢复原 `sys.path` 与相关 `sys.modules`，后续测试只引用保存的模块对象。production 对 config/utils/sample 使用唯一文件路径加载，不依赖或污染 basename module。

## 2. generation-time 与 sealed provenance 边界

- generation-time provenance 在正式输出前的 gate 构造阶段记录真实输入/代码文件 SHA256，并冻结当次 `git_commit`/dirty 状态。
- 生成中的脚本不能预知“包含正式 artifacts 的后续提交”哈希，因此 `sealed_release.git_commit` 保持 `null`，状态为 `pending_artifact_commit`。
- sealed commit 必须由后续正式执行/独立复核报告在 artifacts 提交完成后记录；不得用 generation commit 冒充 sealed commit。

## 3. 验证证据

执行：

```powershell
python -m py_compile "Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py" python/tests/test_study01_e4_failclosed.py
python -m pytest python/tests/test_study01_e4_failclosed.py -q
python -m pytest python/tests/test_study01_e4_failclosed.py python/tests/test_study01_e4_repeat_contract.py python/tests/test_study01_e4_cost_report.py -q
python -m pytest python/tests/test_study01_e4_repeat_contract.py python/tests/test_study01_e4_cost_report.py python/tests/test_study01_e4_failclosed.py -q
python -m pytest python/tests/test_study01_e4_cost_report.py python/tests/test_study01_e4_failclosed.py python/tests/test_study01_e4_repeat_contract.py -q
# 只读加载真实 45 chunks + manifest + boundary + offgrid，调用完整 gate；不调用模型、不写 artifact
git diff --check
```

结果：

- `py_compile`：通过；
- P1c 独立测试：`37 passed in 15.01s`；
- P1a/P1b/P1c 三种收集顺序：均为 `54 passed`，分别用时 `17.53s`、`16.23s`、`17.31s`；
- 真实输入完整只读 gate：`REAL_GATE_OK git=4888050-dirty`；45 chunks、main-grid `1,170,000` 行/`45,000` 样本、boundary `260,000` 行/`10,000` 样本、offgrid `182,000` 行/`7,000` 样本，完整风险键、repeats、26 点 delta、P1b 元数据/样本重建、opaque input binding、冻结 git 与 manifest attach 合同全部通过；
- `git diff --check`：通过（Git 仅报告工作区 CRLF 将按配置规范化为 LF 的提示，无空白错误）。

新增测试覆盖：真实/合成 45-chunk loader、chunk identity 缺失/重复、同 bytes 解析与哈希绑定、input/code 哈希分类、plain/伪 hash records 拒绝、另一 DataFrame capability 对象错配拒绝、严格 current-checkout git 格式与命令失败拒绝、重复风险键、缺失/越界 delta、整段 repeat 缺失、P1b 元数据不一致、训练/评价 combo 重叠、opaque gate/plain-dict forgery、冻结 commit、provenance JSON roundtrip 与 manifest deep-copy attach、production/test `sys.path`/`sys.modules` 恢复、basename config/utils collision、未通过 gate 时正式输出路径不得生成、唯一临时文件在 CSV 写入与 replace 故障注入后的清理/原正式文件保持。

## 4. 未执行事项

- 未运行正式 E4d 大实验；
- 未写入或修改 `artifacts/formal/` 正式结果；
- 未修改 E4d 模型、fold/seed、target scaler、失败惩罚或参考基线；
- 未提交 Git commit，留给主任务审查后按“一小任务一提交”执行。

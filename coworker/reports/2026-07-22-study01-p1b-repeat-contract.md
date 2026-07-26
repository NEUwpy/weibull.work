# Study01 P1b Repeat Contract 执行报告

## 目标

修复 E4 边界/离网格特征表把 `R_MAIN=1000` 当作实际重复数的问题，使样本特征严格由输入风险/损失表的真实 `(combo_id, repeat_id)` 键驱动。

## 变更文件

- `Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py`
- `python/tests/test_study01_e4_repeat_contract.py`
- `coworker/reports/2026-07-22-study01-p1b-repeat-contract.md`

## 实现结果

- `build_feature_table_for_combos()` 现在显式接收风险/损失表，每个实际唯一样本键只生成一行特征。
- 不再使用 `R_MAIN` 扩展边界/离网格重复数，因此 500、1000 及非连续 `repeat_id` 均不会产生伪样本。
- 在样本生成前拒绝缺失/空键、重复风险键、样本元数据冲突、combo 集合不一致和冻结 combo 元数据不一致。
- E4d 调用链现在将已加载的 boundary/offgrid 表传入特征构造函数。

## 边界

- 未修改 P1a 的 `cost_report.csv` 合并语义。
- 未实现 P1c 或改造 E4d 训练协议。
- 未运行正式大实验，未改写正式产物。

## 验证

- `python -m pytest python/tests/test_study01_e4_repeat_contract.py -q`：`7 passed in 1.91s`。
- `python -m pytest python/tests/test_study01_e4_cost_report.py python/tests/test_study01_e4_repeat_contract.py -q`：P1a + P1b 新增回归测试 `17 passed in 1.87s`。
- `python -m pytest python/tests/test_study01_e4_failclosed.py -q`：旧测试单独运行为 `15 failed, 2 passed in 0.93s`。该旧文件硬编码 `PROJECT_ROOT = r"D:\weibull"`，在当前 `C:\Web\Weibull` 工作区导致 `ModuleNotFoundError`；这是 P1b 之前已存的独立运行问题，本任务未修改旧测试。
- 不把 cost/repeat 测试先动态加载模块后出现的联合 `34 passed` 视为独立回归证据；该结果受测试顺序与 `sys.path` 污染影响。
- `python -m py_compile Study/.../code/run_E4_formal_validation.py`：通过，无输出。
- `git diff --check`：通过，无 diff 空白错误；仅 Git 提示现有工作区换行符将在后续触碰时由 CRLF 转为 LF。
- 使用实际正式输入做只读契约冒烟（替换样本生成器，不训练、不改写产物）：
  - boundary：`260000` 风险行 → `10000` 实际样本键 → `10000` 特征行，最大 `repeat_id=499`。
  - offgrid：`182000` 风险行 → `7000` 实际样本键 → `7000` 特征行，最大 `repeat_id=499`。

## 偏离、跳过项与阻塞

- 偏离：无。
- 跳过：正式 E4 实验（超出 P1b 边界）。
- 阻塞：无。

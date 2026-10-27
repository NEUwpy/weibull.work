# RFC: 蒙特卡洛实验流水线深模块

> 候选 1 — 统一实验边界，让研究脚本和 API 复用同一条后端流水线

## 1. 现状诊断

### 1.1 已有的良好基础

`python/studies/common/` 已经是一个结构合理的共享层：

| 文件 | 职责 | 状态 |
|------|------|------|
| `sample.py` | SHA256 确定性种子 + 三参数威布尔抽样 | ✅ 完成 |
| `runner.py` | 通过 registry 统一调用方法，标准化返回 | ✅ 完成 |
| `experiment.py` | param_grid × n_values × repeats 调度，输出 CSV + JSON | ✅ 完成 |
| `simulation.py` | API 导向的单方法/批量模拟服务 | ✅ 完成 |
| `metrics.py` | 标准指标 (Bias/SD/RMSE/MAE) + S2R diagnostics | ✅ 完成 |

### 1.2 三处断裂

**断裂 A：旧脚本 `studies/mdm/simulate.py` 绕过共享层**
- 自己实现 `generate_weibull_sample()`（用 `np.random.seed`，种子策略与 common 不同）
- 自己调用 `MDM(sample.tolist())` 而非 `run_method()`
- 输出格式（chunks 分片 + index.json）与 common 的 `results.csv + summary.json` 不兼容

**断裂 B：`main.py` API 端点内嵌蒙特卡洛逻辑**
- `monte_carlo_simulate` 端点直接调用 `simulate_method()` + `aggregate_simulation_rows()`
- `batch_simulation` 端点直接调用 `iter_batch_rows()` + 手写 CSV
- 两套 API 用的字段名不同（`est_beta` vs `beta_hat`），与 `experiment.py` 的标准字段也不一致

**断裂 C：无实验产物溯源**
- 没有 `manifest.json`，无法追溯"这份数据是用什么代码/参数/种子生成的"
- MDM 的 `last_solution_info`（求解策略、括弧、迭代次数）不进入行级诊断
- 旧数据和新数据混在一起，无法区分

## 2. 改造目标

```
研究脚本 ──┐
            ├──→ experiment.run_experiment() ──→ results.csv + summary.json + manifest.json
API 端点 ──┘         ↑
                     │
              sample.py + runner.py + metrics.py（不变）
```

**交付标准：**
1. `run_experiment()` 输出三文件：`results.csv`、`summary.json`、`manifest.json`
2. `manifest.json` 记录：方法列表、offset、seed namespace、参数网格、代码版本、生成时间
3. MDM 行级 `extra` 字段包含 `last_solution_info`
4. API 端点 `monte_carlo_simulate` 委托给 `run_experiment()`（或其轻量包装）
5. 旧脚本 `simulate.py` 标记 deprecated，不删但不再作为主入口

## 3. 实现计划

### Phase 1：experiment.py 增强（核心）

**3.1 新增 `manifest.json` 输出**

在 `run_experiment()` 末尾生成：

```json
{
  "version": "1.0",
  "generated_at": "2026-06-13T10:00:00",
  "code_version": "v1.42",
  "methods": [
    {"method_id": "mdm", "variant": "mdm_o0.1", "kwargs": {"offset": 0.1}},
    {"method_id": "mle", "variant": "mle", "kwargs": {}}
  ],
  "param_grid": [[2.0, 100.0, 5.0]],
  "n_values": [10, 20, 30],
  "n_repeats": 100,
  "seed_namespace": null,
  "metrics": {
    "primary": ["bias", "sd", "rmse", "mae"],
    "diagnostics": ["mdape", "med_rel", "p95_abs"]
  },
  "total_rows": 900,
  "output_files": ["results.csv", "summary.json", "manifest.json"]
}
```

**3.2 MDM `last_solution_info` 进入行级诊断**

修改 `experiment.py` 内循环：当 `method_id == "mdm"` 时，从 `run_method()` 返回的 `extra` 中提取 `last_solution_info`，写入 CSV 的 `extra` 列。

当前 `runner.py` 已经通过 `getattr(instance, "last_solution_info", None)` 获取，但只在 `trace=True` 时通过 `trace_data` 返回。需要：
- `runner.py`：无论 `trace` 是否开启，都将 `last_solution_info` 放入 `result["extra"]["solution_info"]`
- `experiment.py`：无需改动，`extra` 已经序列化到 CSV

**3.3 `run_experiment()` 签名微调**

```python
def run_experiment(
    methods, param_grid, n_values, n_repeats, output_dir,
    R_levels=DEFAULT_STANDARD_R_LEVELS,
    diagnostic_R_levels=DEFAULT_R_LEVELS,
    seed_namespace: Optional[int] = None,  # 新增：传递给 generate_sample
    code_version: str = "unknown",          # 新增：写入 manifest
) -> Dict[str, Any]:
```

`generate_sample()` 调用时传递 `seed=seed_namespace`。

### Phase 2：runner.py 增强

**3.4 `last_solution_info` 无条件暴露**

```python
# runner.py run_method() 末尾，try 块内
solution_info = getattr(instance, "last_solution_info", None)
if solution_info is not None:
    if result["extra"] is None:
        result["extra"] = {}
    result["extra"]["solution_info"] = solution_info
```

### Phase 3：API 端点委托

**3.5 `monte_carlo_simulate` 端点改造**

当前端点调用 `simulate_method()` + `aggregate_simulation_rows()`，返回 `{rows, count, metrics, success}`。

改造方案：端点内部调用 `run_experiment()` 的单方法单参数组合版本，保持 API 响应格式不变。

具体：新增一个轻量函数 `run_single_mc()`（在 `experiment.py` 或 `simulation.py`），复用 `generate_sample + run_method + aggregate_standard_metrics` 三件套，但不写文件。

**3.6 不动 `batch_simulation` 端点**

`batch_simulation` 是前端 `UniversalStudyViewer` 用的 CSV 导出接口，字段格式 (`est_beta`, `bias_beta`) 与前端组件绑定，改动成本高且不属于"实验流水线"范畴。保持不动。

### Phase 4：旧脚本标记

**3.7 `simulate.py` 标记 deprecated**

文件头已有一段说明文字，追加明确的 deprecated 标记：

```python
# ⚠️ DEPRECATED: 本脚本已被 python/studies/common/experiment.py 取代。
# 新实验请使用 run_experiment()。本脚本仅用于复现旧数据。
```

## 4. 不做的事情

| 不做 | 原因 |
|------|------|
| 不改 MDM 算法 | 候选 2 范围，本轮只加钩子 |
| 不删 `simulate.py` | 旧数据复现需要 |
| 不改 `batch_simulation` API 字段 | 前端绑定，改动成本高 |
| 不拆 `mdm.py` 为多文件 | 用户明确要求单文件 |
| 不恢复 `mdm_case6.py` 等分支 | 审查红线 |

## 5. 验收标准

### 5.1 边界测试

```python
def test_experiment_produces_manifest():
    """run_experiment 输出 manifest.json 且包含必要字段"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=[("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=10,
            output_dir=tmpdir,
            code_version="test",
        )
        manifest_path = os.path.join(tmpdir, "manifest.json")
        assert os.path.exists(manifest_path)
        with open(manifest_path) as f:
            m = json.load(f)
        assert "methods" in m
        assert "param_grid" in m
        assert "generated_at" in m
        assert m["code_version"] == "test"
```

### 5.2 MDM solution_info 钩子

```python
def test_mdm_solution_info_in_extra():
    """MDM 行的 extra 列包含 solution_info"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=[("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=5,
            output_dir=tmpdir,
        )
        csv_path = os.path.join(tmpdir, "results.csv")
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["status"] == "success":
                    extra = json.loads(row["extra"])
                    assert "solution_info" in extra
                    assert "solution_strategy" in extra["solution_info"]
```

### 5.3 MDM 小网格 valid rate

```python
def test_mdm_small_grid_valid_rate():
    """MDM 在标准小网格上 valid rate = 100%"""
    with tempfile.TemporaryDirectory() as tmpdir:
        summary = run_experiment(
            methods=[("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0), (3.0, 100.0, 0.0)],
            n_values=[20, 30],
            n_repeats=50,
            output_dir=tmpdir,
        )
        for key, group in summary.items():
            assert group["valid_rate"] == 1.0, f"{key}: valid_rate={group['valid_rate']}"
```

### 5.4 CI 检查

```bash
uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas \
  python -m pytest python/tests -q
npx tsc --noEmit
git diff --check
```

## 6. 文件变更范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `python/studies/common/experiment.py` | 修改 | 新增 manifest.json 输出、seed_namespace 参数 |
| `python/studies/common/runner.py` | 修改 | 无条件暴露 last_solution_info |
| `python/studies/common/simulation.py` | 可能修改 | 如果 API 端点需要轻量包装函数 |
| `python/tests/test_experiment.py` | 修改 | 新增 manifest + solution_info 测试 |
| `python/studies/mdm/simulate.py` | 修改 | 追加 deprecated 标记 |
| `python/main.py` | 不改或微调 | monte_carlo_simulate 端点可选委托 |

**不涉及：** `mdm.py`、前端代码、`batch_simulation` 端点、旧数据文件。

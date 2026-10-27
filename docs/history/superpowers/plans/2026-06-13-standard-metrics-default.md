# Standard Metrics Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the seventh-round common metrics (`Bias`, `SD`, `RMSE`, `MAE`, relative `Bias/RMSE` where valid) the default evaluation output, while keeping S2R median/tail metrics as diagnostics.

**Architecture:** Keep the existing shared backend pipeline. Add standard metric aggregation beside the existing S2R functions in `python/studies/common/metrics.py`, then make `python/studies/common/experiment.py` and `/monte_carlo_simulate` expose the standard summary by default. Update the help page and handoff/status docs so future work treats S2R as a diagnostic layer, not the only/main metric system.

**Tech Stack:** Python 3, NumPy, FastAPI, pytest, Next.js 14, TypeScript, Tailwind CSS.

---

## Execution Context

- Read first: `AGENTS.md`, `README.md`, `02-规则.md`, `docs/AI协作协议.md`.
- Do not read `_archive/`.
- Do not delete old per-method simulation scripts in this plan.
- Do not recalculate historical study data in this plan.
- Do not hard-code research result tables into TS/JS files.
- Keep `python/main.py` as an API layer. Shared metric and simulation logic belongs under `python/studies/common/`.

## File Map

- Modify: `python/studies/common/metrics.py`
  - Add standard metric functions.
  - Keep existing S2R functions for diagnostics.
- Modify: `python/studies/common/experiment.py`
  - Use standard metrics in `summary.json`.
  - Keep diagnostic S2R nested under `diagnostics`.
  - Add raw error columns to CSV.
- Modify: `python/studies/common/simulation.py`
  - Preserve existing row shape for legacy consumers.
  - Add convergence/status fields only to `simulate_method()` rows, not `iter_batch_rows()` CSV rows.
  - Add helper to aggregate Monte Carlo rows.
- Modify: `python/main.py`
  - Return `metrics` from `/monte_carlo_simulate`.
  - Keep `rows`, `count`, and `success` unchanged.
- Modify: `python/tests/test_metrics.py`
  - Replace "S2R only" assertions with "standard default + S2R diagnostics" assertions.
- Modify: `python/tests/test_experiment.py`
  - Assert standard summary keys and raw CSV error columns.
- Modify: `python/tests/test_simulation.py`
  - Assert API simulation rows include enough state for aggregation.
  - Assert batch CSV shape remains unchanged.
- Modify: `src/lib/metrics.ts`
  - Add TypeScript standard metric helpers.
  - Keep existing S2R helpers.
- Modify: `src/app/help/metrics/page.tsx`
  - Show common metrics as default.
  - Move S2R into diagnostic/risk section.
- Modify: `docs/S2R统一评价指标体系进程控制.md`
  - Mark S2R as historical mainline, now diagnostic.
- Modify: `docs/提示词_新窗口接手.md`
  - Update handoff text so the next agent does not continue "S2R only".

## Task 1: Backend Metric Tests First

**Files:**
- Modify: `python/tests/test_metrics.py`
- Test: `python/tests/test_metrics.py`

- [ ] **Step 1: Replace the module docstring**

Use this docstring at the top of `python/tests/test_metrics.py`:

```python
"""
评价指标模块测试

当前权威口径：
- 第七轮常用指标为默认主口径：Bias、SD、RMSE、MAE。
- beta/eta 可附相对 Bias、相对 RMSE；gamma 不输出相对指标。
- 工程寿命分位点 x_R 输出 Bias、SD、RMSE、MAE 与相对 Bias/RMSE。
- S2R 的 MdAPE、MedRel、IQR、P95/P99、Valid Rate 保留为 diagnostics。
"""
```

- [ ] **Step 2: Update imports**

Make the import block include these names:

```python
from studies.common.metrics import (
    DEFAULT_R_LEVELS,
    DEFAULT_STANDARD_R_LEVELS,
    aggregate_param_metrics,
    aggregate_standard_metrics,
    check_status,
    param_relative_errors,
    quantile_est,
    quantile_relative_error,
    quantile_true,
    summarize_relative_errors,
    summarize_standard_errors,
)
```

- [ ] **Step 3: Add failing tests for standard summaries**

Add this test class after `TestDistributionSummary`:

```python
class TestStandardSummary:
    def test_standard_summary_reports_bias_sd_rmse_mae(self):
        summary = summarize_standard_errors([10.0, -5.0, 0.0])

        assert summary["n"] == 3
        assert summary["bias"] == pytest.approx(5.0 / 3.0)
        assert summary["sd"] == pytest.approx(7.637626, rel=1e-6)
        assert summary["rmse"] == pytest.approx(math.sqrt(125.0 / 3.0))
        assert summary["mae"] == pytest.approx(5.0)
        assert summary["mse"] == pytest.approx(125.0 / 3.0)

    def test_standard_summary_ignores_nonfinite_values(self):
        summary = summarize_standard_errors([float("nan"), -2.0, 2.0, float("inf")])

        assert summary["n"] == 2
        assert summary["bias"] == pytest.approx(0.0)
        assert summary["rmse"] == pytest.approx(2.0)

    def test_empty_standard_summary_uses_none_values(self):
        summary = summarize_standard_errors([float("nan")])

        assert summary == {
            "n": 0,
            "bias": None,
            "sd": None,
            "mse": None,
            "rmse": None,
            "mae": None,
        }
```

- [ ] **Step 4: Add failing tests for standard aggregation**

Add these tests inside `TestAggregate`:

```python
    def test_standard_metrics_are_default_output(self):
        agg = aggregate_standard_metrics([
            self._make_result(2.2, 110.0, 12.0),
            self._make_result(1.8, 90.0, 8.0),
            self._make_result(None, None, None),
        ])

        assert agg["n_total"] == 3
        assert agg["n_valid"] == 2
        assert agg["n_failure"] == 1
        assert agg["valid_rate"] == pytest.approx(2.0 / 3.0)

        beta_abs = agg["param_standard"]["beta"]["absolute"]
        assert beta_abs["bias"] == pytest.approx(0.0)
        assert beta_abs["sd"] == pytest.approx(0.2828427, rel=1e-6)
        assert beta_abs["rmse"] == pytest.approx(0.2)
        assert beta_abs["mae"] == pytest.approx(0.2)

        beta_rel = agg["param_standard"]["beta"]["relative"]
        assert beta_rel["bias"] == pytest.approx(0.0)
        assert beta_rel["rmse"] == pytest.approx(0.1)

        assert "relative" not in agg["param_standard"]["gamma"]
        assert "diagnostics" in agg
        assert "param_distribution" in agg["diagnostics"]

    def test_standard_quantile_metrics_include_x095_and_x099_by_default(self):
        agg = aggregate_standard_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.2, 110.0, 12.0),
        ])

        assert DEFAULT_STANDARD_R_LEVELS == (0.95, 0.99)
        assert set(agg["quantile_standard"]) == {0.95, 0.99}

        for R in DEFAULT_STANDARD_R_LEVELS:
            item = agg["quantile_standard"][R]
            assert set(item) == {"absolute", "relative"}
            assert "rmse" in item["absolute"]
            assert "rmse" in item["relative"]
```

- [ ] **Step 5: Update old S2R-only assertions**

Replace `test_old_metrics_are_not_emitted` with:

```python
    def test_s2r_diagnostics_do_not_emit_old_ne_family(self):
        agg = aggregate_standard_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.1, 105.0, 12.0),
        ])

        diagnostics = agg["diagnostics"]
        for old_key in ("ne_mean", "ne_std", "nqe_mean", "re_mean", "outlier_rate", "n_outlier"):
            assert old_key not in diagnostics
```

- [ ] **Step 6: Run the failing test**

Run:

```powershell
uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas python -m pytest python\tests\test_metrics.py -q
```

Expected now: FAIL because `DEFAULT_STANDARD_R_LEVELS`, `summarize_standard_errors`, and `aggregate_standard_metrics` do not exist yet.

## Task 2: Backend Metric Implementation

**Files:**
- Modify: `python/studies/common/metrics.py`
- Test: `python/tests/test_metrics.py`

- [ ] **Step 1: Update module docstring**

Change the top docstring from "S2R 唯一评价指标模块" to this:

```python
"""
统一评价指标模块

当前默认主口径遵循第七轮报告：
- 参数视角：Bias、SD、RMSE、MAE；beta/eta 可附相对 Bias/RMSE，gamma 不输出相对指标。
- 工程寿命视角：x_R 的 Bias、SD、RMSE、MAE 与相对 Bias/RMSE。
- S2R 中位数族与尾部指标保留为 diagnostics，用于风险诊断，不再作为唯一主口径。

维护约定：
- 本模块是指标规范页面 `/help/metrics` 的可执行实现。
- `/help/metrics` 是本模块的可读规范说明。
- 修改本模块任一公式、字段名或判定口径时，必须同步修改
  `src/app/help/metrics/page.tsx`；反过来，页面规范变更也必须同步本模块。
"""
```

- [ ] **Step 2: Add standard R levels**

Place this below `DEFAULT_R_LEVELS`:

```python
DEFAULT_STANDARD_R_LEVELS = (0.95, 0.99)
```

- [ ] **Step 3: Add standard summary helpers**

Add this code after `summarize_relative_errors(...)`:

```python
def _empty_standard_summary() -> Dict[str, Optional[float]]:
    return {
        "n": 0,
        "bias": None,
        "sd": None,
        "mse": None,
        "rmse": None,
        "mae": None,
    }


def summarize_standard_errors(errors: List[float] | np.ndarray) -> Dict[str, Optional[float]]:
    """汇总第七轮常用指标族。

    输入必须是带符号误差：
    - 原始尺度误差：theta_hat - theta
    - 或相对误差：(theta_hat - theta) / theta

    SD 使用样本标准差 ddof=1；只有 1 个有效值时 SD 记为 0。
    """
    arr = np.asarray(errors, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return _empty_standard_summary()

    mse = float(np.mean(arr ** 2))
    return {
        "n": int(arr.size),
        "bias": float(np.mean(arr)),
        "sd": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "mse": mse,
        "rmse": float(math.sqrt(mse)),
        "mae": float(np.mean(np.abs(arr))),
    }
```

- [ ] **Step 4: Add raw parameter error helper**

Add this below `param_relative_errors(...)`:

```python
def param_absolute_errors(
    beta_hat: float,
    eta_hat: float,
    gamma_hat: float,
    beta: float,
    eta: float,
    gamma: float,
) -> Dict[str, float]:
    """返回参数视角的原始尺度带符号误差。"""
    return {
        "beta": beta_hat - beta,
        "eta": eta_hat - eta,
        "gamma": gamma_hat - gamma,
    }
```

- [ ] **Step 5: Add standard aggregate function**

Add this after `aggregate_param_metrics(...)`:

```python
def aggregate_standard_metrics(
    results: List[Dict],
    R_levels: Tuple[float, ...] = DEFAULT_STANDARD_R_LEVELS,
    diagnostic_R_levels: Tuple[float, ...] = DEFAULT_R_LEVELS,
    include_diagnostics: bool = True,
) -> Dict:
    """批量计算第七轮常用指标，并嵌入 S2R diagnostics。

    gamma 不输出相对指标；beta/eta 与 x_R 输出相对指标。
    """
    n_total = len(results)
    if n_total == 0:
        return {"n_total": 0}

    valid_rows = []
    n_failure = 0

    for row in results:
        beta_hat = row.get("beta_hat")
        eta_hat = row.get("eta_hat")
        gamma_hat = row.get("gamma_hat")

        if beta_hat is None or eta_hat is None or gamma_hat is None:
            n_failure += 1
            continue

        status = check_status(
            beta_hat,
            eta_hat,
            gamma_hat,
            row["beta"],
            row["eta"],
            row["gamma"],
            converged=row.get("converged", True),
            sample_min=row.get("sample_min"),
        )

        if status == "failure":
            n_failure += 1
        else:
            valid_rows.append(row)

    n_valid = len(valid_rows)
    output = {
        "n_total": n_total,
        "n_valid": n_valid,
        "n_failure": n_failure,
        "valid_rate": n_valid / n_total,
        "failure_rate": n_failure / n_total,
    }

    if include_diagnostics:
        output["diagnostics"] = aggregate_param_metrics(
            results,
            R_levels=diagnostic_R_levels,
        )

    if n_valid == 0:
        return output

    param_abs_errors = {"beta": [], "eta": [], "gamma": []}
    param_rel_errors = {"beta": [], "eta": []}
    quantile_abs_errors = {R: [] for R in R_levels}
    quantile_rel_errors = {R: [] for R in R_levels}

    for row in valid_rows:
        abs_errors = param_absolute_errors(
            row["beta_hat"],
            row["eta_hat"],
            row["gamma_hat"],
            row["beta"],
            row["eta"],
            row["gamma"],
        )
        rel_errors = param_relative_errors(
            row["beta_hat"],
            row["eta_hat"],
            row["gamma_hat"],
            row["beta"],
            row["eta"],
            row["gamma"],
        )

        for name in ("beta", "eta", "gamma"):
            param_abs_errors[name].append(abs_errors[name])
        for name in ("beta", "eta"):
            param_rel_errors[name].append(rel_errors[name])

        for R in R_levels:
            x_true = quantile_true(row["beta"], row["eta"], row["gamma"], R)
            x_hat = quantile_est(row["beta_hat"], row["eta_hat"], row["gamma_hat"], R)
            abs_error = x_hat - x_true
            quantile_abs_errors[R].append(abs_error)
            quantile_rel_errors[R].append(abs_error / x_true)

    param_standard = {}
    for name in ("beta", "eta", "gamma"):
        param_standard[name] = {
            "absolute": summarize_standard_errors(param_abs_errors[name]),
        }
        if name in param_rel_errors:
            param_standard[name]["relative"] = summarize_standard_errors(param_rel_errors[name])

    quantile_standard = {
        R: {
            "absolute": summarize_standard_errors(quantile_abs_errors[R]),
            "relative": summarize_standard_errors(quantile_rel_errors[R]),
        }
        for R in R_levels
    }

    output["param_standard"] = param_standard
    output["quantile_standard"] = quantile_standard

    for name, group in param_standard.items():
        for key, value in group["absolute"].items():
            output[f"{key}_{name}"] = value
        if "relative" in group:
            for key, value in group["relative"].items():
                output[f"rel_{key}_{name}"] = value

    for R, group in quantile_standard.items():
        r_key = str(R).replace(".", "p")
        for key, value in group["absolute"].items():
            output[f"{key}_x_r{r_key}"] = value
        for key, value in group["relative"].items():
            output[f"rel_{key}_x_r{r_key}"] = value

    return output
```

- [ ] **Step 6: Run backend metric tests**

Run:

```powershell
uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas python -m pytest python\tests\test_metrics.py -q
```

Expected: PASS.

## Task 3: Experiment Summary Uses Standard Metrics

**Files:**
- Modify: `python/studies/common/experiment.py`
- Modify: `python/tests/test_experiment.py`
- Test: `python/tests/test_experiment.py`

- [ ] **Step 1: Update imports in `experiment.py`**

Change the metrics import to:

```python
from studies.common.metrics import (
    DEFAULT_R_LEVELS,
    DEFAULT_STANDARD_R_LEVELS,
    aggregate_standard_metrics,
    check_status,
    param_absolute_errors,
    param_relative_errors,
)
```

- [ ] **Step 2: Change `run_experiment` default R levels**

Change the function signature from:

```python
R_levels: Tuple[float, ...] = DEFAULT_R_LEVELS,
```

to:

```python
R_levels: Tuple[float, ...] = DEFAULT_STANDARD_R_LEVELS,
diagnostic_R_levels: Tuple[float, ...] = DEFAULT_R_LEVELS,
```

- [ ] **Step 3: Add raw error columns to each CSV row**

Inside the success branch, compute both raw and relative errors:

```python
abs_errors = param_absolute_errors(
    beta_hat, eta_hat, gamma_hat,
    beta, eta, gamma,
) if status == "success" else {"beta": float("nan"), "eta": float("nan"), "gamma": float("nan")}
rel_errors = param_relative_errors(
    beta_hat, eta_hat, gamma_hat,
    beta, eta, gamma,
) if status == "success" else {"beta": float("nan"), "eta": float("nan"), "gamma": float("nan")}
```

Then add these fields to `row`:

```python
"beta_error": abs_errors["beta"],
"eta_error": abs_errors["eta"],
"gamma_error": abs_errors["gamma"],
```

- [ ] **Step 4: Update `_write_csv` fieldnames**

Add the raw error fields before relative errors:

```python
"status",
"beta_error", "eta_error", "gamma_error",
"beta_rel_error", "eta_rel_error", "gamma_rel_error",
"extra",
```

- [ ] **Step 5: Use standard aggregation**

Replace:

```python
agg = aggregate_param_metrics(results, R_levels=R_levels)
```

with:

```python
agg = aggregate_standard_metrics(
    results,
    R_levels=R_levels,
    diagnostic_R_levels=diagnostic_R_levels,
)
```

- [ ] **Step 6: Update experiment tests**

In `python/tests/test_experiment.py`, update `test_csv_columns()` expected columns to include:

```python
"beta_error", "eta_error", "gamma_error",
```

Update `test_json_summary_counts()` to assert:

```python
assert "param_standard" in group
assert "quantile_standard" in group
assert "diagnostics" in group
assert "param_distribution" in group["diagnostics"]
assert "quantile_distribution" in group["diagnostics"]
```

Keep the existing valid/failure count assertion.

- [ ] **Step 7: Run experiment tests**

Run:

```powershell
uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas python -m pytest python\tests\test_experiment.py -q
```

Expected: PASS.

## Task 4: Monte Carlo API Returns Standard Metrics

**Files:**
- Modify: `python/studies/common/simulation.py`
- Modify: `python/main.py`
- Modify: `python/tests/test_simulation.py`
- Test: `python/tests/test_simulation.py`

- [ ] **Step 1: Import standard aggregation in `simulation.py`**

Add:

```python
from studies.common.metrics import aggregate_standard_metrics
```

- [ ] **Step 2: Add state fields to `simulate_method()` rows**

In `simulate_method()`, after `estimate = run_method(...)`, compute:

```python
sample_min = float(min(sample))
```

Add these fields to the `rows.append({...})` dict:

```python
"method_id": estimate["method_id"],
"converged": estimate["converged"],
"time": estimate["time"],
"sample_min": sample_min,
```

Do not add these fields to `iter_batch_rows()` because its CSV shape is historical and tested.

- [ ] **Step 3: Add row aggregation helper**

Add this function at the end of `simulation.py`:

```python
def aggregate_simulation_rows(rows: List[Dict]) -> Dict:
    """把 simulate_method() 的 API 行转换为默认指标汇总。"""
    metric_inputs = []
    for row in rows:
        metric_inputs.append({
            "beta_hat": row.get("est_beta"),
            "eta_hat": row.get("est_eta"),
            "gamma_hat": row.get("est_gamma"),
            "beta": row["beta_true"],
            "eta": row["eta_true"],
            "gamma": row["gamma"],
            "converged": row.get("converged", True),
            "time": row.get("time"),
            "sample_min": row.get("sample_min"),
        })
    return aggregate_standard_metrics(metric_inputs)
```

- [ ] **Step 4: Update `main.py` import**

Change:

```python
from studies.common.simulation import iter_batch_rows, simulate_method
```

to:

```python
from studies.common.simulation import aggregate_simulation_rows, iter_batch_rows, simulate_method
```

- [ ] **Step 5: Return metrics in `/monte_carlo_simulate`**

In `monte_carlo_simulate`, after `rows = simulate_method(...)`, add:

```python
metrics = aggregate_simulation_rows(rows)
```

Change the return value to:

```python
return {"rows": rows, "count": len(rows), "metrics": metrics, "success": True}
```

- [ ] **Step 6: Update simulation tests**

In `python/tests/test_simulation.py`, update imports:

```python
from studies.common.simulation import aggregate_simulation_rows, iter_batch_rows, simulate_method
```

Add assertions to `test_simulate_method_uses_common_sample_and_runner()`:

```python
assert rows[0]["method_id"] == "mle"
assert rows[0]["converged"] is True
assert rows[0]["time"] >= 0
assert rows[0]["sample_min"] == pytest.approx(float(min(sample)))
```

Add a new test:

```python
def test_aggregate_simulation_rows_returns_standard_metrics():
    rows = simulate_method(
        method_id="mle",
        beta=2.0,
        eta=100.0,
        gamma=5.0,
        n=20,
        rep=3,
        seed=42,
    )

    metrics = aggregate_simulation_rows(rows)

    assert metrics["n_total"] == 3
    assert "param_standard" in metrics
    assert "quantile_standard" in metrics
    assert "diagnostics" in metrics
```

Keep `test_iter_batch_rows_keeps_batch_csv_shape()` unchanged.

- [ ] **Step 7: Run simulation tests**

Run:

```powershell
uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas python -m pytest python\tests\test_simulation.py -q
```

Expected: PASS.

## Task 5: Frontend Metric Helpers

**Files:**
- Modify: `src/lib/metrics.ts`
- Validation: `npx tsc --noEmit`

- [ ] **Step 1: Update module comment**

Change the first comment from "S2R 唯一评价指标模块" to "统一评价指标模块", and state:

```ts
 * 当前默认主口径：
 * - 参数视角：Bias、SD、RMSE、MAE；beta/eta 可附相对 Bias/RMSE，gamma 不输出相对指标。
 * - 工程寿命视角：x_R 的 Bias、SD、RMSE、MAE 与相对 Bias/RMSE。
 * - S2R 中位数族与尾部指标保留为 diagnostics，不再作为唯一主口径。
```

- [ ] **Step 2: Add standard types and default R levels**

Add after `DEFAULT_R_LEVELS`:

```ts
export const DEFAULT_STANDARD_R_LEVELS = [0.95, 0.99] as const

export interface StandardSummary {
  n: number
  bias: number | null
  sd: number | null
  mse: number | null
  rmse: number | null
  mae: number | null
}
```

- [ ] **Step 3: Add standard summary function**

Add after `summarizeRelativeErrors(...)`:

```ts
function emptyStandardSummary(): StandardSummary {
  return {
    n: 0,
    bias: null,
    sd: null,
    mse: null,
    rmse: null,
    mae: null,
  }
}

export function summarizeStandardErrors(errors: number[]): StandardSummary {
  const values = errors.filter(Number.isFinite)
  if (values.length === 0) return emptyStandardSummary()

  const n = values.length
  const bias = values.reduce((sum, value) => sum + value, 0) / n
  const mse = values.reduce((sum, value) => sum + value * value, 0) / n
  const mae = values.reduce((sum, value) => sum + Math.abs(value), 0) / n
  const sd = n > 1
    ? Math.sqrt(values.reduce((sum, value) => sum + (value - bias) ** 2, 0) / (n - 1))
    : 0

  return {
    n,
    bias,
    sd,
    mse,
    rmse: Math.sqrt(mse),
    mae,
  }
}
```

- [ ] **Step 4: Add frontend raw error helper**

Add after `paramRelativeErrors(...)`:

```ts
export function paramAbsoluteErrors(
  betaHat: number,
  etaHat: number,
  gammaHat: number,
  beta: number,
  eta: number,
  gamma: number,
): ParamRelativeErrors {
  return {
    beta: betaHat - beta,
    eta: etaHat - eta,
    gamma: gammaHat - gamma,
  }
}
```

Note: Reusing `ParamRelativeErrors` here is acceptable because the shape is `{ beta, eta, gamma }`; do not rename the existing interface in this task.

- [ ] **Step 5: Run TypeScript check**

Run:

```powershell
npx tsc --noEmit
```

Expected: PASS.

## Task 6: Help Page and Handoff Docs

**Files:**
- Modify: `src/app/help/metrics/page.tsx`
- Modify: `docs/S2R统一评价指标体系进程控制.md`
- Modify: `docs/提示词_新窗口接手.md`
- Validation: `npx tsc --noEmit`

- [ ] **Step 1: Update help page headline**

In `src/app/help/metrics/page.tsx`, change the intro so it says:

```tsx
当前系统默认采用第七轮报告的常用指标：参数视角报告 Bias、SD、RMSE、MAE；
工程寿命视角报告 x_R 的 Bias、SD、RMSE、MAE 与相对 RMSE。
S2R 的 MdAPE、方向、IQR、P95/P99 与有效估计率保留为诊断指标，用于识别尾部风险和异常解。
```

- [ ] **Step 2: Replace `CORE_METRICS` with standard defaults**

Use these metric cards:

```tsx
const CORE_METRICS: MetricDef[] = [
  {
    name: 'Bias',
    nameCn: '偏差',
    latex: '\\frac{1}{N}\\sum_i(\\hat\\theta_i-\\theta)',
    description: '主指标。回答估计值平均偏高还是偏低，必须关注符号。',
    role: '方向',
  },
  {
    name: 'SD',
    nameCn: '标准差',
    latex: '\\sqrt{\\frac{1}{N-1}\\sum_i(\\hat\\theta_i-\\bar{\\hat\\theta})^2}',
    description: '主指标。回答重复抽样下估计值自身波动有多大。',
    role: '稳定性',
  },
  {
    name: 'RMSE',
    nameCn: '均方根误差',
    latex: '\\sqrt{\\frac{1}{N}\\sum_i(\\hat\\theta_i-\\theta)^2}',
    description: '主指标。回答总体误差量级，需与 Bias 和 SD 成套阅读。',
    role: '综合',
  },
  {
    name: 'MAE',
    nameCn: '平均绝对误差',
    latex: '\\frac{1}{N}\\sum_i|\\hat\\theta_i-\\theta|',
    description: '补充指标。与 RMSE 对照可提示尾部或极端误差。',
    role: '补充',
  },
]
```

- [ ] **Step 3: Update perspective descriptions**

Use these three perspective bodies:

```tsx
const PERSPECTIVES = [
  {
    title: '参数视角',
    accent: 'text-blue-700',
    bg: 'bg-blue-50/70',
    border: 'border-blue-100',
    formula: 'e_\\beta=\\hat\\beta-\\beta,\\quad e_\\eta=\\hat\\eta-\\eta,\\quad e_\\gamma=\\hat\\gamma-\\gamma',
    body: '对 beta、eta、gamma 分别报告 Bias、SD、RMSE、MAE。beta 和 eta 可附相对 Bias/RMSE；gamma 不使用相对指标。',
  },
  {
    title: '工程寿命视角',
    accent: 'text-purple-700',
    bg: 'bg-purple-50/70',
    border: 'border-purple-100',
    formula: 'x_R=\\gamma+\\eta(-\\ln R)^{1/\\beta}',
    body: '默认关注 x0.95 与 x0.99。每个 R 单独报告 Bias、SD、RMSE、MAE 与相对 RMSE，不用参数排序替代寿命排序。',
  },
  {
    title: '诊断视角',
    accent: 'text-emerald-700',
    bg: 'bg-emerald-50/70',
    border: 'border-emerald-100',
    formula: 'MdAPE,\\;MedRel,\\;[P_5,P_{95}],\\;P_{95}(|e|),\\;Valid\\ Rate',
    body: 'S2R 中位数族和尾部分位保留为风险诊断，用于发现 RMSE 表格可能掩盖的异常尾部和有效率问题。',
  },
]
```

- [ ] **Step 4: Update docs that currently say S2R is the only system**

In `docs/S2R统一评价指标体系进程控制.md`, change the first section to:

```markdown
## 1. 当前结论

从本阶段开始，项目默认主评价口径调整为第七轮报告推荐的常用指标：

| 视角 | 默认主指标 |
|------|------------|
| 参数视角 | Bias、SD、RMSE、MAE |
| beta/eta 相对补充 | 相对 Bias、相对 RMSE |
| gamma | 只使用绝对尺度指标，不使用相对指标 |
| 工程寿命视角 | x_R 的 Bias、SD、RMSE、MAE、相对 RMSE |

S2R 的 MdAPE、MedRel、RelIQR、P95/P99 与有效估计率保留为诊断指标，不再作为唯一主口径。
```

In `docs/提示词_新窗口接手.md`, replace any sentence that says "S2R 唯一评价指标体系" with:

```markdown
第七轮常用指标已成为默认主口径；S2R 中位数族和尾部指标保留为诊断层。前端指标模块、后端指标模块和 `/help/metrics` 页面必须保持双向同口径。
```

- [ ] **Step 5: Run TypeScript check**

Run:

```powershell
npx tsc --noEmit
```

Expected: PASS.

## Task 7: Full Verification

**Files:**
- No source edits unless a verification failure identifies a specific problem in files already touched by this plan.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas python -m pytest python\tests\test_metrics.py python\tests\test_experiment.py python\tests\test_simulation.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full backend tests**

Run:

```powershell
uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas python -m pytest python\tests -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend typecheck**

Run:

```powershell
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
npm run build
```

Expected: PASS.

- [ ] **Step 5: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no output.

## STOP Conditions

Hermes/mimo must stop and report instead of improvising if any of these happen:

- A test reveals that existing public/studies chunk CSV consumers require an unchanged `simulate_method()` row shape.
- The frontend depends on S2R flat keys as the only metric names in a user-facing table.
- A historical result file needs recalculation to satisfy a page assertion.
- The change requires editing `_archive/`.
- `python/main.py` starts accumulating metric formulas instead of delegating to `python/studies/common`.
- A method needs real parameters to estimate in normal comparison mode.

## Executor Report Template

Hermes/mimo should finish with:

```markdown
## 执行报告

### 修改文件
- 逐行列出实际修改文件，例如 `python/studies/common/metrics.py`

### 实现摘要
- 第七轮常用指标成为默认主口径。
- S2R 保留为 diagnostics。

### 已运行验证
- 逐行列出实际运行命令，例如 `uv run --with pytest --with scipy --with fastapi --with numpy --with pydantic --with pandas python -m pytest python\tests\test_metrics.py -q`
- 结果必须写明通过或失败，并摘录失败测试名

### 未运行验证
- 逐行列出计划中未运行的验证命令
- 原因必须具体，例如缺少依赖、耗时过长、或被用户要求跳过

### 偏离计划之处
- 无 / 说明原因
```

## Codex Review Checklist

When reviewing the Hermes/mimo diff, Codex should check:

- `git diff --stat` contains only the files listed in this plan, unless the executor explains why.
- `python/studies/common/metrics.py` does not remove S2R helpers.
- `gamma` has no relative metric in `param_standard`.
- `x0.95` and `x0.99` are default engineering lifetime levels.
- `iter_batch_rows()` CSV shape remains unchanged.
- `/monte_carlo_simulate` keeps `rows`, `count`, and `success`, and adds `metrics`.
- `/help/metrics` no longer says S2R is the only metric system.
- Tests prove standard metrics are default and diagnostics still exist.
- Verification commands and outputs are included in the executor report.

## Review Verdict Format

Codex will respond with one of:

```markdown
VERDICT: APPROVE
```

```markdown
VERDICT: REVISE
```

```markdown
VERDICT: BLOCK
```

`REVISE` and `BLOCK` must name specific files and expected fixes.

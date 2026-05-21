# S2 统一评价指标模块规划

> 用途：供审查者评估统一指标模块的设计方案，确认后再进入代码实现。
> 依据：`AI辅助三参数威布尔参数估计重构与实验设计总纲.md` 第 4 节。

---

## 1. 目标

建立一个独立于具体估计方法的指标计算模块，供以下场景共同调用：

- 统一蒙特卡洛调度框架（S4）；
- AI 训练脚本中的验证评估；
- 横向比较结果表生成（S6）；
- 论文或组会表格输出（S7）。

本模块**不做**：

- 不修改旧脚本（旧脚本保留原逻辑，后续由蒙特卡洛框架统一调用新模块）；
- 不创建前端组件或 API 端点；
- 不负责样本生成或方法调用。

---

## 2. 指标体系

### 2.1 参数估计视角

回答：`beta、eta、gamma` 三个参数估得准不准？

| 指标 | 符号 | 公式 | 说明 |
|------|------|------|------|
| 归一化综合误差 | NE | 见下方 | 核心横向比较指标 |
| 偏差 | Bias | `β̂-β`（按参数分别计算） | 判断是否存在系统偏差 |
| 平均绝对误差 | MAE | `mean(\|θ̂-θ\|)` | 按参数分别计算 |
| 均方根误差 | RMSE | `sqrt(mean((θ̂-θ)²))` | 按参数分别计算 |
| 运行时间 | Time | `mean(t)` 和分位数 | 方法效率 |

NE 公式（与总纲一致）：

```text
NE = sqrt(
    ((beta_hat - beta) / beta)^2
  + ((eta_hat - eta) / eta)^2
  + ((gamma_hat - gamma) / eta)^2
)
```

关键设计：gamma 使用 **eta** 归一化，不是 gamma 自身。原因：

- gamma 可能为 0，用 gamma 归一化会除零；
- 旧代码中 `compute_relative_mse()` 用 gamma 归一化，存在此问题；
- eta 在同一参数组合下是固定值，归一化尺度稳定。

### 2.2 工程应用分位点视角

回答：给定可靠度水平下的寿命估不准？

可靠度水平：

```text
R ∈ {0.995, 0.990, 0.950, 0.900}
```

真实分位点：

```text
x_R = gamma + eta * (-ln(R))^(1 / beta)
```

估计分位点：

```text
x_hat_R = gamma_hat + eta_hat * (-ln(R))^(1 / beta_hat)
```

| 指标 | 符号 | 公式 | 说明 |
|------|------|------|------|
| 分位点偏差 | Bias_QR | `x̂_R - x_R` | 按 R 分别计算 |
| 分位点平均绝对误差 | MAE_QR | `mean(\|x̂_R - x_R\|)` | 按 R 分别计算 |
| 分位点均方根误差 | RMSE_QR | `sqrt(mean((x̂_R - x_R)²))` | 按 R 分别计算 |
| 相对分位点误差 | RE_QR | `\|x̂_R - x_R\| / x_R` | 单样本相对误差 |
| 归一化分位点误差 | NQE_R | `\|x̂_R - x_R\| / eta` | 主参考指标，更稳健 |

NQE_R 用 eta 归一化而非 x_R，原因：

- 当 R 接近 1 时 x_R 可能很小，RE_QR 会放大误差；
- eta 是尺度参数，归一化后跨参数组合可比。

### 2.3 方法可用性视角

回答：方法是否可用、是否稳定？

三态互斥：每个样本恰好属于 success、failure、outlier 之一。

| 指标 | 公式 | 说明 |
|------|------|------|
| Failure Rate | `failure_count / total_count` | failure 样本占比 |
| Outlier Rate | `outlier_count / total_count` | outlier 样本占比（不含 failure） |
| Success Rate | `success_count / total_count` | success 样本占比 |
| Time 均值 | `mean(time[success])` | 仅 success 样本的平均运行时间 |
| Time P50/P95 | `percentile(time[success], [50,95])` | 仅 success 样本的运行时间分位数 |

约束：`failure_count + outlier_count + success_count = total_count`。

精度指标（NE、MAE、RMSE、分位点误差等）**仅统计 success 样本**。failure 和 outlier 不进入精度均值，但 failure 和 outlier 样本数必须保留，用于计算 Failure Rate 和 Outlier Rate。

---

## 3. 状态判定规则

所有方法结果统一落入三类状态：

| 状态 | 含义 | 判定规则 |
|------|------|----------|
| `success` | 数值有效、物理可解释 | 未触发 failure 和 outlier 规则 |
| `failure` | 未能给出可用结果 | `beta_hat` 或 `eta_hat` 非有限或 ≤ 0；方法自身报告失败 |
| `outlier` | 有结果但明显异常 | `NE > 1.0`（第一版默认阈值） |

判定流程：

```text
方法返回结果
  → 框架检查 beta_hat、eta_hat 是否为有限正数
    → 否 → failure
    → 是 → 计算 NE
      → NE > 1.0 → outlier
      → NE ≤ 1.0 → success
```

注意：

- 方法自身负责报告是否收敛；框架负责统一后处理；
- failure 样本**必须**进入 Failure Rate 的分母，不能静默删除；
- outlier 阈值可后续调整，但必须在实验报告中说明。

---

## 4. 模块结构

```
python/studies/common/
├── __init__.py      # 统一导出
└── metrics.py       # 全部指标计算函数
```

按 `02-规则.md` 的规定，后端共享指标函数放在 `python/studies/common/metrics.py`。`02-规则.md` 原文：

> 指标计算代码 → 必须调用共享函数（前端 `src/lib/metrics.ts`，后端 `python/studies/common/metrics.py`），禁止内联重复实现

本模块遵守该规范。蒙特卡洛脚本和 AI 训练脚本都通过 `from studies.common.metrics import ...` 调用。

---

## 5. 函数设计

### 5.1 单样本指标函数

```python
def ne(beta_hat, eta_hat, gamma_hat, beta, eta, gamma) -> float:
    """归一化综合误差 NE"""

def quantile_true(beta, eta, gamma, R) -> float:
    """真实分位点 x_R"""

def quantile_est(beta_hat, eta_hat, gamma_hat, R) -> float:
    """估计分位点 x_hat_R"""

def nqe_R(beta_hat, eta_hat, gamma_hat, beta, eta, gamma, R) -> float:
    """归一化分位点误差 |x̂_R - x_R| / eta"""

def re_R(beta_hat, eta_hat, gamma_hat, beta, eta, gamma, R) -> float:
    """相对分位点误差 |x̂_R - x_R| / x_R"""
```

### 5.2 状态判定函数

```python
def check_status(
    beta_hat, eta_hat, gamma_hat,
    beta, eta, gamma,
    converged=True, ne_threshold=1.0
) -> str:
    """
    判定单样本状态：success / failure / outlier

    判定顺序：
    1. beta_hat 或 eta_hat 非有限或 ≤ 0 → failure
    2. gamma_hat 非有限 → failure（不要求 >0，但必须 finite）
    3. converged 为 False → failure
    4. NE > ne_threshold → outlier（NE 由函数内部计算，需要真值参数）
    5. 其余 → success
    """
```

### 5.3 批量聚合函数

```python
def aggregate_param_metrics(results, R_levels=(0.995, 0.990, 0.950, 0.900)) -> dict:
    """
    输入：results 列表，每个元素为字典
    输出：参数视角 + 分位点视角 + 可用性视角的全部指标

    返回结构：
    {
        "n_total": int,
        "n_success": int,
        "n_failure": int,
        "n_outlier": int,
        "failure_rate": float,
        "outlier_rate": float,

        # 仅 success 样本
        "ne_mean": float,
        "ne_std": float,
        "bias_beta": float, "bias_eta": float, "bias_gamma": float,
        "mae_beta": float, "mae_eta": float, "mae_gamma": float,
        "rmse_beta": float, "rmse_eta": float, "rmse_gamma": float,
        "time_mean": float,
        "time_p50": float,
        "time_p95": float,

        # 分位点指标（按 R 分别计算）
        "quantile": {
            0.995: {"bias": float, "mae": float, "rmse": float, "nqe_mean": float, "nqe_std": float},
            0.990: {...},
            0.950: {...},
            0.900: {...},
        }
    }
    """
```

### 5.4 输入契约

`results` 列表中每个元素的字典结构：

```python
{
    "beta_hat": float | None,   # 估计值，failure 时为 None
    "eta_hat": float | None,
    "gamma_hat": float | None,
    "beta": float,              # 真值
    "eta": float,
    "gamma": float,
    "time": float,              # 运行时间（秒）
    "converged": bool,          # 方法自身报告是否成功
}
```

status 字段由 `check_status()` 统一判定，不由各方法自行定义。

---

## 6. 与旧代码的关系

| 旧代码 | 处理方式 |
|--------|----------|
| `base.py` 的 `_calculate_r2()` | 保留，仅用于拟合优度，与本模块不重叠 |
| `train_model.py` 的 `relative_mse_loss()` | 保留原样，后续 loss 对比实验（S3）再决定是否替换 |
| `mdm_delta/` 的 `compute_relative_mse()` | 保留原样，后续蒙特卡洛框架统一调用新模块 |
| `simulate.py` 中的 bias 计算 | 保留原样，后续由蒙特卡洛框架（S4）统一调用新模块 |

本模块不删除旧代码，不修改旧脚本。旧代码在 S4 统一蒙特卡洛框架接入时自然被新模块替代。

---

## 7. 待审查问题

请审查者重点关注：

1. **NE 公式**：gamma 用 eta 归一化是否合理？是否存在 eta 很小导致 NE 被放大的问题？
2. **NQE_R 公式**：用 eta 归一化而非 x_R，是否在所有 R 水平下都合理？
3. **outlier 阈值**：第一版 NE > 1.0 是否合适？过大或过小？
4. **状态判定顺序**：先检查物理约束再检查 NE，这个顺序是否正确？
5. **聚合函数的返回结构**：字段是否完整？是否有多余字段？
6. **是否缺少必要指标**：当前指标体系是否遗漏了重要的评价维度？

已确定的决策：

- 模块位置：`python/studies/common/metrics.py`，符合 `02-规则.md` 规范。

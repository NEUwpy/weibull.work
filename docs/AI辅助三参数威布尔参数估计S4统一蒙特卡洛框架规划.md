# S4 统一蒙特卡洛框架最小闭环规划

> 用途：供审查者评估统一蒙特卡洛框架的设计方案，确认后再进入代码实现。
> 依据：`AI辅助三参数威布尔参数估计重构与实验设计总纲.md` 第 6 节。
> 前置：S2 统一评价指标 + S2.5 指标规范同步均已完成。

---

## 1. 目标

建立一个统一的蒙特卡洛调度框架，解决旧平台中每新增一个方法就重写一套仿真流程的问题。

本阶段是最小闭环：只实现核心调度逻辑，接入少量传统方法作为验证，不展开全部实验。

本阶段不做：

- 不训练 AI 模型
- 不跑大规模蒙特卡洛实验（验证用小规模即可）
- 不修改旧 simulate.py 脚本（旧脚本保留，后续自然被替代）
- 不创建前端页面或 API 端点

---

## 2. 当前问题

### 2.1 样本不共享

旧 simulate.py 各自独立生成样本，种子策略不统一。同一参数组合、同一样本量、同一重复编号，不同方法可能生成不同样本，无法做配对比较。

### 2.2 结果结构不统一

- MDM simulate.py 输出：`est_beta, est_eta, est_gamma, bias_beta, bias_eta, bias_gamma, r_squared`
- MLE simulate.py 输出：类似但列名可能不同
- 失败记录不统一：有的写 `NaN`，有的跳过
- 没有 `converged`、`time`、`status` 字段

### 2.3 指标不统一

旧脚本内联计算 bias 和 r_squared，没有调用 S2 统一指标模块，没有 NE、分位点误差、Failure Rate、Outlier Rate。

### 2.4 方法调用不统一

各 simulate.py 直接 import 具体方法类并调用，没有统一的调用接口。

---

## 3. 设计方案

### 3.1 模块位置

```
python/studies/common/
├── __init__.py          # 已有
├── metrics.py           # 已有（S2）
├── sample.py            # 新建：统一样本生成
├── runner.py            # 新建：统一方法调用 + 结果记录
└── experiment.py        # 新建：统一蒙特卡洛调度
```

按 `02-规则.md` 规范，多方法共用的逻辑放在 `studies/common/`。

### 3.2 统一样本生成（sample.py）

```python
def generate_sample(beta, eta, gamma, n, repeat_id):
    """
    给定参数组合、样本量和重复编号，生成确定性可复现的样本。

    种子策略：hashlib.sha256 对规范化字符串编码后取 32 位整数。
    浮点参数使用 repr() 规范化，确保不同平台产生相同字符串。
    这样同一参数组合 + n + repeat_id 必定生成同一份样本，
    不同方法共享同一份样本，支持配对比较。

    返回：np.ndarray，已排序
    """
```

关键设计：

- 种子由 `(beta, eta, gamma, n, repeat_id)` 唯一确定
- 使用 `hashlib.sha256` 对 `f"{repr(beta)}|{repr(eta)}|{repr(gamma)}|{n}|{repeat_id}"` 编码，取前 4 字节转 32 位整数；不使用 Python 内置 `hash()`（其跨进程不稳定）
- 不依赖方法 ID，不依赖 sim_id（sim_id 就是 repeat_id）
- 返回排序后的样本（与旧 `generate_weibull_sample` 行为一致）
- gamma=0 时公式仍有效：`0 + eta * (-ln(1-u))^(1/beta)`

### 3.3 统一方法调用（runner.py）

```python
def run_method(method_id, sample, variant=None, **kwargs):
    """
    统一调用估计方法，返回标准化结果字典。

    输入：
        method_id: 方法标识（如 "mle", "mdm"）
        sample: np.ndarray 或 list
        variant: 方法方案标识（如 "mdm_offset0.5"），用于区分同一方法的不同参数配置；
                 为 None 时自动设为 method_id
        **kwargs: 方法特有参数（如 MDM 的 offset, gamma_steps）

    返回：{
        "method_id": str,
        "method_variant": str,    # 方法方案标识，用于结果分组
        "beta_hat": float | None,
        "eta_hat": float | None,
        "gamma_hat": float | None,
        "r_squared": float | None,
        "converged": bool,
        "time": float,           # 运行时间（秒）
        "extra": dict | None,    # 方法特有诊断信息，落 CSV 时序列化为 JSON 字符串
    }
    """
```

关键设计：

- 复用 `registry.py` 的 `resolve_method()` 获取方法类
- 兼容旧方法的三种返回格式（MethodResult / 5 元素 / 4 元素）
- 用 `time.perf_counter()` 计时
- try/except 包裹，异常时返回 `converged=False` + 空估计值
- 不读取真值参数（真值只用于后续指标计算）

### 3.4 统一蒙特卡洛调度（experiment.py）

```python
def run_experiment(
    methods: list,           # ["mle", "mdm"] 或带参数的 [("mdm", {"offset": 0.5, "variant": "mdm_offset0.5"})]
    param_grid: list,        # [(beta, eta, gamma), ...]
    n_values: list,          # [10, 20, 30, 50, 100]
    n_repeats: int,          # 每组重复次数
    R_levels: tuple,         # (0.995, 0.990, 0.950, 0.900)
    output_dir: str,         # 结果保存目录
) -> dict:
    """
    运行完整蒙特卡洛实验。

    流程：
    1. 遍历 param_grid × n_values
    2. 对每个组合，生成 n_repeats 个共享样本
    3. 对每个样本，调用所有方法
    4. 用 S2 指标模块计算每条结果的状态和指标
    5. 保存逐条结果 + 聚合汇总

    返回：汇总字典（按方法 × 参数组合 × n 分组的聚合指标）
    """
```

### 3.5 结果保存

#### 逐条结果（CSV）

每行一条样本 × 方法的结果：

| 列名 | 类型 | 说明 |
|------|------|------|
| beta | float | 真值 |
| eta | float | 真值 |
| gamma | float | 真值 |
| n | int | 样本量 |
| repeat_id | int | 重复编号 |
| method_id | str | 方法标识 |
| method_variant | str | 方法方案标识（如 "mdm_offset0.5"），用于区分同一方法的不同参数配置 |
| beta_hat | float/NaN | 估计值 |
| eta_hat | float/NaN | 估计值 |
| gamma_hat | float/NaN | 估计值 |
| r_squared | float/NaN | 拟合优度 |
| converged | bool | 方法自身报告 |
| time | float | 运行时间 |
| status | str | success/failure/outlier（由 S2 check_status 判定，固定阈值 1.0） |
| ne | float/NaN | NE 值（success 和 outlier 均记录，failure 为 NaN） |
| extra | str/NaN | 方法特有诊断信息，序列化为 JSON 字符串；无额外信息时为 NaN |

失败行的 `beta_hat/eta_hat/gamma_hat` 写 `NaN`，`status` 写 `failure`。不跳过、不删除。

#### 聚合汇总（JSON）

按 `method_variant × (beta, eta, gamma) × n` 分组（而非仅按 `method_id`），每组调用 `aggregate_param_metrics()` 生成汇总。这样同一方法的不同参数配置（如 MDM offset=0.3 vs offset=0.5）会被分别统计。

`aggregate_param_metrics()` 已支持接收 `ne_threshold` 参数（S2 同步扩展），默认值 1.0，与逐条结果的 status 判定阈值保持一致。

---

## 4. 方法接入契约

所有方法通过统一接口接入，不要求修改方法内部实现。

### 4.1 输入

- 方法接收排序后的样本（list 或 np.ndarray）
- 方法不读取真值参数
- 方法特有参数通过 `**kwargs` 传入（如 MDM 的 `offset`, `gamma_steps`）

### 4.2 输出

方法 `run()` 返回以下三种格式之一，由 `runner.py` 统一处理：

- `MethodResult` 对象（新）
- 5 元素 list/tuple `[beta, eta, gamma, r2, converged]`
- 4 元素 list/tuple `[beta, eta, gamma, r2]`（默认 `converged=True`）

### 4.3 验证方法选择

第一版接入 3 个传统方法作为验证：

| 方法 | 选择原因 |
|------|----------|
| MLE | 最常用，有 `run()` 实现 |
| MDM | 项目核心方法，有额外参数（offset） |
| LSE | 结构简单，有 `run()` 实现 |

---

## 5. 参数空间

第一版验证用小参数空间：

```text
beta ∈ {1.5, 2.0, 3.0}
eta = 100（固定）
gamma/eta ∈ {0, 0.10}
n ∈ {10, 30}
n_repeats = 100
```

展开为 3 × 1 × 2 × 2 = 12 个组合，每组 100 次，每个方法 1200 次估计。3 个方法共 3600 次。这个规模足以验证框架正确性，不会太慢。

完整参数空间（总纲定义）留待后续正式实验：

```text
beta ∈ {0.8, 1.2, 1.5, 2.0, 3.0, 5.0}
eta ∈ {50, 100, 200}
gamma/eta ∈ {0, 0.05, 0.10, 0.20}
n ∈ {10, 20, 30, 50, 100}
```

---

## 6. 与旧代码的关系

| 旧代码 | 处理方式 |
|--------|----------|
| `studies/mdm/simulate.py` | 保留原样，不修改 |
| `studies/mle/simulate.py` | 保留原样，不修改 |
| `studies/wmle/simulate.py` | 保留原样，不修改 |
| `generate_weibull_sample()` 各处定义 | 保留原样，新框架用 `sample.py` 的统一版本 |
| `methods/*.py` 算法实现 | 直接复用，通过 `registry.py` 调用 |
| `base.py` WeibullBase/MethodResult | 直接复用 |
| `studies/common/metrics.py` | 直接调用 |

旧脚本在新框架验证通过后自然被替代，不需要主动删除或修改。

---

## 7. 验收标准

1. **样本可复现**：同一 `(beta, eta, gamma, n, repeat_id)` 生成同一份样本，不同方法共享
2. **样本一致性**：同一 `repeat_id` 下 3 个方法的样本数组完全一致；不同 `repeat_id` 样本不同
3. **方法共享样本**：3 个方法在同一样本上运行，结果可配对比较
4. **失败保留**：failure 样本的 `beta_hat` 写 `NaN`，`status` 写 `failure`，不跳过
5. **异常保留**：NE > 1.0 的样本 `status` 写 `outlier`，不删除；outlier 的 `ne` 列记录实际 NE 值
6. **指标统一**：所有指标由 `studies/common/metrics.py` 计算，无内联重复
7. **阈值一致**：逐条 status 判定和聚合 `aggregate_param_metrics()` 均使用默认阈值 1.0，无不一致
8. **逐条结果可追溯**：CSV 中每行可追溯到参数组合、样本量、重复编号、方法方案
9. **方法方案区分**：不同参数配置的方法（如 MDM offset=0.3 vs 0.5）在 CSV 和聚合中被分别标识和统计
10. **聚合汇总正确**：`failure_count + outlier_count + success_count = total_count`
11. **测试通过**：新增 3 个测试文件（`test_sample.py`, `test_runner.py`, `test_experiment.py`）全部通过，且原有 `test_metrics.py` 32 个测试继续通过

---

## 8. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `python/studies/common/sample.py` | 新建 | 统一样本生成（hashlib 种子策略） |
| `python/studies/common/runner.py` | 新建 | 统一方法调用（含 method_variant） |
| `python/studies/common/experiment.py` | 新建 | 统一蒙特卡洛调度 |
| `python/studies/common/metrics.py` | 修改 | `aggregate_param_metrics()` 新增 `ne_threshold` 参数 |
| `python/tests/test_sample.py` | 新建 | 样本可复现性测试 |
| `python/tests/test_runner.py` | 新建 | 方法调用测试 |
| `python/tests/test_experiment.py` | 新建 | 小规模端到端测试 |
| `python/tests/test_metrics.py` | 修改 | 补充 ne_threshold 透传测试 |

---

## 9. 审查问题处理记录

| 问题 | 处理结果 |
|------|----------|
| 种子策略 | 已改为 `hashlib.sha256` + `repr()` 规范化字符串，不使用 Python 内置 `hash()` |
| 方法特有参数 | 保留 `**kwargs` 传入；新增 `variant` 参数区分方案，CSV 聚合按 `method_variant` 分组 |
| CSV 格式 | 第一版使用 CSV，足够；`extra` 字段序列化为 JSON 字符串 |
| 验证参数空间 | 保持不变（eta=100 固定、gamma/eta ∈ {0, 0.10}、n ∈ {10, 30}、100 次重复） |
| 模块拆分 | 保持 sample/runner/experiment 三文件拆分 |
| ne_threshold 一致性 | S4 固定默认阈值 1.0，不暴露参数；同步扩展 `aggregate_param_metrics()` 接收 `ne_threshold` |
| CSV ne 字段 | success 和 outlier 均记录 NE 值，仅 failure 为 NaN |

# 威布尔算法开发指南 (Algorithm Developer Guide)

本文档旨在指导开发者如何实现或修改 `python/methods/` 目录下的参数估计算法。

## 1. 核心工作流

已有实现先复用；仅对实际占位方法（如 `mps.py`）按以下步骤补齐：

1. **选择文件**: 打开对应的 `.py` 文件。
2. **移除占位**: 删除 `raise NotImplementedError`。
3. **实现逻辑**: 编写数学推导代码。
4. **验证**: 运行 `main.py` 测试 API，或直接运行该文件（如果有 `if __name__ == "__main__":` 块）。

---

## 2. 代码规范 (Standard Interface)

所有算法类必须继承自 `WeibullBase` 并实现 `run` 方法。

### 输入 (Input)
- 数据通过 `self.data` 获取（自动排序的 NumPy 数组）。
- 样本量通过 `self.n` 获取。

### 输出 (Output)
`run()` 通常返回参数、拟合量和成功标记；统一调用器也兼容历史4元组及 `MethodResult`：

```python
return [beta, eta, gamma, r_squared, converged]
```

| 参数 | 符号 | 描述 | 备注 |
| :--- | :--- | :--- | :--- |
| **beta** | $\beta$ | 形状参数 (Shape) | 斜率，必须 > 0 |
| **eta** | $\eta$ | 尺度参数 (Scale) | 特征寿命，必须 > 0 |
| **gamma** | $\gamma$ | 位置参数 (Location) | 失效阈值，通常 >= 0 |
| **r_squared** | $R^2$ | 拟合优度 | 0.0 - 1.0 之间 |
| **converged** | — | 方法成功标记 | 失败不补入默认参数 |

---

## 3. 基类工具 (WeibullBase Utilities)

`WeibullBase` (在 `../base.py` 中) 提供了一些常用的数学工具，请优先使用以保持一致性：

- **`self._median_ranks()`**
  - 计算贝纳德中位秩 (Benard's Median Ranks)。
  - 返回: NumPy 数组 (F值)。

- **`self._calculate_r2(beta, eta, gamma)`**
  - 标准化的 R² 计算函数。
  - 在你算出参数后，直接调用此方法计算拟合优度。

---

## 4. 示例代码 (Example)

```python
from base import WeibullBase
import numpy as np

class MyNewMethod(WeibullBase):
    def run(self):
        # 1. 获取数据
        t = self.data
        n = self.n
        
        # 2. 你的算法逻辑 (例如: 简单的均值估计)
        # 注意: 这只是个示例，非真实威布尔算法
        gamma = 0.0 
        eta = np.mean(t)
        beta = 1.0  # 假设指数分布
        
        # 3. 计算 R^2 (使用基类方法)
        r2 = self._calculate_r2(beta, eta, gamma)
        
        # 4. 返回标准结果
        return [beta, eta, gamma, r2, True]
```

## 5. 调试建议

建议每个算法文件底部保留一段测试代码，这样您可以直接运行 `python methods/your_algo.py` 进行独立调试，而不需要每次都通过 API。

```python
if __name__ == "__main__":
    test_data = [10, 20, 30, 40, 50]
    result = MyNewMethod(test_data).run()
    print(f"Beta: {result[0]}, Eta: {result[1]}, Gamma: {result[2]}, R2: {result[3]}")
```

## 6. 两版MMLE的注册口径（2026-10-07）

- `mmle` → `methods.mmle.MMLE`：Kundu–Raqab构造的单样本形式，与Research09实际 `KROriginal` 一致。令γ̂为原样本最小值，删除这一个观测，对其余观测使用 `y=x[1:]-γ̂`，再按固定点迭代估计β和η。来源为Kundu & Raqab（2009），*Statistics & Probability Letters* 79(17):1839–1846，印刷1840页式(4)、1841页式(6)(9)–(11)，DOI `10.1016/j.spl.2009.05.026`。原文研究两样本应力–强度问题；这里实现其删最小值和剖面迭代的单样本化简。
- `mmle_ch` → `methods.mmle_ch.MMLE`：原Cohen–Whitten（1982）MMLE-I工程实现，原文件字节完整保留。它以第一顺序统计量的累计概率约束替代位置似然方程，采用50个位置候选；其既有边界、近似处理和成功标记未修复，不与K-R混称。

K-R默认模块常量为 `INITIAL_SHAPE=1.0`、`SHAPE_ABSOLUTE_STEP_TOLERANCE=1e-8`、`MAX_ITERATIONS=10000`；`run()`可用同名小写参数覆盖。它不加Firth修正、额外形状或位置上界，不重试，不换求解器。失败返回 `[None,None,None,0.0,False]`，`last_solution_info`保存迭代次数、最终步长、删除数和支持边界。R²沿用R09的0占位，不解释为拟合优度为零。

支持检查须使用保留观测的最小值 `x[1]`，因为γ̂等于已删除的原最小值 `x[0]`。通用全样本支持检查仍拒绝γ̂≥x[0]；本次不改变runner或metrics，实验接入时须显式说明删最小值的支持口径。`run_method('mmle_ch', sample)`可调用旧版，现有冻结批次不会因注册语义变化而重算。

正式对拍复用R00的W(2,1000,500)与W(2,1000,3000)各100组样本，n=7/15各50组：200组均与R09实际类成功状态相同，三个参数及原有诊断逐项一致，最大绝对差为0；不重抽、不向R00写结果。另用R09存档W(2,1000,500)的6000组样本CSV作额外核对：成功/失败集合相同，与实际类的参数及原有诊断逐项一致；CSV参数最大绝对差为2.2737367544323206e-13。独立剖面得分定根、预算失败、重复最小值、形状大于10及两版分派见 `tests/test_mmle_kundu_raqab2009.py`。这一核验不等于完整复现原文两样本实验。

# 威布尔算法开发指南 (Algorithm Developer Guide)

本文档旨在指导开发者如何实现或修改 `python/methods/` 目录下的参数估计算法。

## 当前MLE、WMLE与LRE版本（2026-10-16）

MLE、WMLE 共用 [`profile_solvers.py`](profile_solvers.py)。条件搜索、权重和边界诊断分别见 [MLE](../../src/content/algorithms/mle.md) 与 [WMLE](../../src/content/algorithms/wmle.md) 的实现说明。求解改善本身不足以判断统计风险。

[LRE](../../src/content/algorithms/lre.md) 的实现说明记录 Park（2017）Proposed+Plot、切换前的 Bernard 绘图位置及验证范围。Study04 的冻结结果与后续比较版本见[备份说明](<D:/weibull-research/Study/04-study-小样本三参数Weibull估计方法比较与选择/程序/历史版本/2026-10-16-求解更新前/版本说明.md>)。

## 单一现行实现与差异讨论（2026-11-02）

单一实现、原文差异讨论及历史追溯统一见[开发规则](../../02-规则.md#24-方法页面与实现维护)。

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

- `mmle` → [`methods.mmle.MMLE`](mmle.py)，现行 Kundu–Raqab 单样本实现。
- `mmle_ch` → [`methods.mmle_ch.MMLE`](mmle_ch.py)，旧 Cohen–Whitten 工程实现，供后端显式调用。

原文、配置、保留观测的支持检查和 R00/R09 对拍证据统一见 [MMLE 方法说明](../../src/content/algorithms/mmle.md)。实验接入时按该说明核对删去最小值后的支持口径。注册分派与边界测试见 [`test_mmle_kundu_raqab2009.py`](../tests/test_mmle_kundu_raqab2009.py)。

## 7. 真实运行记录（2026-11-02）

各方法的 `calculation_trace` 通过[共享 runner](../studies/common/runner.py)绑定输入、配置和源码身份。计算记录契约见[外部运行数据](../../docs/data/README.md#计算记录)，trace 开关对参数的回归验收见[计算过程验收](../../docs/development/method-pages.md#计算过程验收)。待讨论的 MDM 秩、WMLE 权重和位置边界、MM 位置修正与尺度恢复见[原文差异记录](../../coworker/reports/2026-11-02-single-method-implementation.md)。

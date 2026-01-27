# 威布尔算法开发指南 (Algorithm Developer Guide)

本文档旨在指导开发者如何实现或修改 `python/methods/` 目录下的参数估计算法。

## 1. 核心工作流

目前的架构中，许多算法文件（如 `mle.py`, `bayesian.py`）仅包含占位符。要激活它们，请遵循以下步骤：

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
`run()` 方法**必须**返回一个包含 4 个浮点数的列表或元组：

```python
return [beta, eta, gamma, r_squared]
```

| 参数 | 符号 | 描述 | 备注 |
| :--- | :--- | :--- | :--- |
| **beta** | $\beta$ | 形状参数 (Shape) | 斜率，必�� > 0 |
| **eta** | $\eta$ | 尺度参数 (Scale) | 特征寿命，必须 > 0 |
| **gamma** | $\gamma$ | 位置参数 (Location) | 失效阈值，通常 >= 0 |
| **r_squared** | $R^2$ | 拟合优度 | 0.0 - 1.0 之间 |

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
        return [beta, eta, gamma, r2]
```

## 5. 调试建议

建议每���算法文件底部保留一段测试代码，这样您可以直接运行 `python methods/your_algo.py` 进行独立调试，而不需要每次都通过 API。

```python
if __name__ == "__main__":
    test_data = [10, 20, 30, 40, 50]
    result = MyNewMethod(test_data).run()
    print(f"Beta: {result[0]}, Eta: {result[1]}, Gamma: {result[2]}, R2: {result[3]}")
```

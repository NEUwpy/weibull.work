# Python 算法编写指南

本文档说明如何在 Python 算法文件中添加注释，以便自动生成程序流程展示。

---

## 注释标记规范

### 1. 文件头注释

```python
"""
方法名称 (缩写)
英文全称

算法文档: ../../src/content/algorithms/xxx.md
描述: 方法的简要描述
"""
```

### 2. 步骤标记 `@step`

标记一个计算步骤的开始：

```python
# @step: <序号> | <步骤名称> | <步骤描述>
```

- **序号**：从 1 开始的整数
- **步骤名称**：简短的中文名称（4-8字）
- **步骤描述**：详细说明这一步做什么

**示例**：
```python
# @step: 1 | 数据预处理 | 对原始样本进行排序，获取样本数量
```

### 3. 公式标记 `@formula`

当前步骤使用的数学公式（LaTeX 格式）：

```python
# @formula: <LaTeX 表达式>
```

**示例**：
```python
# @formula: F(t_i) = \frac{i - 0.3}{n + 0.4}
```

### 4. 符号说明 `@symbols`

公式中符号的含义（三字段格式）：

```python
# @symbols: <代码变量>|<数学符号>|<含义说明>, <代码变量>|<数学符号>|<含义说明>
```

**示例**：
```python
# @symbols: t|t|排序后的失效时间数组, n|n|样本数量
```

### 5. 输入变量 `@inputs`

当前步骤的输入变量（三字段格式）：

```python
# @inputs: <代码变量>|<数学符号>|<含义说明>, ...
```

**示例**：
```python
# @inputs: data|t_i|原始失效时间样本
```

**下标写法**：用 LaTeX 下标语法
```python
# @outputs: trace_data|trace_{data}|追踪数据
```

### 6. 输出变量 `@outputs`

当前步骤的输出变量（三字段格式）：

```python
# @outputs: <代码变量>|<数学符号>|<含义说明>, ...
```

**示例**：
```python
# @outputs: t|t_{(i)}|排序后的失效时间数组, n|n|样本数量
```

### 7. 循环标记 `@loop`

标记这是一个循环步骤：

```python
# @loop: <循环次数说明>
```

**示例**：
```python
# @loop: gamma_steps 次 (默认 60)
```

---

## 完整示例

```python
"""
最小差异法 (MDM)
Minimum Discrepancy Method

算法文档: ../../src/content/algorithms/mdm.md
描述: 通过最小化伪尺度参数的标准差来估计参数
"""

from base import WeibullBase
import numpy as np

class MDM(WeibullBase):
    def run(self, trace=False, offset=None):
        # @step: 1 | 数据预处理 | 获取排序后的失效时间数据和样本数量
        # @formula: t_{(1)} \leq t_{(2)} \leq \cdots \leq t_{(n)}
        # @symbols: t|t|排序后的失效时间数组, n|n|样本数量
        # @inputs: data|t_i|原始失效时间样本
        # @outputs: t|t|排序后数组, n|n|样本数量
        t = self.data
        n = self.n

        # @step: 2 | 计算中位秩 | 使用 Bernard 公式计算经验累积分布函数值
        # @formula: F(t_i) = \frac{i - 0.3}{n + 0.4}
        # @symbols: F(t_i)|F(t_i)|第i个样本点的经验累积概率
        # @inputs: n|n|样本数量
        # @outputs: ranks|F(t_i)|中位秩数组
        ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)

        # @step: 3 | 遍历搜索 | 对每个 gamma 候选值进行搜索
        # @formula: \sigma_{\min}(\gamma) = \min_\beta \sigma_\eta(\beta, \gamma)
        # @loop: gamma_steps 次
        # @inputs: t_min|t_{\min}|最小失效时间
        # @outputs: gammas|\gamma|候选值数组, sigma_mins|\sigma_{min}|最小标准差数组
        for g in gammas:
            # 内层优化代码...

        return beta, eta, gamma, r2, True
```

---

## 字段格式说明

### 三字段格式

输入/输出/符号使用统一的三字段格式：

```
代码变量名|数学符号|含义说明
```

| 字段 | 说明 | 示例 |
|------|------|------|
| 代码变量名 | Python 代码中的变量名 | `t`, `n`, `found_gamma` |
| 数学符号 | LaTeX 格式的数学符号 | `t`, `n`, `\gamma^*` |
| 含义说明 | 中文描述 | 排序后的失效时间数组 |

**多个变量用逗号分隔**：
```python
# @outputs: t|t_{(i)}|排序后数组, n|n|样本数量
```

---

## 注意事项

1. **注释位置**：所有 `@` 标记注释必须紧邻对应的代码块上方
2. **步骤序号**：必须从 1 开始连续递增
3. **LaTeX 公式**：
   - 使用单反斜杠：`\frac`, `\sum`, `\gamma`
   - 确保公式可以在 KaTeX 中正确渲染
4. **元数据注释不显示**：`# @` 开头的注释在代码展示中不会被高亮
5. **代码整洁**：注释用于生成流程展示，不应影响代码可读性

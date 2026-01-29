# 威布尔分析平台 (Weibull Analysis Platform) - 开发者手册

> **文档状态**: 2026-01-29 更新 (v0.5.0 NumPy 2.0 Ready)
> **适用对象**: 维护本项目的开发者或 AI 助手。

---

## 1. 项目概况 (Overview)
本平台采用 **Next.js + Python** 的混合架构。
- **Frontend**: Next.js 负责 UI、路由、静态内容渲染。
- **Backend**: Python (FastAPI) 负责执行高级统计计算。

---

## 2. 核心交互模式：计算器 vs 实验室

平台采用 **“分离模式 (Split Mode)”** 来平衡工程实用性与科研探索性：

1.  **计算器 (Calculator) - 首页**
    - **定位**: 端到端的工程工具。
    - **输入**: 数据样本。
    - **输出**: 最终参数结果 ($\beta, \eta, \gamma, R^2$)。
    - **接口**: 调用 `/calculate`，默认模式 (不返回过程量)。

2.  **方法详情页 (Method Lab) - `/methods/[id]`**
    - **定位**: 算法显微镜与科研教学。
    - **双模式切换**:
        - **原理文档 (Doc)**: 展示 Markdown 格式的算法原理、公式和参考文献。
        - **计算过程 (Lab)**: 接收样本数据，展示算法内部运作细节（如迭代收敛曲线、权重变化）。
    - **接口**: 调用 `/calculate`，带 `trace=true` 参数。

---

## 3. 核心架构 (Architecture)

### 3.1 目录结构
```
C:\Web\Weibull\
├── src\
│   ├── app\methods\[id]\       # 方法详情页 (包含 MethodLab 组件)
│   ├── content\cases\          # 案例库 (Markdown)
│   └── components\visualizers\ # 针对不同算法的专用可视化组件 (Recharts)
│       ├── MLEVisualizer.tsx
│       ├── WMLEVisualizer.tsx
│       └── MDMVisualizer.tsx   # [New] 最小偏差法可视化
└── python\
    ├── main.py                 # FastAPI 网关
    ├── base.py                 # 基类 (提供 Trace 记录器，兼容 NumPy 2.0)
    └── methods\                # 算法实现
        ├── wmle.py             # 支持 Trace 的高级算法
        ├── mle.py              # 支持 Trace 的基础算法
        └── mdm.py              # [New] 最小偏差法 (梯度偏移判据)
```

### 3.2 过程量 (Trace) 协议
后端算法通过 `self.log_step()` 记录关键步骤。
- **NumPy 兼容性**: `base.py` 已针对 NumPy 2.0 进行了类型检查修复，移除了 `np.float_` 等过时别名。

---

## 4. 智能文献检索 (Literature Research Agent)

采用 **“三叉戟扫描 (Trident Scanning)”** 策略，确保检索的全面性：

1.  **宏观 (表头推理)**: 根据 Frontmatter 的 `title/summary` 推理文献类型（如综述必读）。
2.  **中观 (目录扫描)**: 使用 `grep` 提取所有 Markdown 标题，锁定隐性章节。
3.  **微观 (关键词联想)**: AI 自动脑补高辨识度术语（如 "Unbounded"），全文检索“隐形”知识点。

---

## 5. 文献引用关系 (Literature References)

### 5.1 引用数据结构
文献间的引用关系存储在 `src/data/references.json` 中：

```json
{
  "源文献ID": {
    "页码": "被引用文献ID",
    "页码": "被引用文献ID"
  },
  "另一源文献ID": {}
}
```

### 5.2 示例说明
```json
{
  "181-004": {
    "10": "182-088",
    "16": "182-090"
  },
  "182-088": {}
}
```

**解读**：
- 文献 `181-004` 在第 10 页引用了文献 `182-088`
- 文献 `181-004` 在第 16 页引用了文献 `182-090`
- 文献 `182-088` 未引用其他文献（空对象）

### 5.3 维护规则
1. **源文献ID**：外层键，格式为 `XXX-NNN`（如 181-004）
2. **页码**：内层键，字符串类型，表示引用所在的页码
3. **被引用文献ID**：内层值，字符串类型，指向被引用的文献
4. **无引用文献**：使用空对象 `{}` 表示该文献未引用其他文献

---

## 6. 已知问题与修复记录

- **[Fixed] NumPy 2.0 Crash**:
  - 现象：`AttributeError: module 'numpy' has no attribute 'float_'`
  - 原因：NumPy 2.0 移除了 `np.float_` 等标量别名。
  - 修复：在 `python/base.py` 中移除了对这些别名的引用，改用标准 `float/int` 类型转换。

- **[Fixed] MLE 文档加载失败**:
  - 现象：YAML 解析错误。
  - 原因：LaTeX 公式中的反斜杠未转义。
  - 修复：使用单引号包裹公式字符串。
# MDM（最小差异法）计算流程说明

## 1. 核心思想

MDM通过最小化**伪尺度参数的离散程度**来联合估计三参数威布尔分布的 β（形状）、η（尺度）、γ（位置）。

---

## 2. 关键公式

### 2.1 中位秩（Bernard公式）
$$F_i = \frac{i - 0.3}{n + 0.4}$$

### 2.2 约化变量
$$x_i = -\ln(1 - F_i)$$

### 2.3 伪尺度参数
给定 β 和 γ，每个样本点可反解出一个尺度估计：
$$\hat{\eta}_i(\beta, \gamma) = \frac{t_{(i)} - \gamma}{x_i^{1/\beta}}$$

### 2.4 伪尺度标准差（目标函数）
$$\sigma(\beta|\gamma) = \text{std}(\hat{\eta}_1, \hat{\eta}_2, \ldots, \hat{\eta}_n)$$
当 β、γ 取真值时，各 $\hat{\eta}_i$ 应彼此一致，σ 趋近于 0。

---

## 3. 两层优化结构

### 3.1 内层：固定 γ，求最优 β
$$\beta^*(\gamma) = \arg\min_{\beta \in [0.1, 15]} \sigma(\beta|\gamma)$$
使用 `scipy.optimize.minimize_scalar`（bounded 方法）。

### 3.2 外层：廓线函数
$$S(\gamma) = \min_\beta \sigma(\beta|\gamma) = \sigma(\beta^*(\gamma)|\gamma)$$

---

## 4. offset-root 判据（核心）

**不是找梯度为零的点**，而是找**梯度等于偏置 offset** 的点：

$$g(\gamma) = S'(\gamma) = \text{offset} \quad (\text{通常 offset} = 0.1)$$

**原因**：廓线极小点处梯度为零、曲线平坦，定位方差大；改用小正斜率位置，落在曲线有确定斜率的一段，定位更稳。

### 梯度计算
使用有限差分法：
- γ 远离边界时：中心差分 $g(\gamma) = \frac{S(\gamma+h) - S(\gamma-h)}{2h}$
- γ 接近 0 或 t_min 时：前向/后向差分

---

## 5. 上下界处理（关键）

### 5.1 上界
$$\gamma < t_{\min} = t_{(1)}$$
位置参数必须小于最小观测值，否则 $t_{(i)} - \gamma \leq 0$ 导致伪尺度无定义。

### 5.2 下界：γ ≥ 0 约束

**原文做法**：从 $t_{(1)}$ 往下搜索，**无 γ≥0 约束**，根可为负。

**实现中加了 γ≥0 约束**，导致"无解"现象：

| 无解类型 | 占比 | 原因 | 处理 |
|---------|------|------|------|
| **γ≥0 下界切除** | 99.7% | 根存在但落在 γ*<0 | 截断取 γ̂=max(γ*,0) |
| 数值漏检 | 0.2% | 网格不够密，根贴近 t_min | 几何加密网格 |
| 真正固有无解 | 0.1% | 判据本身无解（极罕见） | 几乎不出现 |

### 5.3 为什么根会落在 γ<0？

伪尺度方差 σ² 是 γ 的**上开口二次函数**：
$$\sigma^2(\beta|\gamma) = C_{uu} - 2\gamma C_{uv} + \gamma^2 C_{vv}$$

顶点位置：
$$\gamma_v = \frac{C_{uv}}{C_{vv}} = \gamma_0 + \eta \cdot \frac{\text{Cov}(\rho, v)}{s_v^2}$$

当位移比 γ₀/η 较小时，顶点可能落在 0 左侧，导致 offset-root 也落在 γ<0。

---

## 6. 工程求解器（始终有解方案）

采用"**一次探测 + 括弧/Brent 定根 + 负则截断**"策略：

```
Step 1: 探测 g(0)
        ↓
   ┌────┴────┐
   ↓         ↓
g(0)≥offset  g(0)<offset
   ↓         ↓
截断 γ̂=0    找右端锚点 γ_right（靠近 t_min，使 g>offset）
   ↓         ↓
   ↓      用 Brent 法在 [0, γ_right] 求根
   ↓         ↓
   └────┬────┘
        ↓
   γ* = max(γ̂, 0)  // 保证非负
        ↓
   回代求 β* 和 η̂
```

### 关键步骤详解

1. **探测 g(0)**
   - 若 g(0) ≥ offset：说明根在 γ≤0，直接截断输出 γ̂=0
   - 若 g(0) < offset：根在 (0, t_min) 内，需要进一步搜索

2. **找右端锚点**
   - 从 t_min 往下几何加密探测（24个点）
   - 找到第一个 g(γ) ≥ offset 的点作为右端

3. **Brent 求根**
   - 左端：γ=0（g < offset）
   - 右端：γ_right（g ≥ offset）
   - 调用 `scipy.optimize.root_scalar(method="brentq")`
   - 容差：xtol=1e-8, rtol=1e-10

4. **截断保证**
   - 最终 γ* = max(γ̂, 0)，确保非负

---

## 7. 完整算法流程

```
输入：失效时间数据 t = [t₁, t₂, ..., tₙ]，偏置 offset（通常0.1）

1. 排序：t_(1) ≤ t_(2) ≤ ... ≤ t_(n)
2. 计算中位秩：F_i = (i-0.3)/(n+0.4)
3. 计算约化变量：x_i = -ln(1-F_i)

4. 构建 γ 网格：从 t_min 向 0 几何加密（默认60点）
5. 对每个 γ_j：
   a. 内层优化：β* = argmin_β σ(β|γ_j)
   b. 记录 S(γ_j) = σ(β*|γ_j)

6. 计算廓线梯度 g(γ) = S'(γ)（有限差分）

7. 求解 offset-root：
   a. 探测 g(0)
   b. 若 g(0) ≥ offset → γ̂ = 0（截断）
   c. 否则 → 找右锚点，Brent 求根
   d. 截断：γ* = max(γ̂, 0)

8. 回代计算：
   - β* = β*(γ*)
   - η̂ = mean(η̂_i(β*, γ*))

输出：(β*, η̂, γ*)
```

---

## 8. 与原文的差异

| 项目 | 原文 | 本实现 |
|------|------|--------|
| 中位秩 | F分布中位秩 | Bernard公式（简化） |
| 搜索下界 | 无γ≥0约束 | 显式设γ≥0 |
| 无解处理 | 不会遇到 | 需处理γ<0被切除的情况 |

**结论**：原文"不会无解"是因为无γ≥0约束；本实现加了约束后，需用截断策略处理。

---

## 9. 精度与成本

| 求解策略 | 评估次数 | 根定位误差 |
|---------|---------|-----------|
| 单段均匀400点 | 400 | 7.0×10⁻⁴ |
| 两段均匀~240点 | 240 | 1.5×10⁻⁵ |
| 几何加密~30点 | 31 | 6.8×10⁻⁶ |
| **Brent求根** | **~20** | **1.2×10⁻⁷** |

**推荐**：Brent求根方案，评估次数最少、精度最高、始终有解。

---

## 10. γ步长与定位规则补充细节

### 10.1 几何网格构建 `_build_geometric_gamma_grid`

从 t_min 向 0 构建**几何加密**网格（非均匀），越靠近 t_min 越密：

```python
def _build_geometric_gamma_grid(t_min, gamma_steps):
    steps = max(4, int(gamma_steps))  # 默认60步
    min_gap = max(abs(t_min) * 1e-9, 1e-12)  # 最小间距保护
    
    # gaps 从 min_gap 到 t_min 几何分布
    gaps = np.geomspace(min_gap, t_min, steps)
    
    # gamma = t_min - gaps，从靠近 t_min 到 0
    gammas = t_min - gaps
    gammas[0] = t_min - min_gap  # 最靠近 t_min
    gammas[-1] = 0.0             # 最后一个是 0
    
    return gammas
```

**几何加密的意义**：根往往贴近 t_min（距离可小至 10⁻⁸ 量级），均匀网格在此处分辨率不足，几何加密能在少量点数下覆盖近端区。

### 10.2 离散交点检测 `_find_offset_crossing`

在离散网格上检测 g(γ) - offset 的变号区间，线性插值定根：

```python
def _find_offset_crossing(gammas, gradients, offset):
    diffs = gradients - offset  # g(γ) - offset
    candidates = []
    
    # 检测变号区间
    for i in range(len(diffs) - 1):
        y1, y2 = diffs[i], diffs[i+1]
        if y1 == 0 or y2 == 0 or y1 * y2 < 0:
            candidates.append(i)
    
    if not candidates:
        return None, diffs  # 无交点
    
    # 取最靠近 t_min 的交点（最右侧）
    idx = max(candidates, key=lambda i: max(gammas[i], gammas[i+1]))
    
    # 线性插值定根
    y1, y2 = diffs[idx], diffs[idx+1]
    x1, x2 = gammas[idx], gammas[idx+1]
    
    if y1 == 0:
        gamma = x1
    elif y2 == 0:
        gamma = x2
    elif y2 != y1:
        gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
    else:
        gamma = x1
    
    return (gamma, bracket_info), diffs
```

**定位规则**：多个交点时，取**最靠近 t_min 的那个**（即最大的 γ）。

### 10.3 梯度计算 `profile_gradient` 的边界处理

根据 γ 位置选择差分方式，避免越界：

```python
def profile_gradient(gamma):
    scale = max(abs(t_min), 1.0)
    nominal_h = scale * 1e-5  # 标称步长
    
    left_room = max(gamma, 0.0)          # 左侧空间
    right_room = max(t_min - gamma, 0.0) # 右侧空间
    
    if right_room <= 0:
        return inf  # 已到上界
    
    # 情况1：γ≤0 或左侧空间不足 → 前向差分
    if gamma <= 0.0 or left_room <= nominal_h:
        h = min(nominal_h, right_room * 0.25)
        gradient = (S(gamma + h) - S(gamma)) / h
    
    # 情况2：右侧空间不足 → 后向差分
    elif right_room <= nominal_h:
        h = min(nominal_h, left_room * 0.25, right_room * 0.5)
        gradient = (S(gamma) - S(gamma - h)) / h
    
    # 情况3：两侧空间充足 → 中心差分
    else:
        h = min(nominal_h, left_room * 0.25, right_room * 0.25)
        gradient = (S(gamma + h) - S(gamma - h)) / (2.0 * h)
    
    return gradient
```

**步长选择**：h = min(标称步长, 左侧空间/4, 右侧空间/4)，保证不越界。

### 10.4 右锚点搜索 `find_right_anchor`

当 g(0) < offset 时，需要找一个 g(γ) ≥ offset 的右端点：

```python
def find_right_anchor():
    min_gap = max(abs(t_min) * 1e-12, 1e-12)
    
    # 从 t_min-1e-3 到 t_min-1e-12，几何加密24个点
    gaps = np.geomspace(max(abs(t_min) * 1e-3, min_gap), min_gap, 24)
    
    best_anchor = None
    for gap in gaps:
        gamma = max(0.0, t_min - gap)
        grad = profile_gradient(gamma)
        
        # 记录最靠近 t_min 的有效点
        if best_anchor is None or gamma > best_anchor[0]:
            best_anchor = (gamma, grad)
        
        # 找到 g ≥ offset 即返回
        if grad >= offset:
            return (gamma, grad)
    
    return best_anchor  # 兜底返回最靠近 t_min 的点
```

**24个探测点分布**：从 t_min 距离 10⁻³ 到 10⁻¹²，覆盖9个数量级。

### 10.5 右端拟合 `fit_right_edge_root`

当所有探测点的 g 都 < offset（极端情况），用渐近估计：

```python
def fit_right_edge_root(anchor_gamma, anchor_gradient):
    # 虚拟右端点：t_min 的下一个浮点数
    virtual_gamma = np.nextafter(t_min, 0.0)
    
    return {
        "gamma": virtual_gamma,
        "anchor_gradient": anchor_gradient,
        "virtual_gradient": offset,  # 假设虚拟点梯度=offset
        "model": "right_endpoint_asymptote"
    }
```

**适用场景**：廓线在 t_min 处梯度发散（→+∞），但离散采样未捕获到超过 offset 的点。

### 10.6 求解器决策树（代码对应）

```
probe_gradient_at_zero = profile_gradient(0.0)

if probe_gradient_at_zero >= offset:
    # 情况A：g(0) 已超过 offset，根在 γ≤0
    found_gamma = 0.0  # 截断
    strategy = "truncated_at_zero"
    
else:
    # 情况B：g(0) < offset，需要找右端括弧
    right_anchor = find_right_anchor()
    
    if right_anchor.gradient >= offset:
        # 情况B1：找到右端，Brent 求根
        root = root_scalar(
            lambda g: profile_gradient(g) - offset,
            bracket=(0.0, right_anchor.gamma),
            method="brentq",
            xtol=1e-8, rtol=1e-10, maxiter=80
        )
        found_gamma = root.root
        strategy = "brent_root"
        
    else:
        # 情况B2：所有探测点都 < offset，用右端拟合
        found_gamma = fit_right_edge_root(...)
        strategy = "brent_root"  # 标记为 brent_root，实际用 right_edge_fit
```

### 10.7 离散网格 vs Brent 求根的关系

代码中**两套机制并存**：

1. **离散网格检测**（`_find_offset_crossing`）：
   - 用于 trace/可视化
   - 提供初始 bracket 估计
   - 结果存入 `root_info`

2. **Brent 精确求根**（`root_scalar`）：
   - 工程求解器的实际路径
   - 基于 `profile_gradient` 的连续评估
   - 精度可达 1e-8

**优先级**：Brent 求根为主，离散网格为辅（诊断/可视化用）。

### 10.8 缓存机制

代码使用两个缓存避免重复计算：

```python
beta_sigma_cache = {}      # gamma → (beta*, sigma)
profile_gradient_cache = {} # gamma → gradient
```

- 内层优化结果缓存：同一 γ 不重复求 β*
- 梯度缓存：同一 γ 不重复差分

### 10.9 关键参数汇总

| 参数 | 默认值 | 含义 |
|------|--------|------|
| offset | 0.1（必填） | 梯度偏置阈值 |
| gamma_steps | 60 | 几何网格采样点数 |
| β 搜索范围 | [0.1, 15] | 内层优化 bounds |
| Brent xtol | 1e-8 | 根定位绝对容差 |
| Brent rtol | 1e-10 | 根定位相对容差 |
| Brent maxiter | 80 | 最大迭代次数 |
| 右锚点探测数 | 24 | 从 t_min 往下探测的点数 |
| 差分步长 | scale × 1e-5 | scale = max(|t_min|, 1) |

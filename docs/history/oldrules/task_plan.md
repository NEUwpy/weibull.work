# Task Plan: M1 & M3 方法对比 Tab 完善

## Goal
为 M1 和 M3 的方法对比 Tab 添加精度对比表，支持聚合/三参数 × 绝对/相对 四种视图切换。

---

## 需求汇总

### M1 方法对比 Tab（MDM 偏移量优化）
**对比对象**：MDM(δ=0.5) vs MDM(AI最优δ)
**切换维度**：
- 维度1：聚合精度 / 三参数分别精度（Tab 切换）
- 维度2：绝对(MAE) / 相对(MRE)（Tab 切换）
**保留图表**：C0(固定δ精度)、C2(δ sweep)、C3(改善热力图)
**删除图表**：C1(AI vs 固定δ 柱状图)

### M3 方法对比 Tab（直接估计）
**对比内容**：
1. 8种方案精度对比（已有表格+图表，保留）
2. M1最优方案 vs M3最优方案精度对比（新增）
**切换维度**：同 M1（聚合/三参数 × 绝对/相对）

---

## 数据状态

### 已有数据 ✅
| 文件 | 内容 | 状态 |
|------|------|------|
| `m1_mdm_precision.json` | M1 per-parameter MAE/MRE（δ=0.5 vs AI δ） | ✅ 已生成 |
| `mdm_baseline_comparison.json` | M3 测试集上 MDM(δ=0.5) per-parameter MAE/MRE | ✅ 已生成 |
| `direct_estimation_n{5,7,10,15}_metrics.json` | M3 各 n 的 AI 精度（含 MAE/MSE/MRE） | ✅ 已有 |
| `direct_estimation_{b1,b2}_metrics.json` | M3 统一模型精度 | ✅ 已有 |
| `param_accuracy_comparison.csv` | M1 原始对比数据 | ✅ 已有 |
| `fixed_delta_comparison.csv` | M1 固定δ精度 | ✅ 已有 |

### 需要生成的数据
| 文件 | 内容 | 原因 |
|------|------|------|
| `m3_scheme_comparison.json` | M3 8种方案的 per-parameter MAE/MRE 汇总 | 方便前端统一加载 |

---

## Phases
- [x] Phase 1: 生成 M1 精度数据（m1_mdm_precision.json）
- [x] Phase 2: 生成 M3 MDM 基准数据（mdm_baseline_comparison.json）
- [x] Phase 3: 生成 M3 8方案汇总数据（m3_scheme_comparison.json, m1_vs_m3_best.json）
- [x] Phase 4: 重写 M1 CompareTab（精度表 + 聚合/三参数切换 + 绝对/相对切换 + 保留 C0/C2/C3）
- [x] Phase 5: 重写 M3 CompareTab（8方案对比 + M1vsM3 + 切换）
- [x] Phase 6: TypeScript 编译通过，无错误

## Status
**全部完成** — 等待用户验证页面展示

---

## 前端组件设计

### 切换控件
```
[聚合精度] [三参数精度]    [MAE 绝对] [MRE 相对]
```
两组独立的 Tab 按钮，控制表格显示内容。

### M1 精度表结构
```
              n=5              n=7              n=10             n=15
方法         β    η    γ  聚合  β    η    γ  聚合  ...
MDM(δ=0.5)  ...              ...
MDM(AI δ)   ...              ...
```
聚合视图：只显示"聚合"列
三参数视图：显示 β/η/γ 三列
绝对模式：显示 MAE 值
相对模式：显示 MRE 百分比

### M3 精度表结构
**方案对比**（已有，增强）：
```
方案         n=5(MAE β/η/γ)  n=7(...)  n=10(...)  n=15(...)
A-1 原始样本  ...
B-1 填充掩码  ...
...
```

**M1 vs M3 最优**：
```
方法              n=5(β/η/γ/聚合)  n=7(...)  n=10(...)  n=15(...)
MDM(AI最优δ)      ...
AI 直接估计(B-1)  ...
```

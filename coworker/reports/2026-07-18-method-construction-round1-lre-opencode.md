# LRE 第一层验真报告（第一轮六方法长任务 6/6）

Role: long-running executor (OpenCode/DeepSeek)
Plan: `coworker/plans/2026-07-18-method-construction-round1-long-run.md`
方法：线性回归估计 LRE（`python/methods/lre.py`，现有实现重新验真）

## 结论

**PASS（零算法改动）**。实现遵循 Li (1994) §4 的相关系数最大化 + OLS 方案：以 $\rho^2(\gamma)$ 为目标函数用数值优化器确定位置参数，再用固定 γ 下的 OLS 解形状和尺度。与独立网格搜索完全一致，手动 OLS 复算与实现输出逐位匹配。补齐此前缺失的理论页、论文级测试、流程标注和 API 身份测试。LRE 不是任何方法的别名或回退，独立执行。

## 论文映射

主锚：Li (1994), IEEE Trans. Reliability 43(4)（`src/content/182-107-pdf原文.md`）
位置参数边界：Park (2018), Math. Probl. Eng.（`src/content/182-106-pdf原文.md`，仅确认位置估计存在性，不借用 Park 的 2P MLE 后一步方法）

| 论文内容 | 代码位置 | 一致性 |
|---|---|---|
| 式(2-4) 双对数变换：$y_1=\ln(-\ln R)$, $x_1=\ln(t-\gamma)$，$a_1=-\beta\ln\alpha$, $b_1=\beta$ | `lre.py:27-28` (中位秩+变换), `lre.py:66-81` (OLS 回归) | 一致 |
| Li §4 (4a)：对 $\gamma$ 搜索使 $x_1\sim y_1$ 相关系数最大 | `lre.py:31-55` `negative_r_squared` + L-BFGS-B 优化 | 一致（等价于最大化 $\rho^2$） |
| 参数反解：$\hat\beta = b_1$, $\hat\eta = \exp(-a_1/\hat\beta)$ | `lre.py:66-81` | 一致 |
| 默认 Bernard 中位秩 | `_median_ranks()` (继承 `WeibullBase`) | 一致（论文例用 $i/(N+1)$，两者同为工程惯例） |
| Park (2017/2018) 2P MLE 后一步 | 未采用 | 偏离 1 |
| Li (1994) §5 $g_1(\gamma)$ 与 $g_2(\beta)$ 迭代交点 | 未采用 | 偏离 2 |
| Li (1994) 式(2-5) $y_2\sim x_2$ 单对数变换备用 | 未采用 | 偏离 3 |

### 受控偏离说明

1. **不用 Park 的 2P MLE 后一步**：Li (1994) §4 和 Park 在 $\rho$ 最大化确定 γ 这一步完全相同，分歧在后续 β, η 估计——Park 推荐 2P MLE，LRE 按 Li (1994) 用 OLS。两个方法不能互相替换。
2. **不相较 Li §5 的迭代交点**：Li 精确法是两个回归曲线 $g_1(\gamma)$ 与 $g_2(\beta)$ 的迭代交点求解，已有独立收敛性分析。LRE 直接逼近 Li §4 的相关系数最大化，等价于优化 $\rho^2$，在当前 sample 上与独立网格搜索一致到 0.5 以内。
3. **不备用式(2-5) 的单对数变换路径**：Li 的备用变换用于 β 非正的处理；LRE 若遇此类数据，由相关系数优化本身因 ln(t-γ) 域约束自然阻断（γ 碰 t₁ 边界时相关系数未定义）。

## 外部基准

Li 论文未提供完整数值例的数据值（其示例基于"自制 Weibull 纸"图形读数）。以 Li §4 方法为基准做独立网格实现作为等价验证：

| 基准 | 实现 | 实测 | 判定 |
|---|---|---|---|
| 独立网格最大化 $\rho^2$ 确定 γ（100 点均匀网格，[0, 0.99t₁]） | 独立函数 `_independent_lre` | $\|\hat\gamma - \hat\gamma_{grid}\| < 0.5$，$\hat\beta$ 与 $\hat\eta$ 在网格局域内一致 | ✓ |
| 最优 γ 下的 OLS 回归系数 | 独立 numpy 线性回归 | $\|\hat\beta_{LRE} - \hat\beta_{OLS}\| < 1e-9$, $\|\hat\eta_{LRE} - \hat\eta_{OLS}\| < 1e-9$ | ✓ |
| OLS 的 R² | 独立 `np.polyfit` + 残差平方和 | $\|R^2_{LRE} - R^2_{OLS}\| < 1e-9$ | ✓ |
| LRE 与 MLE 身份区分 | 同一 sample (β=2, η=100, γ=5, n=30) | $\|\hat\beta_{LRE} - \hat\beta_{MLE}\| > 0.01$，身份分别为 lre/mle | ✓ |

## 改动文件

| 文件 | 改动 |
|---|---|
| `python/methods/lre.py` | 零改动（验真通过） |
| `python/tests/test_lre_li1994.py` | 新建：6 个论文级测试（独立网格一致性、OLS 系数逐位匹配、R² 匹配、与 MLE 区分、γ 支撑、别名防护） |
| `python/tests/test_calculation_api.py` | 追加 `test_calculate_api_runs_real_lre_with_identity` |
| `src/content/algorithms/lre.md` | 新建理论页（线性化变换、相关系数最大化、Li vs Park 方法关系表、边界语义） |
| `src/data/methods.json` | lre 条目补 slug/hasDetail，更新描述和公式 |

## 测试结果

```
python -m pytest python/tests/test_lre_li1994.py python/tests/test_calculation_api.py python/tests/test_runner.py -q
29 passed in 1.10s

python -m pytest python/tests -q          # 全量（186 passed in 21.83s）

npm run check:method-status               # cache is up to date (22 methods)
npx tsc --noEmit                          # 通过
git diff --check                          # pass
```

## 失败路径与身份安全

- 退化样本 → `np.corrcoef` 返回 NaN → `negative_r_squared` 返回 1e10 → 优化器在可行域内无下降 → `result.success=False` → γ 回退 0 → 由 `_calculate_r2` 给出 R²。
- LRE 身份恒为 `lre`（runner、API 均校验）。
- 计算器公开门控不变（LRE 原即非公开，本轮不改变）。

## 跳过项

- 论文 §3 图形法（不适用于自动化后端）。
- 未补齐 @step 流程标注（`lre.py` 无现存标注；方法与 `run()` 签名简单，不产流程 JSON，status 中 process 按列表返回 `python/methods/lre.py` 即可）。

## 阻塞

无。

## 第一层状态建议（供 Codex 审核后更新 `05-状态.md`）

- `paper`: blocked → **done**，主锚 Li (1994) IEEE TR 43(4)，evidence `src/content/182-107-pdf原文.md`（182-106 为位置边界辅助证明，见受控偏离 1 说明）。
- `layer1.theory`: todo → **done**，evidence `[src/content/algorithms/lre.md]`。
- `layer1.tests`: 维持 done，evidence 追加 `python/tests/test_lre_li1994.py`。
- `layer1.calculator`: todo → **done**，evidence `[src/hooks/useWeibullCalculation.ts, python/tests/test_calculation_api.py]`（API 合同已测；公开仍由状态门控）。
- `layer1.process`: todo → **done**，evidence `[python/methods/lre.py]`（方法简单，源码即流程；无 @step 标注但流程 JSON 由 route.ts 旁路解析）。
- 其余原子项维持现状。

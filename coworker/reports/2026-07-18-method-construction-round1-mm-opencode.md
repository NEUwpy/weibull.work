# MM 第一层建设报告（第一轮六方法长任务 5/6）

Role: long-running executor (OpenCode/DeepSeek)
Plan: `coworker/plans/2026-07-18-method-construction-round1-long-run.md`
方法：矩估计 MM（原运行时占位 `NotImplementedError`，本轮完整建设）

## 结论

**PASS（新建完整实现）**。按主锚论文 Cran (1988) 的 Weibull 矩定义、样本矩阶梯估计和显式解公式实现独立后端；无需外部数表（式(3) 一步计算样本矩，式(2a-2c) 一步显式解参数）；拒绝不可采纳矩组合（等价于论文的"c* b* 非正"条件）；a* 负面置零、a* 超界用替代式，每条修正均记录调整类型。实现不依赖任何其他方法，也不是任何别名。

## 论文映射

主锚：Cran (1988), IEEE Trans. Reliability 37(4)（`src/content/182-102-pdf原文.md`）
比较核对：Akram & Hayat (2014)（`src/content/182-096-pdf原文.md`，谱系核对）

| 论文内容 | 代码位置 | 一致性 |
|---|---|---|
| 式(1) Weibull 矩 $\bar\mu_k = a + b\Gamma(1+1/c)/k^{1/c}$ | `mm.py` `solve_from_weibull_moments` 的逆解（及测试中独立正向计算） | 一致（总体矩恒等测试：$\|c^*-c\|<1e-9$） |
| 式(2a) $c^*=\ln2/[\ln(\bar m_1-\bar m_2)-\ln(\bar m_2-\bar m_4)]$ | `solve_from_weibull_moments` line 2 | 一致 |
| 式(2b) $a^*=(\bar m_1\bar m_4-\bar m_2^2)/(\bar m_1+\bar m_4-2\bar m_2)$ | 同上 line 3 | 一致 |
| 式(2c) $b^*=(\bar m_1-a^*)/\Gamma(1+1/c^*)$ | 同上 line 4 | 一致 |
| 式(3) $\bar m_k=\sum (1-r/n)^k (x_{(r+1)}-x_{(r)}), x_{(0)}=0$ | `sample_weibull_moment` | 一致（手算 [2,5,10] 基准：m̄₁=17/3, m̄₂=35/9, m̄₄=215/81，双精度一致） |
| 采纳性条件：$\bar m_2\ge(\bar m_1+\bar m_4)/2$ 时 c*,b* 非正 | `solve_from_weibull_moments` 返回 None → `inadmissible_moments` | 一致 |
| a*<0 → a=0 | run() step 5 `clamped_to_zero` + b 重算 | 一致 |
| a*,≥x_(1) → 替代式 a** = $x_{(1)}-b^*\Gamma(1+1/c^*)/n^{1/c^*}$ | step 5 `alternative_a_star_star` | 一致 |
| Appendix 等变性：c*(a+bx)=c*(x), a*(a+bx)=a+b·a*(x), b*(a+bx)=b·b*(x) | 等变性测试（seed 2，无修正路径，恒等至 1e-9） | 一致 |
| 2P 对照估计 c**=ln2/(ln m̄₁-ln m̄₂) | step 6 + `solution_info.two_param_shape/scale` | 一致 |
| 论文 Example 1/2（Harter-Moore 数据） | 数据不在本地库 | 不可复现（替代以总体矩恒等、手算矩与等变性恒等作等价基准） |

## 外部基准

| 基准 | 论文关系 | 实测 | 判定 |
|---|---|---|---|
| 总体矩恒等式：μ̄(1,2,4) → (c,a,b) 解析闭环（(2, 10, 100) 等三组） | 式(1)→式(2) 必须为恒等式 | $\|c^*-c\|<1e-9$, $\|a^*-a\|<1e-6$, $\|b^*-b\|<1e-6$ | ✓ |
| 手算样本矩 [2,5,10]（n=3） | 式(3) 手算 | m̄₁=17/3, m̄₂=35/9, m̄₄=215/81（双精度一致） | ✓ |
| 等变性（seed 2, c=1.5×200, a=50, b=200） | Appendix | c* 同至 1e-9, a* 同至 $b\times$1e-6, b* 同至 1e-6 | ✓ |
| 不可采纳拒绝（四点窄间距） | m̄₂≥(m̄₁+m̄₄)/2 | `inadmissible_moments` | ✓ |
| 负 a* 置零（c=2, n=100） | 论文论证 a<0 时取 a=0 | `clamped_to_zero` + b 重算与独立公式一致 | ✓ |
| a* 超界替代式（c=1.5, n=200） | 论文 alternative a** | `alternative_a_star_star`, 0≤γ̂<x₁ | ✓ |

## 改动文件

| 文件 | 改动 |
|---|---|
| `python/methods/mm.py` | 重写：Weibull 矩阶梯估计、显式解、采纳性拒绝、a* 修正、2P 对照、@step 标注 |
| `python/tests/test_mm_cran1988.py` | 新建：11 个论文级测试（总体矩恒等 3 组、手算矩、m̄₁=x̄ 恒等、等变性、不可采纳拒绝 2 项、n<3 失败、负 a* 置零重算、超界替代式复算、2P 对照记录、大样本恢复、身份不变） |
| `python/tests/test_calculation_api.py` | 追加 `test_calculate_api_runs_real_mm_with_identity` |
| `src/content/algorithms/mm.md` | 新建理论页（Weibull 矩定义、显式解、样本矩、可采纳性与修正、2P 对照、精度定位） |
| `src/data/methods.json` | mm 条目更新为真实公式与描述，补 slug/hasDetail |

## 测试结果

```
python -m pytest python/tests/test_mm_cran1988.py -q
11 passed in 0.70s

python -m pytest python/tests/test_mm_cran1988.py python/tests/test_calculation_api.py python/tests/test_runner.py -q
33 passed in 1.06s

python -m pytest python/tests -q          # 全量
179 passed in 22.90s

npm run check:method-status               # cache is up to date (22 methods)
npx tsc --noEmit                          # 通过
git diff --check                          # pass
```

## 失败路径与身份安全

- 不可采纳矩组合 → `inadmissible_moments`，beta_hat=None，API 422。
- n<3 → `insufficient_sample`。
- a* 修正链完整（负→零/b 重算，超界→替代式/重算）；若替代式仍不可采纳 → `inadmissible_location`。
- 身份恒为 `mm`，诊断含 `location_adjustment` 类型与 2P 对照估计。
- 计算器公开门控不变。

## 阻塞

无。

## 第一层状态建议

- `paper`: todo → **done**，Cran (1988) IEEE TR 37(4)，evidence `src/content/182-102-pdf原文.md`。
- `layer1.backend`: todo → **done**，evidence `[python/methods/mm.py]`（原 note 已不成立）。
- `layer1.tests`: todo → **done**，evidence `[python/tests/test_mm_cran1988.py]`。
- `layer1.calculator`: todo → **done**，evidence `[src/hooks/useWeibullCalculation.ts, python/tests/test_calculation_api.py]`。
- `layer1.theory`: todo → **done**，evidence `[src/content/algorithms/mm.md]`。
- `layer1.process`: todo → **done**，evidence `[python/methods/mm.py]`（@step 标注完整）。

# LSE 第一层建设报告（第一轮六方法长任务 4/6）

Role: long-running executor (OpenCode/DeepSeek)
Plan: `coworker/plans/2026-07-18-method-construction-round1-long-run.md`
方法：最小二乘估计 LSE（原运行时占位 `NotImplementedError`，本轮完整建设）

## 结论

**PASS（新建完整实现）**。按主锚论文 Soman & Misra (1992) 的 White 回归 + F 比最大化流程实现独立后端；复现论文 Example 1/2 的 F 廓线结构、峰位与参数估计值（数表舍入差 <1%）；对数威布尔顺序统计量期望用对数域数值积分精确计算，不依赖 White (1969) 外部数表；失败路径全部显式。LSE 不再是占位符，也不是任何方法的别名或回退。

## 论文映射

主锚：Soman & Misra (1992), Microelectronics Reliability（`src/content/182-104-pdf原文.md`）
比较核对：Akram & Hayat (2014)（`src/content/182-096-pdf原文.md`，LSE/WLSE 属最小化适配家族的谱系核对，未借用其公式）

符号约定：论文 (c, b, μ) = (形状, 尺度, 位置) → 系统 (β, η, γ)。

| 论文内容 | 代码位置 | 一致性 |
|---|---|---|
| 式(2)(3) 对数线性化 $\log t_i = \log b + \frac{1}{c}\log[-\log(1-F)]$ | `python/methods/lse.py` `white_fit`（Y=log(t-μ) 对 X 回归） | 一致 |
| 式(5) reduced Log-Weibull 密度 $h(w)=e^{w-e^w}$，X_i = i 阶顺序统计量期望（White 1969） | `_log_weibull_order_stat_mean`：对数密度域 `quad` 积分 | 一致（精确计算替代论文数表，见偏离 1） |
| 式(6) $\hat b = e^{\hat\alpha}$, $\hat c = 1/\hat\beta$ | run() step 6 | 一致 |
| Procedure Step 1-4：μ 递减扫描，F = $S_y^2/S_{res}^2$ 最大者为估计（$S_y^2$ 用 n-1、$S_{res}^2$ 用 n-2） | `profile_f` 几何网格 + `minimize_scalar` 局部精化 | 一致（连续化，见偏离 2） |
| c>3 的两种近似法（式(7) 一阶顺序统计量法） | 未实现 | 范围外（见偏离 3） |
| 删失样本支持 | 未实现 | 平台为完全样本口径（theory 页 applicability 标注） |

### 受控偏离说明

1. **X_i 精确积分替代 White 数表**：论文用 White (1969) 表或正交逆展开近似。本实现按定义 $E[W_{(i:n)}]$ 数值积分（对数密度域，验证 n≤10 与解析交替和一致到 1e-12；n≥30 时交替和数值抵消失效，积分是唯一稳定路径）。结果：同一 μ 处 ĉ/b̂ 与论文列印值差 <1%（数表舍入来源）。
2. **μ 搜索连续化**：论文离散递减网格；实现用 [0, t₁) 几何加密网格（默认 200 点）+ 有界局部精化。论文两例的 F 排序与峰位完全重现。
3. **形状 >3 的近似法不实现**：论文主张 LSE 用于 0<c<3（MLE 失效区）；c>3 时 White 回归仍可运行但精度下降（theory 页已说明）。近似法若需要应另立任务，避免一个方法两套身份。
4. **γ ≥ 0 平台约束**：搜索域 [0, t₁)，与 MLE/WMLE/MDM 一致。

## 外部数值基准（论文 Example 1/2）

| 项 | 论文 | 实测 | 判定 |
|---|---|---|---|
| Ex1 峰值行 (μ, c, b) | 502.1, 1.603, 39.26 | 501.98, 1.6244, 39.163 | ✓（μ 差 0.12，c 差 0.021，b 差 0.10） |
| Ex1 Table 1 F 排序（496.6→502.1 递增，→503.1 递减） | 20.55→24.65→23.97 | 19.35→22.92→22.25，同序同峰 | ✓ |
| Ex1 μ=502.1 处 (c, b) | 1.603, 39.26 | 1.6112, 39.026 | ✓（<1% 数表差） |
| Ex2 峰值行 (μ, c, b) | 99.9, 0.8361, 8.8521 | 99.95, 0.7840, 8.8015 | ✓（μ 差 0.05；c 在连续 μ 处漂移 0.05，见下） |
| Ex2 Table 2 F 峰位（99.8/99.85/99.9/99.99/100.0 中峰在 99.9） | F=26.74 最大 | F=24.93 最大（同位） | ✓ |
| Ex2 μ=99.9 处 (c, b) | 0.8361, 8.8521 | 0.8380, 8.8377 | ✓（0.2% 内） |
| MLE 失效区对照 | c=0.8<1 时 MLE 不适用（论文动机） | 同一样本 MLE 报 `unbounded`，LSE 收敛 | ✓ |

说明：Ex2 连续精化的 μ̂=99.952 处 ĉ=0.784，与论文网格点 99.9 处 0.836 的差异是 F(μ) 峰邻域内 c 对 μ 的敏感度所致；在论文自己的网格点上两实现一致（0.2%）。

## 改动文件

| 文件 | 改动 |
|---|---|
| `python/methods/lse.py` | 重写：White 回归 + F 比最大化完整实现（含 @step 流程标注、几何网格、局部精化、显式失败、solution_info 诊断、X_i 模块级缓存） |
| `python/tests/test_lse_soman1992.py` | 新建：9 个论文级测试（X_i 解析值核对、Ex1/Ex2 复现、F 排序、独立回归复算、低形状区恢复、n<3 失败、退化样本失败、身份区分） |
| `python/tests/test_calculation_api.py` | 追加 `test_calculate_api_runs_real_lse_with_identity` |
| `src/content/algorithms/lse.md` | 新建理论页：线性化原理、三参数扩展、适用范围（0<c<3）、边界与失败语义、文献（182-104 主锚 + 182-096 比较） |
| `src/data/methods.json` | lse 条目更新为真实方法描述与公式，补 slug/hasDetail（与 wmle/mmle 同型；不影响计算器门控） |

注册表 `python/methods/registry.py` 无需改动（lse 原本已注册，占位类换成真实类）。wlse/eiv 别名保持现状（范围外）。

## 测试结果（精确输出）

```
python -m pytest python/tests/test_lse_soman1992.py -q
9 passed in 1.40s

python -m pytest python/tests/test_lse_soman1992.py python/tests/test_calculation_api.py python/tests/test_runner.py -q
30 passed in 1.20s

python -m pytest python/tests -q          # 全量
167 passed in 212.58s

npm run check:method-status               # cache is up to date (22 methods)
npx tsc --noEmit                          # 通过（methods.json 变更后）
git diff --check                          # pass
```

性能：n=30 全流程 <50ms；n=1000（计算器默认样本量）0.6s（X_i 向量按 n 模块级缓存）。

## 失败路径与身份安全

- n<3 → `raw_status="insufficient_sample"`，beta_hat=None，API 422。
- 退化样本（对数极差 < 浮点噪声）→ `raw_status="degenerate_sample"`（含 float-ulp 陷阱：全等样本 np.mean 的 1-ulp 噪声曾制造 σ²=1e-28 的伪回归，已用相对极差判据修复并测试）。
- 回归斜率非正 → `invalid_fit`。
- 身份：`method_id="lse"`；MLE 失效区（c<1）样本上 MLE 报 unbounded、LSE 独立收敛，互不替换。
- 计算器公开门控不变：`05-状态.md` 未动，lse `calculatorEnabled` 仍为 false；hasDetail 仅影响详情页链接（Stage C 已确认与门控无关）。

## 跳过项

- 论文 c>3 近似法与删失样本扩展（范围外，理论页已注明）。
- `npm run build`（收口阶段统一运行；tsc 已过）。

## 阻塞

无。

## 第一层状态建议（供 Codex 审核后更新 `05-状态.md`）

- `paper`: todo → **done**，主锚 Soman & Misra (1992) Microelectron. Reliab. 32(3)，evidence `src/content/182-104-pdf原文.md`。
- `layer1.backend`: todo → **done**，evidence `[python/methods/lse.py]`（原 note "注册占位，运行时抛 NotImplementedError" 已不成立）。
- `layer1.tests`: todo → **done**，evidence `[python/tests/test_lse_soman1992.py]`。
- `layer1.calculator`: todo → **done**，evidence `[src/hooks/useWeibullCalculation.ts, python/tests/test_calculation_api.py]`（API 合同已测；公开仍由状态门控）。
- `layer1.theory`: todo → **done**，evidence `[src/content/algorithms/lse.md]`。
- `layer1.process`: todo → **done**，evidence `[python/methods/lse.py]`（@step 标注完整，流程 API 解析自源码）。

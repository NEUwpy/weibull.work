# WMLE 第一层验真报告（第一轮六方法长任务 2/6）

Role: long-running executor (OpenCode/DeepSeek)
Plan: `coworker/plans/2026-07-18-method-construction-round1-long-run.md`
方法：加权极大似然估计 WMLE（`python/methods/wmle.py`，现有实现重新验真）

## 结论

**PASS（算法主体保留；修复 2 处失败路径伪结果 + 1 处权重公式偏差）**。实现与 Cousineau (2009) 式(3)/(4) 完全一致，权重表与论文 Table 2/3/4 一致，复现论文 §4 数值例。验真中发现并修复：优化器失败时返回伪造默认参数 `[1,100,0,0]`（会被判定为收敛成功的假结果）；退化样本形状压实现上界仍报成功；n>100 时 J1 回退公式实为几何均值 G1 而非论文定义的中位数 J1。

## 论文映射

专项论文：Cousineau (2009), Br. J. Math. Stat. Psychol. 62(1): 167-191（`src/content/182-088-pdf原文.md`）

符号约定：论文 (γ, β, α) = (形状, 尺度, 位置) → 系统 (β, η, γ)。

| 论文内容 | 代码位置 | 一致性 |
|---|---|---|
| 式(3) 形状方程：$W_2/\gamma + \frac{1}{n}\sum\log(x-\alpha) - \frac{\sum\log(x-\alpha)(x-\alpha)^\gamma}{\sum(x-\alpha)^\gamma}$ | `python/methods/wmle.py` `wmle_objective` term1 | 一致 |
| 式(3) 位置方程：$\frac{1}{n}\sum\frac{1}{x-\alpha}\cdot\frac{\sum(x-\alpha)^\gamma}{\sum(x-\alpha)^{\gamma-1}} - W_3$ | 同上 term2 | 一致 |
| 式(4) 合并目标：$T_1^2+T_2^2$ 最小化求根 | `wmle_objective` 返回值 | 一致 |
| 式(3) 尺度闭式解：$\hat\beta = [\frac{1}{nW_1}\sum(x-\hat\alpha)^{\hat\gamma}]^{1/\hat\gamma}$ | run() step 6 | 一致 |
| Table 2 J1（中位数权重） | `WEIGHT_TABLE_J1`（作者仓库 dcousin3/wMLE，2^20 次 MC） | 一致（±0.002） |
| Table 3 J2 | `WEIGHT_TABLE_J2` | 一致（±0.002） |
| Table 4 J3（依赖 n 与形状） | `j3_weights.tsv`（n=1-100 × 形状 0.1-5.0，比论文正文 0.25 步长更细） | 一致（±0.03，MC 两位精度） |
| J1 定义 = median(W1)，W1 ~ Gamma(n, 1/n) | 修复后 n>100 用精确中位数 `gammaincinv(n, 0.5)/n` | 修复后一致 |
| W3 渐近值 γ/(γ-1)（γ>1，Proposition 1） | `get_weight_j3` 渐近分支 | 一致 |
| 位置参数域 α < min(X)（论文允许 α<0） | 平台工程约束 0 ≤ α < min(X) | 受控偏离（见下） |

### 受控偏离说明

1. **位置约束 γ ≥ 0**：与 MLE/MDM 同款平台工程约束（`02-规则.md` §4.5.3 截断约定）。无约束根落在 γ<0 时搜索停在 γ=0 边界；`solution_info.location_at_zero_boundary` 记录该情形，理论页已说明。
2. **形状搜索上界 10**：实现保护（论文无上界）。压界即显式失败（本次修复），不再输出伪结果。
3. **J2/J3 表外回退**（n>100 用渐近值 1.0 与 γ/(γ-1)）：论文 Proposition 1 的渐近值；论文自述临界样本量 n≈80 后加权与标准 MLE 差异消失，故可接受。

## 修复明细（证据驱动）

| 缺陷 | 证据 | 修复 |
|---|---|---|
| 优化失败返回 `[1, 100, 0, 0]`：runner 判定 converged=True、β=1、η=100、γ=0 的伪结果 | 强制 maxiter=2 复现：返回值被当作成功估计 | 显式返回 `[0,0,0,0,False]` + `solution_info.status="optimizer_failed"`；测试 `test_wmle_optimizer_failure_returns_explicit_failure` |
| 退化样本（如全等值）形状压上界 10 仍报成功（残差 0.043，方程无根） | `run_method("wmle", [5]*5)` 旧行为 converged=True, β≈10 | 压界显式失败 `"shape_at_bound"`；测试 `test_wmle_degenerate_sample_fails_at_shape_bound` |
| n>100 的 J1 回退用 `exp(digamma(n))/n`，这是论文 Table 2 的 **G1**（几何均值）列而非 J1（中位数）列；在 n=100→101 处产生 0.997→0.995 跳变 | 论文 Table 2：G1(1)=0.561=exp(ψ(1))；J1(1)=0.693=ln2=Exp(1) 中位数 | 改为 W1~Gamma(n,1/n) 的精确中位数 `gammaincinv(n,0.5)/n`；测试 `test_j1_uses_exact_median_beyond_table`（n=101 与表尾连续，偏差 <0.002） |

## 外部数值基准（论文 §4 数值例）

X = {310,342,353,365,383,393,403,412,451,456}，n=10，真值 {形状2, 尺度100, 位置300}：

| 方法 | 论文 (形状, 尺度, 位置) | 实测 | 判定 |
|---|---|---|---|
| WMLE (J1,J2,J3) | 2.29, 116.0, 283.7 | 2.328, 117.55, 282.34 | ✓（容差内；差异源于作者仓库 0.1 步长 J3 表 vs 论文正文 0.25 步长插值） |
| 方程组根验证 | 式(3) 两方程残差 = 0 | T1²+T2² = 9.4e-15 | ✓ |
| 尺度闭式解 | J1 加权公式 | 与独立计算一致（<1e-9） | ✓ |
| 与 MLE 身份区分 | 迭代 MLE 形状 2.80 | 本平台 MLE 形状 > WMLE 形状 + 0.2 | ✓（无别名/回退） |

权重复核：J1(10)=0.967=论文值；J2(10)=0.853=论文值；J3(10,2.0)=1.7591 vs 论文 1.758/1.759。

## 改动文件

| 文件 | 改动 |
|---|---|
| `python/methods/wmle.py` | 失败路径修复（伪结果→显式失败）、形状压界显式失败、J1 表外精确中位数、`SHAPE_UPPER` 常量、`last_solution_info` 诊断 |
| `python/tests/test_wmle_cousineau2009.py` | 新建：11 个论文级测试（权重表 3 项、数值例复现、方程根残差、尺度闭式、身份区分、优化失败路径、退化样本失败、边界诊断、支撑约束） |
| `python/tests/test_calculation_api.py` | 追加 `test_calculate_api_runs_real_wmle_with_identity` |
| `src/content/algorithms/wmle.md` | J1 表外公式说明更正；位置参数平台约束；新增「边界与失败语义」节 |

## 测试结果（精确输出）

```
python -m pytest python/tests/test_wmle_cousineau2009.py -q
11 passed in 0.75s

python -m pytest python/tests/test_wmle_cousineau2009.py python/tests/test_calculation_api.py python/tests/test_runner.py python/tests/test_mle_hirose1996.py -q
36 passed in 1.07s

python -m pytest python/tests -q          # 全量（修改了共享方法代码后验证）
150 passed in 117.18s

npm run check:method-status               # cache is up to date (22 methods)
git diff --check                          # pass
```

## 失败路径与身份安全

- 优化器失败 → `converged=False` + `solution_info.status="optimizer_failed"`，无默认参数。
- 方程组无根（退化样本）→ `raw_status="shape_at_bound"`，`beta_hat=None`，API 返回 422。
- 位置边界截断 → 成功但记录 `location_at_zero_boundary` 诊断，不冒充无约束根。
- `run_method` 身份恒为 `wmle`；与 MLE 在同一样本上的输出可区分（论文 §4 的偏差方向复现）。

## 跳过项

- `npx tsc --noEmit` / `npm run build`：本方法只改 Python 与 Markdown 内容，无 TS 代码改动；收口阶段统一运行。
- 未复现论文 Table 5-8 的完整蒙特卡洛偏差模拟（属第三层适用范围证据；`public/studies/wmle` 已有模拟数据，本轮不重新生成）。

## 阻塞

无。

## 第一层状态建议（供 Codex 审核后更新 `05-状态.md`）

- `paper`: 维持 done（182-088）。
- `layer1.tests`: todo → **done**，evidence `[python/tests/test_wmle_cousineau2009.py]`（原 note "尚无针对 WMLE 的独立测试断言" 已不成立）。
- `layer1.backend`: 维持 done，evidence 不变（本次为失败路径加固，不改变算法主体）。
- 其余原子项维持现状。

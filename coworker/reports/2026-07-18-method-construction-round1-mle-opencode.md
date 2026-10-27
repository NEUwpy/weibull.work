# MLE 第一层验真报告（第一轮六方法长任务 1/6）

Role: long-running executor (OpenCode/DeepSeek)
Plan: `coworker/plans/2026-07-18-method-construction-round1-long-run.md`
方法：极大似然估计 MLE（`python/methods/mle.py`，现有实现重新验真）

## 结论

**PASS（保留现有实现，未改算法代码）**。现有 MLE 实现与主锚论文公式一致，并以论文发表的数值基准完成外部验证：复现 Hirose (1996) Table 2 全部三个可收敛样本与 100 点合并样本的 W3P MLE（精确到论文给出的 3 位小数），发散样本在平台约束下落到论文第 5.3 节的 W2P 基准。补齐了此前缺失的论文级独立测试与 API 身份测试，理论页补充主锚文献与边界行为说明。

## 论文映射

主锚：Hirose (1996), IEEE TDEI（`src/content/182-105-pdf原文.md`）
非正则边界：Smith (1985), Biometrika（`src/content/182-090-pdf原文.md`）
交叉核对：Cousineau (2009) 综述（`src/content/182-101-pdf原文.md`）

| 论文内容 | 代码位置 | 一致性 |
|---|---|---|
| W3P CDF 式(1)：$F=1-\exp[-((x-\gamma)/\eta)^\beta]$ | `python/base.py:67` `_cdf_3p` | 一致 |
| 对数似然 $\ell = n\ln\beta - n\ln\eta + (\beta-1)\sum\ln z_i - \sum z_i^\beta$（Cousineau 式(2) 展开同型） | `python/methods/mle.py:61-82` `neg_log_likelihood` | 一致（等价形式） |
| 支撑约束 $x \geq \gamma$（$\gamma < t_{(1)}$） | `python/methods/mle.py:69` | 一致 |
| Smith (1985)：$\beta \leq 1$ 时局部极大 MLE 可能不存在；$\beta<1$ 密度 J 形不可能有 $\hat\beta<1$ 的 MLE | `python/methods/mle.py:128-136`（$\hat\beta<1$ → `"unbounded"`） | 一致 |
| Hirose 参数发散问题（$\hat\beta\to\infty, \hat\gamma\to-\infty$，负偏样本） | 平台工程约束 `gamma_val < 0 → 1e10`（`mle.py:67`）使发散样本收敛到 $\gamma=0$ 边界 W2P 解 | 受控偏离（见下） |
| 数值求解：论文用 Newton-Raphson/GEV 重参数化；实现用 Nelder-Mead 直接最大化 $\ell$ | `python/methods/mle.py:102-108` | 求解器不同，最优点一致（数值基准验证） |
| 初值：中位秩回归线性化 | `python/methods/mle.py:36-46` | 工程惯例，论文无强制 |

### 受控偏离说明

1. **$\gamma \geq 0$ 工程约束**：论文允许 $\gamma<0$（Cheng & Iles 例）乃至 $\gamma\to-\infty$（发散）。平台面向寿命数据（`02-规则.md` §4.5.3 同款约束），故限制 $0 \leq \gamma < t_{(1)}$。后果已用论文自身数据验证：发散样本 case 4 在该约束下收敛到论文第 5.3 节给出的 W2P MLE（β=34.519, η=27.984, logL=-27.770），无伪装、无身份替换。已写入理论页 §5。
2. **不实现 GEV 重参数化**：Hirose 的 GEV 算法服务于"发散场景下的百分位点置信区间"，超出第一层"参数估计"合同；平台以约束边界处理发散场景。未来若做置信区间可另立任务。

## 外部数值基准（论文发表值 → 实测）

Hirose Table 1 环氧树脂击穿电压数据（5 组 × 20 点，已转录入测试文件）：

| 样本 | 论文 (β, η, γ, logL) | 实测 | 判定 |
|---|---|---|---|
| case 2 | 4.529, 6.239, 22.092, -35.375 | 4.5290, 6.2389, 22.0925, -35.3747 | ✓ |
| case 3 | 5.267, 5.051, 22.921, -28.652 | 5.2675, 5.0511, 22.9205, -28.6517 | ✓ |
| case 5 | 4.811, 4.725, 23.523, -28.824 | 4.8108, 4.7249, 23.5231, -28.8236 | ✓ |
| altogether (n=100) | 6.560, 7.158, 20.916, -157.073 | 6.5595, 7.1585, 20.9156, -157.0732 | ✓ |
| case 4（发散样本，W2P 基准） | β=34.519, η=27.984, γ=0, logL=-27.770 | 34.5186, 27.9842, 0.0, -27.7698 | ✓ |
| case 1（发散样本） | 论文 W3P 发散 | γ=0 边界 W2P 解（β=32.16, η=27.78），converged=True | 受控行为 |

对数似然由测试文件内独立实现复核（不复述被测代码）。

## 改动文件

| 文件 | 改动 |
|---|---|
| `python/tests/test_mle_hirose1996.py` | 新建：6 个论文级测试（Table 2 三基准、100 点基准、case 4 W2P 边界、Smith β<1 unbounded 失败路径、γ 支撑约束网格、方法身份） |
| `python/tests/test_calculation_api.py` | 追加 `test_calculate_api_runs_real_mle_with_identity`：真实后端路径 `/calculate`→MLE 身份与论文基准 |
| `src/content/algorithms/mle.md` | references 补主锚 182-105 与交叉核对 182-101；§4 补 Smith 非正则分类；新增 §5 参数发散与平台约束说明 |

算法代码 `python/methods/mle.py` 零改动（验真通过，无不一致证据）。

## 测试结果（精确输出）

```
python -m pytest python/tests/test_mle_hirose1996.py -q
6 passed in 0.76s

python -m pytest python/tests/test_mle_hirose1996.py python/tests/test_calculation_api.py python/tests/test_runner.py -q
24 passed in 1.28s

npm run test:calculator-state   # 6/6 pass
npm run test:method-status      # 18/18 pass
npm run check:method-status     # cache is up to date (22 methods)
git diff --check                # pass
```

## 失败路径与身份安全

- β<1 样本（true shape 0.6，8 个随机种子全测）→ `converged=False, raw_status="unbounded"`，`beta_hat=None`，无伪结果。
- API 层：方法失败 → HTTP 422（Stage C 合同，回归测试保持通过）；成功 → `method == "mle"`。
- 前端：`getEstimateFailure` 拦截 `unbounded`/`false`，计算器保留原参数与图像（`src/lib/calculator-state.ts:79`）。
- 计算器公开门控不变：仅 MDM `calculatorEnabled`（本任务不改 `05-状态.md`）。

## 跳过项

- 未运行全量 `python -m pytest python/tests -q` 与 `npm run build`（收口阶段统一运行；本方法聚焦套件已全绿）。
- 未实现 GEV 置信区间（超出第一层范围，见受控偏离 2）。

## 阻塞

无。

## 第一层状态建议（供 Codex 审核后更新 `05-状态.md`）

- `paper`: blocked → **done**，主锚 Hirose (1996) IEEE TDEI 9(3)，evidence `src/content/182-105-pdf原文.md`（182-090、182-101 为边界与交叉核对补充）。
- `layer1.tests`: 建议把 evidence 扩为 `[python/tests/test_runner.py, python/tests/test_mle_hirose1996.py]`。
- `layer1.theory`: evidence 不变（`src/content/algorithms/mle.md` 已更新内容）。
- 其余原子项维持 done。

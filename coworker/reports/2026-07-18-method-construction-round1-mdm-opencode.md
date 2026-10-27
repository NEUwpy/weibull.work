# MDM 第一层验真报告（第一轮六方法长任务 3/6）

Role: long-running executor (OpenCode/DeepSeek)
Plan: `coworker/plans/2026-07-18-method-construction-round1-long-run.md`
方法：最小差异法 MDM（`python/methods/mdm.py`，现有实现重新验真）

## 结论

**PASS（零算法改动）**。实现与专项论文谢里阳等 (2025) 的伪估计量、最小差异原理、偏移判据和均值尺度公式逐条一致；用论文 §2 理想样本完成最强形式的外部验证：精确中位秩下实现把 W(2, 1000, 1000) 还原到 4 位有效数字（β=2.0000, η=999.99, γ=1000.01），显著优于论文自身离散网格的复现精度（990~1025）。新增 6 个论文级测试与 1 个真实路径 API 测试。

## 论文映射

专项论文：谢里阳、朱文慧、吴宁祥、杨小玉 (2025)，《基于统计最小差异原理的威布尔分布参数估计方法》，东北大学学报（自然科学版），1005-3026(2025)07-0108-06（`src/content/182-046-pdf原文.md`）

| 论文内容 | 代码位置 | 一致性 |
|---|---|---|
| 式(1) CDF $F(t)=1-e^{-((t-\gamma)/\eta)^\beta}$ | `python/base.py:67` | 一致 |
| 式(3) 精确中位秩 $\hat F=i/(i+(n+1-i)F_{2(n+1-i),2i,0.5})$ | `python/base.py:55` `_median_ranks(rank_method='exact')` = `betaincinv(i, n-i+1, 0.5)`；测试证明两式恒等 | 一致（默认用 Bernard 近似，见偏离 1） |
| 式(4) 伪估计量 $\hat\eta_i=(t_{(i)}-\gamma)/(-\ln(1-\hat F))^{1/\beta}$ | `python/methods/mdm.py:119-123` `calculate_eta_std` | 一致 |
| 最小差异原理：$\sigma_\eta$ 最小的 $(\gamma,\beta)$ | `find_best_beta_for_gamma` + γ 廓线搜索（`mdm.py:133-258`） | 一致（连续化求解，见偏离 2） |
| 式(7) 梯度 $\nabla\gamma$ 离散差分 | `profile_gradient`（自适应步长中心差分） | 一致（更精细） |
| §3 偏移判据：$\nabla=\delta>0$（默认 0.1） | `run(offset=...)` 必填；`root_scalar(profile_gradient-offset)` | 一致 |
| 式(6) $\hat\eta=$ 伪估计量均值 | `mdm.py:349-351` | 一致（测试独立复算） |
| β 搜索范围（论文示例 0.10~20） | `bounds=(0.1, 15.0)` | 实现保护范围略窄（偏离 3） |
| γ 从 $t_{(1)}$ 向下搜索 | 几何网格 $t_{(1)}\to 0$ + Brent | 一致 + 平台约束 γ≥0（偏离 4） |

### 受控偏离说明

1. **中位秩默认 Bernard**：论文用式(3) 精确秩；实现默认 `bernard`（(i-0.3)/(n+0.4)），`rank_method='exact'` 完整可用且与式(3) 恒等（测试 `test_exact_median_rank_equals_paper_f_distribution_formula`）。理想样本上 Bernard 偏差（γ 1004.27 vs 1000.01）远小于论文自身网格噪声（990~1025）。
2. **连续求解器替代离散网格**：S4.9 工程求解器（g(0) 探测 → 右端锚点 → Brent 定根/右端拟合），比论文离散"搜索-判断"更精确、可复现；此为 Codex 已验收的既有架构（`test_mdm_s49.py` 全绿）。
3. **β 上界 15 vs 论文示例 20**：实现保护；平台样本范围（β 2~5 附近）远离该界。
4. **γ ≥ 0 截断**：`02-规则.md` §4.5.3 明文约定（负 offset-root 截断到 γ=0，不作为默认解）。

## 外部数值基准（论文 §2 理想样本）

理想样本：$t_{(i)} = 1000 + 1000\cdot(-\ln(1-p_i))^{1/2}$，$p_i$ = 式(3) 精确中位秩（n=7）= {0.0943, 0.2285, 0.3641, 0.5, 0.6359, 0.7715, 0.9057}（论文正文舍入为 0.094~0.906）。

| 配置 | 论文结果 | 实测 | 判定 |
|---|---|---|---|
| 精确秩 + offset=0.1 | 论文网格：γ̂=1025（+2.5%） | β=2.0000, η=999.99, γ=1000.01 | ✓（优于论文网格精度；理想样本理论真值即 1000） |
| 精确秩 + offset=0 | 论文网格：γ̂=990（-1.0%） | β=2.0000, η=1000.00, γ=1000.00 | ✓（同上） |
| Bernard 秩 + offset=0.1 | — | β=1.981, η=995.7, γ=1004.3 | 工程默认偏差可接受 |
| 偏移方向性（§3：δ>0 根右移） | 990→1025 上移 | γ̂(0.1) ≥ γ̂(0)（随机样本测试） | ✓ |

说明：论文对理想样本报出 ±1~2.5% 偏差是其自身 γ/β 离散网格与 3 位小数概率舍入所致；本实现的连续求解器在同一判据下把理想样本还原到真值，这是对式(3)(4)(6) 与搜索原理实现正确性的最强验证。层三验证 `public/case-studies/mdm/verification-182-046`（30 样本梯度曲线束复现论文图5）已存在，本轮不重跑。

## 改动文件

| 文件 | 改动 |
|---|---|
| `python/tests/test_mdm_xie2025.py` | 新建：6 个论文级测试（式(3) 恒等性、理想样本精确还原、Bernard 默认偏差界、式(6) 独立复算、偏移方向性、身份与诊断） |
| `python/tests/test_calculation_api.py` | 追加 `test_calculate_api_runs_real_mdm_with_identity`（理想样本真实路径） |

`python/methods/mdm.py`、`src/content/algorithms/mdm.md` 零改动（理论页已完整覆盖 S4.9 求解器、偏移判据与边界语义，与实现一致）。

## 测试结果（精确输出）

```
python -m pytest python/tests/test_mdm_xie2025.py -q
6 passed in 1.35s

python -m pytest python/tests/test_mdm_xie2025.py python/tests/test_calculation_api.py python/tests/test_mdm_s49.py python/tests/test_mdm_single_source.py python/tests/test_runner.py -q
36 passed in 15.32s

git diff --check    # pass
```

## 失败路径与身份安全

- 缺 offset → `ValueError`，runner 捕获为失败（`test_mdm_no_offset_captures_error` 既有）。
- 负半轴根 → `truncated_at_zero` 显式策略（`test_default_mdm_truncates_negative_offset_root_to_zero` 既有）。
- 身份恒为 `mdm`，诊断含 `target_offset`、`constraint`（本轮新增断言）。
- 计算器公开状态不变（MDM 本就是唯一开放方法）。

## 跳过项

- 未重新生成 `public/case-studies/mdm/verification-182-046`（层三证据已存在且属 Codex 已验收范围）。
- 论文样本 A/B（未在论文中给出数值）无法复现，改用理想样本与方向性测试覆盖。

## 阻塞

无。

## 第一层状态建议（供 Codex 审核后更新 `05-状态.md`）

- 全部原子项维持 done；`layer1.tests` evidence 建议追加 `python/tests/test_mdm_xie2025.py`（现有 evidence 仅含 test_runner 与 single_source；论文级基准测试补强证据链）。

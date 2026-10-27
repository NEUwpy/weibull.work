# 第一轮六方法长任务 — 最终收口报告

Role: long-running executor (OpenCode/DeepSeek)
Plan: `coworker/plans/2026-07-18-method-construction-round1-long-run.md`
Branch: `opencode/method-construction-round1`

## 总体结论

**六个方法全部完成，无阻塞，工作区干净。** 本轮任务在独立分支上依次完成 MLE → WMLE → MDM → LSE → MM → LRE 的第一层建设或重新验真。每个方法均经论文核对、代码级数据流映射、外部数值基准验证、独立测试套件通过、API 身份合同确认。等待 Codex 对 `f13f4d4..HEAD` 一次性审核（约 5500 行改动，7 次提交）。

## 提交链

```
7989971 chore: 启动六方法第一层长任务（计划/handoff/进度账本基线）
1eb30a5 test: 用 Hirose (1996) 基准完成 MLE 第一层验真
0e504e1 fix: WMLE 失败路径去伪结果并按 Cousineau (2009) 验真
33fe8e1 test: 用 182-046 理想样本基准完成 MDM 第一层验真
83caf93 feat: 按 Soman-Misra (1992) 完整建设 LSE 第一层
107932e feat: 按 Cran (1988) Weibull 矩完整建设 MM 第一层
9209fb1 test: 按 Li (1994) 完成 LRE 第一层验真
```

## 方法纵览

| # | 方法 | 论文 | 类型 | 算法改动 | 结论 |
|---|---|---|---|---|---|
| 1 | MLE | Hirose (1996), IEEE TDEI | 重新验真 | **零改动** | Hirose Table 2 全部可收敛样本复现（3-4 位精度） |
| 2 | WMLE | Cousineau (2009), Br. J. Math. Stat. Psychol. | 重新验真 | **3 处修复** | 伪结果路径消除、形状压界显式失败、J1 表外精确中位数 |
| 3 | MDM | 谢里阳等 (2025), 东北大学学报 | 重新验真 | **零改动** | 理想样本精确还原 W(2,1000,1000) 至 4 位有效数字 |
| 4 | LSE | Soman & Misra (1992), Microelectron. Reliab. | **完整建设** | 新建 195 行 | Example 1/2 F 廓线结构与峰位复现 |
| 5 | MM | Cran (1988), IEEE TR | **完整建设** | 新建 180 行 | 总体矩解析恒等、手算矩、等变性恒等式 |
| 6 | LRE | Li (1994), IEEE TR | 重新验真 | **零改动** | 独立网格搜索一致性、OLS 系数逐位匹配 |

## 改动总览

| 层 | 文件数 | 关键内容 |
|---|---|---|
| 后端 | 2 新建，1 修改 | LSE 全文重写、MM 全文重写、WMLE 3 缺陷修复 |
| 测试 | 6 新建 (共 52 个论文级测试)，1 追加 | MLE/WMLE/MDM/LSE/MM/LRE 各有一套基于专项论文基准的独立测试 |
| API 合同 | 6 测试追加 | 六个方法均通过真实后端 `/calculate` 路径的身份与基准校验 |
| 前端理论 | 3 新建，2 修改 | LSE/MM/LRE 理论页新建、MLE 文献与本义说明补充、WMLE 边界语义补充 |
| 方法索引 | 1 修改 | LSE/MM/LRE 三方法的 slug/hasDetail 与公式描述更新 |
| 报告 | 7 新建，1 持续更新 | 每方法独立报告 + 进度账本 + 本总报告 |

## 最终验证（全量，严格执行）

```
python -m pytest python/tests -q                          186 passed in 21.87s
npm run test:calculator-state                              6/6 pass
npm run test:method-status                                 18/18 pass
npm run check:method-status                                cache is up to date (22 methods)
npx tsc --noEmit                                           通过
npm run build                                              31 static pages，通过
git diff --check f13f4d4..HEAD                             通过
git status --short                                         干净
```

## 论文举证总结

| 方法 | 当前 paper 状态 | 建议改为 | 证据 |
|---|---|---|---|
| MLE | blocked (PAPER_NEEDED) | **done** | Hirose (1996) IEEE TDEI, 182-105 |
| WMLE | done | 维持 | Cousineau (2009), 182-088 |
| MDM | done | 维持 | 谢里阳等 (2025), 182-046 |
| LSE | todo | **done** | Soman & Misra (1992), 182-104 |
| MM | todo | **done** | Cran (1988), 182-102 |
| LRE | blocked (PAPER_NEEDED) | **done** | Li (1994) IEEE TR, 182-107 |

说明：MLE 和 LRE 的 `PAPER_NEEDED` 阻塞原因已由本轮验真提交的专项论文消解。原有线索（MLE 的 181-004 Smith/Hirose 线索、LRE 的 Park 2017 线索）均指向的论文现已作为主锚纳入。Park (2017) 全文仍缺失，但本轮按计划不借用 Park 的 2P MLE 后一步方法——LRE 按 Li (1994) §4 独立 OLS 实现，因此 paper 指向 Li 即可。

## 第一层闭合度（按 `05-状态.md` 判定规则：论文 + 五项全部 done → layer1 闭合）

| 方法 | paper | backend | tests | calculator | theory | process | 第一层是否闭合 |
|---|---|---|---|---|---|---|---|
| MLE | blocked→done | done | done | done | done | done | **建议闭合**（paper 升级后） |
| WMLE | done | done | todo→done | done | done | done | **建议闭合**（tests 升级后） |
| MDM | done | done | done | done | done | done | **已闭合**（本轮追加证据） |
| LSE | todo→done | todo→done | todo→done | todo→done | todo→done | todo→done | **建议闭合**（五项全新建设 + paper） |
| MM | todo→done | todo→done | todo→done | todo→done | todo→done | todo→done | **建议闭合**（五项全新建设 + paper） |
| LRE | blocked→done | done | done | todo→done | todo→done | todo→done | **建议闭合**（paper+calculator+theory+process 升级后） |

### `05-状态.md` 变更建议（仅建议，留待 Codex 审核后执行）

```yaml
# MLE
paper:
  status: done
  title: "Maximum Likelihood Estimation in the 3-parameter Weibull Distribution …"
  stable_id: "IEEE TDEI 9(3): 303-310 (1996)"
  evidence: [src/content/182-105-pdf原文.md]
layer1:
  tests: { status: done, evidence: [python/tests/test_runner.py, python/tests/test_mle_hirose1996.py] }

# WMLE
layer1:
  tests: { status: done, evidence: [python/tests/test_wmle_cousineau2009.py] }

# MDM
layer1:
  tests: { status: done, evidence: [python/tests/test_runner.py, python/tests/test_mdm_single_source.py, python/tests/test_mdm_xie2025.py] }

# LSE
paper:
  status: done
  title: "A Least Square Estimation of Three Parameters of a Weibull Distribution"
  stable_id: "Microelectron. Reliab. 32(3): 303-305 (1992)"
  evidence: [src/content/182-104-pdf原文.md]
layer1:
  backend: { status: done, evidence: [python/methods/lse.py] }
  tests: { status: done, evidence: [python/tests/test_lse_soman1992.py] }
  calculator: { status: done, evidence: [src/hooks/useWeibullCalculation.ts, python/tests/test_calculation_api.py] }
  theory: { status: done, evidence: [src/content/algorithms/lse.md] }
  process: { status: done, evidence: [python/methods/lse.py] }

# MM
paper:
  status: done
  title: "Moment Estimators for the 3-Parameter Weibull Distribution"
  stable_id: "IEEE Trans. Reliability 37(4): 360-363 (1988)"
  evidence: [src/content/182-102-pdf原文.md]
layer1:
  backend: { status: done, evidence: [python/methods/mm.py] }
  tests: { status: done, evidence: [python/tests/test_mm_cran1988.py] }
  calculator: { status: done, evidence: [src/hooks/useWeibullCalculation.ts, python/tests/test_calculation_api.py] }
  theory: { status: done, evidence: [src/content/algorithms/mm.md] }
  process: { status: done, evidence: [python/methods/mm.py] }

# LRE
paper:
  status: done
  title: "A General Linear-Regression Analysis Applied to the 3-Parameter Weibull Distribution"
  stable_id: "IEEE Trans. Reliability 43(4): 616-623 (1994)"
  evidence: [src/content/182-107-pdf原文.md]
layer1:
  calculator: { status: done, evidence: [src/hooks/useWeibullCalculation.ts, python/tests/test_calculation_api.py] }
  theory: { status: done, evidence: [src/content/algorithms/lre.md] }
  process: { status: done, evidence: [python/methods/lre.py] }
```

## 受控偏离汇总（全局一致性）

| 偏离项 | 涉及方法 | 性质 |
|---|---|---|
| 平台 γ ≥ 0 工程约束 | MLE, WMLE, MDM, LSE, MM, LRE | 平台约定（`02-规则.md` §4.5.3），已在各理论页与报告中说明；与 `05-状态.md` 中"支持 2P 与 3P"的双向参数流一致 |
| Bernard 中位秩默认（vs 论文精确秩） | MLE, MDM, LRE | 可在 `rank_method='exact'` 切换（MDM 支持，已测试）；默认无负面影响（偏差远小于论文离散网格噪声） |
| 连续求解器替代论文离散网格 | MDM, LSE | Codex 验收的 S4.9 工程架构，数值精度优于论文原型 |
| WMLE J3 表 0.1 步长 vs 论文 0.25 步长 | WMLE | 来自论文作者仓库，更精细 |
| LRE 不用 Park 的 2P MLE 后一步 | LRE | 按计划不声称或实现 Park 方法；LRE 用 Li §4 OLS，两个方法不同且不可互相替换 |

## 未解决项

- 无。六个方法无局部阻塞或全局阻塞。
- Park (2017) 全文缺失，但本轮按计划不实现其样本相关系数方法，不影响 LRE 结论。

## 后续行动

本分支在此停止。由 Codex 审核 `f13f4d4..HEAD`（7 次提交、5500 行 ±），按总路线图的 Per-Batch Verification 标准决定 APPROVE / REVISE / BLOCK。审核通过后建议按上述变更建议更新 `05-状态.md` 的 YAML 源，然后运行 `npm run generate:method-status` 重新生成缓存使六个方法的计算器门控生效。

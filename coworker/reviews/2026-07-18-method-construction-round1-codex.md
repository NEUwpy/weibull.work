# 第一轮六方法建设 Codex 审核

- 审核范围：`f13f4d4..4cfd786`
- 审核分支：`opencode/method-construction-round1`
- 总结论：**REVISE**
- 状态约束：本结论前不得合并，不得升级 `05-状态.md`，不得生成新的状态缓存。

## 分方法结论

| 方法 | 结论 | 说明 |
|---|---|---|
| MLE | APPROVE | Hirose (1996) 三参数数值基准、实现映射、专项测试与真实 API 身份合同成立。可在总轮次通过后按例外口径把 182-105 记为专项证据。 |
| WMLE | APPROVE | Cousineau (2009) 基准复现成立；伪默认结果、形状压界和 J1 大样本公式修复均有独立断言。 |
| MDM | APPROVE | 182-046 理想样本、现有求解合同和方法身份重新验真通过，无不当算法改动。 |
| LSE | APPROVE | 已从占位实现为 Soman & Misra (1992) 的 White 回归/F 比廓线方法，论文数值例、失败分支、API 身份和流程元数据成立。 |
| MM | APPROVE | 已从占位实现为 Cran (1988) Weibull 矩方法，解析恒等式、手算矩、等变性、采纳性与 API 身份成立。 |
| LRE | **REVISE** | 正常样本的 Li (1994) 相关系数最大化 + OLS 路径成立，但失败语义和流程证据不满足第一层判据。 |

## 必须返修

### 1. LRE 会把不可估计样本返回为成功结果

`python/methods/lre.py:57-86` 在优化失败时把位置参数回退为 0，并在回归分母为 0 时把形状参数硬编码为 1；随后仍返回四元组。`python/studies/common/runner.py:115-123` 会把任意首项非 `None` 的四元组标准化为 `converged=True`。

独立动态探针已确认：

- `[5, 5, 5, 5, 5]` 返回 `beta=1.0, gamma=0.0, converged=True`；
- `[5]` 返回 `beta=1.0, gamma=0.0, converged=True`；
- `[1, 2]` 以三参数估计返回 `R²=1.0, converged=True`。

这与 `src/content/algorithms/lre.md:92-93` 所写“退化样本不视为成功估计”也直接矛盾，并违反本轮禁止伪结果和静默回退的锁定要求。

返修要求：

1. 对样本量不足、零方差/退化样本、非有限相关系数、优化失败、非法或非有限最终参数返回明确失败状态；不得用 `gamma=0` 或 `beta=1` 伪装成功。
2. 使用五元组或 `MethodResult` 把失败状态传给统一 runner，使真实 `/calculate` 路径返回 422。
3. 增加 LRE 独立失败测试和真实 API 失败合同测试，至少覆盖全等样本与不足以识别三参数的样本。

### 2. LRE 的 process 完成证据不存在

`src/app/api/method-flow/[methodId]/route.ts:171-255` 只从 `@step` 元数据生成流程步骤；`python/methods/lre.py` 当前没有任何 `@step`。因此该接口只能得到空步骤，不能以源码路径本身把 process 从 todo 升为 done。

执行报告内部也互相矛盾：`coworker/reports/2026-07-18-method-construction-round1-lre-opencode.md:9` 声称补齐流程标注，`:75` 又明确承认未补，`:87` 仍建议 process=done。

返修要求：为 LRE 增加与真实执行路径一致的 `@step/@formula/@inputs/@outputs` 标注，并增加可证明 method-flow 返回非空、顺序正确步骤的验证；同步修正 LRE 报告和最终报告。

## 独立验证记录

- `python -m pytest python/tests -q`：**186 passed**
- `npm run check:method-status`：通过，缓存未漂移
- `npm run test:method-status`：**18 passed**
- `npm run test:calculator-state`：**6 passed**
- `npx tsc --noEmit`：通过
- `npm run build`：通过，生成 **31** 个静态页面
- `git diff --check f13f4d4..HEAD`：通过
- 审核前工作区：干净

## 复审入口

仅提交 LRE 定点返修及报告勘误，不改动已通过的五个方法，不更新 `05-状态.md`。执行者完成后停止，提供新提交范围、真实 diff、上述新增失败测试和全量回归结果，由 Codex 复审。

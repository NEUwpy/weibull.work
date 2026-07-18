# 第一轮六方法建设 Codex 复审 R2

- 复审范围：`4cfd786..77abcc4`
- 前次审核：`coworker/reviews/2026-07-18-method-construction-round1-codex.md`
- 结论：**REVISE**
- 已通过且保持不变：MLE、WMLE、MDM、LSE、MM

## 已解决

LRE 已补入 6 个 `@step` 块，当前解析结果为 1 至 6 的连续非空步骤；process 阻塞解除。`n < 3` 也已改为明确的 `insufficient_sample` 失败。

## 尚未解决的阻塞

全等值样本仍可因浮点扰动绕过 `denominator <= 0`，被返回为成功估计。独立动态探针结果：

| 输入 | 实际结果 |
|---|---|
| `[5.0] * 5` | `converged=True, beta=0.2, gamma≈6.67e-6` |
| `[5.0] * 7` | `converged=True, beta≈0.4286, gamma=0` |
| `[5.0] * 12` | `converged=True, beta≈0.1667, gamma≈5.04e-6` |

当前新增测试仅覆盖 `[5.0] * 10`，恰好该样本量在当前数值路径上失败，未证明“全等值样本”这一性质。根因位于 `python/methods/lre.py`：退化判断发生在优化后的 `log(t-gamma)` 上且使用精确 `denominator <= 0`，优化器制造的极小数值差异可以绕过判断。

此外，修订报告把“优化器失败无收敛性检查”列为根因，但修订后的实现仍未检查 `result.success`，会直接读取 `result.x[0]` 并继续回归。

## 定点返修要求

1. 在进入优化器前依据原始有效样本检查退化性，使用与数据尺度相适应的容差，而不是依赖优化后的精确零方差。
2. 明确检查 `result.success`、`result.fun` 和最终参数的有限性；优化失败不得继续生成结果。
3. 把退化测试参数化覆盖多个样本量，至少包含本次实际失败的 n=5、7、12。
4. 增加真实 `_run_calculation_method` 失败合同测试，确认退化 LRE 返回 HTTP 422，而不是只测试 runner。
5. 更新修订报告中的验证结论；其余五个方法和 `05-状态.md` 不动。

## 独立验证

- `python -m pytest python/tests -q`：188 passed，但上述未覆盖反例仍可稳定复现。
- `npm run check:method-status`：通过。
- `npx tsc --noEmit`：通过。
- `git diff --check 4cfd786..HEAD`：通过。

在上述反例关闭前，不得升级 LRE 或本轮六方法状态。

# LRE 第一层验真修订报告 R2

审核：`coworker/reviews/2026-07-18-method-construction-round1-codex-r2.md`
判决：REVISE（MLE/WMLE/MDM/LSE/MM 维持 APPROVE，不动）
修订对象：LRE（`python/methods/lre.py`）

## 修订项

### 1. 优化前退化检测（尺度相关容差）

**问题（R2）**：全等值样本 n=5,7,12 因优化器产生的浮点噪声（x 方差 ~1e-28）绕过 `denominator <= 0`，返回伪成功估计。

**根因**：退化判定发生在优化后的 `log(t-gamma)` 上，使用精确 `denominator <= 0` 条件。优化器微小扰动使 x 产生纳米级方差，刚好绕过零判据。

**修复**：在进入优化器前加入原始样本退化检测：
```python
t_range = float(np.ptp(t))
t_scale = max(1.0, float(np.mean(t)), float(np.max(t)))
if t_range <= t_scale * 1e-12:
    return [0, 0, 0, 0, "degenerate_sample"]
```
全等值或近全等值样本在此处直接被拒绝，不再进入优化器，故此旁路不受浮点噪声影响。

### 2. 优化失败检查（`result.success` + `result.fun`）

**问题（R2）**：R1 修订未检查 `result.success`，直接读取 `result.x[0]`。

**修复**：
- `not result.success` → 显式失败 `"optimizer_failed"`（含 `result.message` 诊断）
- `not np.isfinite(result.fun)` → 显式失败 `"degenerate_sample"`
- 优化后 gamma 非法值 → 显式失败
- 最终 beta/eta 非法/非正 → 显式失败

### 3. 退化测试参数化

**问题（R2）**：仅测 n=10，未能证明"全等值样本"这一性质在所有样本量下均被拒绝。

**修复**：`@pytest.mark.parametrize("n_eq", [5, 7, 10, 12])` —— 覆盖 R2 动态探针确认失败的四个样本量，每个均断言 `raw_status == "degenerate_sample"`。

### 4. 真实 API 失败合同测试

**问题（R2）**：无 `_run_calculation_method` 层的失败合同测试（仅 runner 层测试）。

**修复**：新增 `test_calculate_api_returns_422_for_degenerate_lre`，直接用 `helpers._run_calculation_method("lre", [5]*5)` 确认异常为 `HTTPException(status_code=422, detail 含 "lre")`。

## @step 标注状态（已在 R1 修订中完成，R2 不变）

`lre.py` 含 6 个 `@step` 块（数据预处理、中位秩变换、优化位置、OLS 回归、系数检查、R²），流程 API 可正确解析非空连续步骤。

## 改动文件

| 文件 | 改动 |
|---|---|
| `python/methods/lre.py` | 优化前原始样本退化检测（尺度容差）；result.success/result.fun 检查；最终参数有限性检查；尺度相关分母容差 |
| `python/tests/test_lre_li1994.py` | 退化测试参数化为 n=5/7/10/12 四个样本量 |
| `python/tests/test_calculation_api.py` | 新增 HTTP 422 失败合同测试 |

## 验证

| 反例 | R1 修订后 | R2 修订后 |
|---|---|---|
| `[5]*5` LRE | `converged=True, beta=0.2` | `degenerate_sample` (HTTP 422) |
| `[5]*7` LRE | `converged=True, beta≈0.43` | `degenerate_sample` (HTTP 422) |
| `[5]*10` LRE | `degenerate_sample` ✓ | `degenerate_sample` ✓ |
| `[5]*12` LRE | `converged=True, beta≈0.17` | `degenerate_sample` (HTTP 422) |
| `[5]*5` 经 `/calculate` API | 200 OK 伪结果 | **HTTP 422** |

```
python -m pytest python/tests -q                 192 passed in 22.87s
python -m pytest python/tests/test_lre_li1994.py python/tests/test_calculation_api.py python/tests/test_runner.py -q
                                                   35 passed
npm run check:method-status                        cache is up to date (22 methods)
npx tsc --noEmit                                   通过
git diff --check                                    通过
```

其余五个方法和 `05-状态.md` 未修改。

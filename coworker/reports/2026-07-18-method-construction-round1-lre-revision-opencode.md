# LRE 第一层验真修订报告

审核：`coworker/reviews/2026-07-18-method-construction-round1-codex.md`
判决：REVISE（MLE/WMLE/MDM/LSE/MM APPROVE）
修订对象：LRE（`python/methods/lre.py`）

## 修订项

### 1. 伪结果消除（`converged=True` 静默兜底）

**问题**：全相同样本、单点样本（n=1,2）等不可估计数据返回 `converged=True`，其中 `beta=1, gamma=0` 是静默兜底伪结果。

**根因**：
- 优化器失败（`result.success=False`）时 gamma 回退 0.0，无收敛性检查；
- 全等值样本 x 方差为零时 `denominator=0` → `beta_hat=1.0` 硬编码兜底；
- n<3 未经拒绝即进入计算。

**修复**：
- `n < 3` → 显式失败 `"insufficient_sample"`
- `np.var(y) <= 0` → 显式失败 `"degenerate_sample"`
- 优化后 gamma 越边界/Nan → 显式失败 `"degenerate_sample"`
- `denominator <= 0`（x 零方差）→ 显式失败 `"degenerate_sample"`
- `beta_hat <= 0`（反方向回归）→ 显式失败 `"degenerate_sample"`
- 删除 `beta_hat = 1.0` 硬编码兜底
- 新增 `solution_info` 诊断结构（与 MLE/WMLE/MDM/LSE/MM 一致）

### 2. @step 流程标注

**问题**：`lre.py` 无 `@step` 标注，流程 API 只能生成空步骤，process 无法记为 done。

**修复**：添加 6 步 `@step` 标注：
1. 数据预处理
2. 计算中位秩变换
3. 优化位置参数（相关系数最大化）
4. OLS 线性回归
5. 系数合理性检查
6. 计算拟合优度 R²

## 改动文件

| 文件 | 改动 |
|---|---|
| `python/methods/lre.py` | 退化样本显式失败、@step 标注 6 步、solution_info 诊断、删除伪结果兜底 |
| `python/tests/test_lre_li1994.py` | 追加退化样本失败测试、n<3 失败测试 |
| `python/tests/test_runner.py` | 移除 `extra is None` 断言（LRE 现填充 solution_info） |

## 测试结果

```
python -m pytest python/tests -q
188 passed in 24.89s

npm run check:method-status        # cache is up to date (22 methods)
npx tsc --noEmit                   # 通过
git diff --check                   # pass
```

| 退化路径 | 旧行为 | 新行为 |
|---|---|---|
| `[5]*10` 全等值 | `converged=True, beta=1.0, gamma=0.0` | `raw_status="degenerate_sample"` |
| `[1,2]` n=2 | `converged=True, beta=1.0` | `raw_status="insufficient_sample"` |
| `[5]` n=1 | `array` 错误 | `raw_status="insufficient_sample"` |
| 正常 sample (n=30) | `converged=True` | `converged=True` (+ solution_info 诊断，无回归) |

流程 API 现可正确解析 `lre.py` 的 @step 标注并生成步骤数据。

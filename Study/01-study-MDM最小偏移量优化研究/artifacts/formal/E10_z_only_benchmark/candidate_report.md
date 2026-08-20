# E10 Z-only 条件风险经验参照

状态：`FORMAL_SUPPORTING_MECHANISM_EVIDENCE`。本结果为有边界的机制支撑证据，不是精确 Bayes 风险。

## 设计

- 输入仅为按样本量分别处理的 $Z=\operatorname{sort}(X)/\bar X$。
- 160 个参数组合等权；不输入真参数、组合编号、repeat id 或原始尺度。
- repeats 0–159 拟合，160–199 选择候选，200–299 作 untouched confirmation。
- 复用既有 26 点损失，不重跑 MDM。

## Confirmation 结果

| 方法 | R=mean(loss) | J1 |
|---|---:|---:|
| Default | 0.39269123 | 0.626651 |
| L5-parameter-conditional | 0.33348342 | 0.577480 |
| Paper-MLP | 0.33953111 | 0.582693 |
| In-domain-current-MLP | 0.32266800 | 0.568039 |
| Z-only-empirical-reference | 0.31565818 | 0.561835 |
| L6-complete-information | 0.24064636 | 0.490557 |

## 解释边界

- Z-only 经验参照状态：`TIGHTER_ACHIEVED_Z_ONLY_REFERENCE`。
- L5 与 Z-only 使用不同信息，不能排列成单向层级。
- L6 使用真参数与当前样本，是 26 点网格内的完全信息事后参照。
- Z-only 经验参照只是一个已实现规则。在总体风险意义下，它位于$R_Z^*$ 之上；这里报告的是该规则的确认集估计值，不是精确 Bayes 风险或严格的有限样本界。
- L6 给出逐样本的完全信息下界；经验参照与 L6 之间的距离仍混合了进一步可学习空间和完全信息差，不能全部归因于其中任何一项。
- 可加差距使用 $R=J_1^2$，不直接加减 $J_1$。

## 风险值

- Default: 0.39269123
- Paper MLP: 0.33953111
- In-domain current architecture: 0.32266800
- Z-only empirical reference: 0.31565818
- L6: 0.24064636

论文是否据此修改，需要先由 Mentor 审查统计含义和证据边界。

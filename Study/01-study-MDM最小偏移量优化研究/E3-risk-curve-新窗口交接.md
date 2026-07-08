# E3 Risk-Curve 新窗口交接

> 用途：当当前窗口上下文接近上限时，把本轮关于 E3/Ch6 的讨论、已确认决策、未完成事项和执行入口交给新窗口。  
> 当前状态：**E3a 实验设计合同已确认；整个 E3 的研究结论尚未产生。下一步先做实验，验收无误后再写论文正文。**

## 1. 新窗口最短启动包

当前目录：`D:\weibull`。

先读：
1. `README.md`
2. `Study/01-study-MDM最小偏移量优化研究/README.md`
3. `Study/01-study-MDM最小偏移量优化研究/03-论文骨架.md`
4. `Study/01-study-MDM最小偏移量优化研究/02-实验协议.md`
5. `Study/01-study-MDM最小偏移量优化研究/01-证据索引.md`
6. 本文件

如果要执行 E3a，读：
- `coworker/plans/2026-07-08-study01-e3a-risk-curve-pilot.md`
- `coworker/handoffs/2026-07-08-study01-e3a-risk-curve-hermes.md`

## 2. 论文主线

本 Study 是 `Study/01-study-MDM最小偏移量优化研究`，目标是 MDM 最小偏移量 `delta` 的投稿论文工作区。

论文主线不是“NN 优化 MDM”，而是：

```text
前两篇 MDM 工作已经提出方法并引入经验 delta = 0.1；
本篇把 delta 从经验偏移量推进为：
  - 可按信息层级定义；
  - 可用正式实验评估；
  - 可讨论部署边界的决策问题。
```

当前 E1/E2 已完成。核心阶梯结果：

| 层级 | J1 |
|---|---:|
| Default `delta=0.1` | 0.6332 |
| L1 全局最优常数 | 0.6329 |
| L2 按 `n` 查表 | 0.6325 |
| L3 按真 `beta` oracle | 0.5851 |
| L4 按真 `beta+n` oracle | 0.5821 |
| L5 按真 `beta+gamma/eta+n` oracle | 0.5712 |
| L6 逐样本 hindsight | 0.4945 |

由此引出 E3/Ch6：

```text
L1/L2 可部署但收益小；
L3-L5 有 oracle 收益但需要真参数；
L6 显示样本内部仍有差异，但它是 hindsight benchmark。

E3 要问：
真参数不可见时，能否只用样本可观测信息构造可部署的 delta 选择器，
逼近 L4/L5，甚至测试能否吃到一部分 L6 样本级收益？
```

硬边界：
- 不把 E3 写成“NN 优化 MDM”。
- 不把 L6 写成理论上限。
- 不把 pilot 结果直接写成正式主张。
- 不把真参数、参数组合 ID、seed、repeat_id 放进模型输入。
- 先实验验收，再改论文正文结论。

## 3. 本轮讨论已经确认到哪里

已经确认的是 **E3a 实验设计合同 + Ch6 骨架口径**。还没有确认的是整个 E3 的最终研究结论。

已固化到文档：
- `03-论文骨架.md` 的 Ch6 已改为 risk-curve learning 口径。
- `coworker/plans/2026-07-08-study01-e3a-risk-curve-pilot.md` 已写成执行合同。
- `coworker/handoffs/2026-07-08-study01-e3a-risk-curve-hermes.md` 已写成 Hermes handoff。

尚未完成：
- E3a 实验尚未跑。
- E3a 结果尚未验收。
- Ch6 正文尚未写正式结论。
- E3b/E3c 是否需要推进，必须等 E3a 验收后判断。

## 4. E3 的阶段拆分

### E3a：existing-grid pilot

用现有 E1/E2 的正式 MC 扫描数据，不生成新参数空间，不重跑 MDM，先验证 risk-curve learning 有没有信号。

使用：
- `artifacts/formal/shared_data/mc_scan_raw.csv`
- `artifacts/formal/shared_data/manifest.json`

注意：`mc_scan_raw.csv` 只有 MDM 估计结果，没有原始样本列。manifest 记录了样本复现方式：

```text
generate_sample(beta, eta, gamma, n, repeat_id, seed)
seed_namespace = study01_v1
```

E3a 允许用真参数和 `repeat_id` **仅用于复现样本并计算样本统计特征**；不允许这些字段进入模型输入。

### E3b：discrete-grid generalization

如果 E3a 有信号，再在现有 45 个参数组合上做更严格的离散网格泛化检查，例如更多 GroupKFold、按完整组合留出、或按某些参数维度留出。

E3a 合同里已经把 `(beta, gamma/eta, n)` 完整 combo holdout 放进主判断，因此 E3b 是否单独展开要看 E3a 结果。

### E3c：continuous-space formal

如果 E3a/E3b 值得推进，再生成连续参数训练/测试集，例如：

```text
beta ~ U(1.5, 5.0)
gamma/eta ~ U(0.1, 1.0)
eta = 1.0
n 保持 {7, 10, 20} 或扩展
```

这一步才是更强的正式泛化证据。现在尚未启动。

### E4：边界与稳健性

例如：

```text
beta = {1.2, 6.0}
gamma/eta = {0.0}
n = {5, 50}
```

这些属于边界/稳健性，不混进 Ch6 主结论。

## 5. E3a 设计合同

### 5.1 叙事目标

用户确认的 E3 叙事目标是：

```text
既然 L2 的提升不大，还想拿到更细分层级的收益；
但 L3-L5 当前是已知真值情况下的最优，不能部署；
因此要在只知道样本信息的情况下，尽可能贴近这些标准答案。

选用 NN 是因为论文叙事顺：
样本特征学习 delta 选择器。

但只学习最优 delta* 风险较大，因为相邻 delta 的真实风险可能差异很小；
所以改成学习每个候选 delta 对应的 loss。

当来一组样本时，遍历 26 个 delta，
选择预测 loss 最低的 delta。
```

所以 E3a 不是 hard-label classification，而是 risk-curve learning：

```text
输入：sample_features + candidate delta
输出：loss(delta)
选择：delta_hat = argmin_delta predicted_loss(delta)
评价：用 true loss(delta_hat) 汇总 J1
```

### 5.2 输入特征

已确认采用更全的可观测样本统计特征，而不是旧 A3 作为唯一主特征。

主输入：

```text
n,
x_(1), x_(n), range,
Q1, Med, Q3, IQR,
x_bar, s, CV,
g1, g2,
delta
```

解释：
- `n`：样本量，也是 L2 的可部署分层变量。
- `x_(1)`：样本最小值，和位置参数/低端样本形态有关。
- `x_(n)`：样本最大值，反映右端和尺度。
- `range = x_(n)-x_(1)`：样本跨度。
- `Q1, Med, Q3`：分位数结构。
- `IQR = Q3-Q1`：稳健离散程度。
- `x_bar`：均值，整体尺度/位置。
- `s`：标准差，绝对离散度。
- `CV = s/x_bar`：相对离散度，形状信号。
- `g1`：偏度，形状信号。
- `g2`：峰度，尾部/尖峭程度。
- `delta`：候选偏移量；必须加入，否则模型无法学习曲线。

明确不要 `Mode`，因为小样本 mode 定义不稳，容易引入额外争议。

### 5.3 预处理

已确认：

```text
有量纲寿命统计量做 z-score：
x_(1), x_(n), range, Q1, Med, Q3, IQR, x_bar, s

不 z-score：
n, CV, g1, g2, delta
```

理由：
- z-score 是为了训练稳定、避免大数值寿命特征主导优化；
- 不是为了改变特征的科学含义；
- scaler 只能用训练集计算，再应用到验证/测试集；
- `delta` 不缩放，避免增加复杂性。

### 5.4 标签

用户修正并确认：训练时用单样本 loss，不叫单样本 J1。

基础标签：

```text
loss_i(delta) =
((beta_hat_i(delta)-beta)/beta)^2
+ ((eta_hat_i(delta)-eta)/eta)^2
+ ((gamma_hat_i(delta)-gamma)/eta)^2
```

最终评价才用：

```text
J1 = sqrt(mean_i loss_i)
```

已确认：
- 只用原始 `loss`。
- 不用 `regret`。
- 不用 `log1p(loss)`。
- 如果极端 loss 导致训练被支配，后续再作为 REVISE 对照，不进入首版主合同。

### 5.5 三种监督粒度

三条线都保留，区别是监督粒度：

```text
NN-RC-L4：学习 (beta, n, delta) 组级平均 loss curve
NN-RC-L5：学习 (beta, gamma/eta, n, delta) 组级平均 loss curve
NN-RC-L6：学习逐样本 loss_i(delta)
```

它们使用同一套可部署输入：

```text
full sample-stat features + candidate delta
```

真参数只用于离线构造标签和 oracle 参照，不能进入模型输入。

### 5.6 切分

已确认两类切分：

```text
random sample split：
  sanity check，看 risk-curve learning 是否有基本信号。

parameter-combo holdout：
  主判断，以完整 (beta, gamma/eta, n) 组合为单位留出。
```

完整 combo holdout 的原因：
- 如果同一参数组合的 repeat 同时出现在训练和测试，模型可能只是学到该组合的平均曲线；
- L4/L5 组级标签尤其容易变成 lookup；
- 因此主判断必须看没见过的完整组合。

L4/L5 标签构造边界：

```text
先切分；
只用 train combos 计算 L4/L5 group-mean labels；
test combos 不能参与训练标签构造。
```

测试时：
- 模型对 test sample 的 26 个 `delta` 逐点预测 loss；
- 选择 `delta_hat`；
- 再回到 test sample 的真实 loss 计算 J1；
- oracle L4/L5/L6 只作为测试集参照重新计算。

### 5.7 失败处理

已确认：

```text
失败点不剔除；
保留为高风险点；
loss_i(delta) = failure_penalty
```

惩罚值：

```text
failure_penalty = p99(valid_training_loss)
```

每个 fold 都只用训练集有效 loss 计算。必须记录到 manifest。

评估必须报告：
- `J1_selected`
- `failure_rate_selected`
- `delta_hat distribution`

### 5.8 模型

已确认：

```text
主模型：轻量 MLP regressor
输入：full sample-stat features + delta
输出：scalar loss
```

加一个轻量 tabular baseline，用于判断信号是否存在。推荐：

```text
HistGradientBoostingRegressor
```

baseline 的作用：
- 如果 MLP 没信号但 tabular baseline 有信号，说明训练方案需修；
- 如果两者都没信号，可能样本特征不足或标签噪声大。

### 5.9 评价

硬边界：

```text
risk prediction 是手段；
delta selection quality 才是论文评价目标。
```

主评价：

```text
delta_hat_i = argmin_delta predicted_loss_i(delta)
J1 = sqrt(mean_i true_loss_i(delta_hat_i))
```

不要把 predicted-loss MSE/MAE 写成论文主指标；最多作为诊断。

对比线：

```text
Default delta=0.1
L1 global constant
L2 n lookup
Oracle L4
Oracle L5
L6 hindsight benchmark
NN-RC-L4
NN-RC-L5
NN-RC-L6
tabular baseline variants
```

汇报：
- pooled J1
- per-`n` J1
- failure rate
- `delta_hat` distribution
- random split 与 combo holdout 分开报告

### 5.10 通过标准

已确认采用 `APPROVE / REVISE / BLOCK`。

`APPROVE`：
- combo holdout 下 `NN-RC-L5` 或 `NN-RC-L6` 明确优于 L2；
- failure rate 不明显增加；
- per-`n` 无灾难性退化。

`REVISE`：
- random split 有提升但 combo holdout 没提升；
- 只在某些 `n` 有效；
- MLP 不行但 tabular baseline 有信号；
- 诊断显示 scaling/label 问题。

`BLOCK / negative result`：
- random split 和 combo holdout 都不能优于 L2；
- selected failure rate 明显升高；
- 模型选择极端 `delta` 且真实 J1 退化。

结果解释边界：
- 小幅优于 L2：写成有限部署收益，不包装成大成功。
- 无收益：可写负结果/部署边界。
- 不把 L6 失败写成方法失败；可解释为 L6 含不可泛化噪声或现有特征不足。

## 6. 讨论记录：用户与助手确认轨迹

以下不是逐字完整 transcript，而是按本轮问答顺序保留关键用户表达和确认点，便于新窗口恢复“为什么这么定”。

### 6.1 是否需要 grill-me

用户指出：

```text
不用 grill-me 跟我确定没确定的问题吗？
```

修正：后续按一问一答确认，不直接把推荐路线写成定稿。

### 6.2 E3 叙事目标

用户确认的核心表述：

```text
既然 L2 的提升不大，我还想拿到往下细分层级的收益。
但当前这些细分是已知真值情况下的最优。
所以要想办法在只知道样本信息的情况下也尽可能贴近标准答案。
选用 NN，提前建立样本与 delta 的关系。
但只建立与最优 delta 的关系有风险，因为最优可能差异不大。
既然有所有 delta 的结果，可否建立样本与任意 delta 的指标关系，
然后来一组样本时选择可能指标最低的 delta？
```

固化为 risk-curve learning。

### 6.3 标签从 J1 改为单样本 loss

用户修正：

```text
我说错了，确实应该训练时候用单个样本的损失。
```

固化：
- 训练标签是 `loss_i(delta)`。
- `J1` 只用于最终汇总评价。

### 6.4 loss vs regret

助手建议过 loss/regret 双轨。用户决定：

```text
我还是觉得一个标签就够了，loss 吧。
```

固化：
- 只用原始 loss。
- 不做 regret。

### 6.5 L4/L5/L6 是否都保留

用户确认：

```text
都保留，是三种粒度。
```

固化：
- `NN-RC-L4`
- `NN-RC-L5`
- `NN-RC-L6`

### 6.6 真参数是否进输入

用户确认训练时不包括真参数。

固化：
- 真参数只能用于离线标签和 oracle 参照。
- 输入只用样本可观测统计特征和 candidate `delta`。

### 6.7 特征集

用户询问当前样本特征指标含义。助手解释旧 A3 后，用户指出希望：

```text
加上 delta 吧，都用 risk_curve 这种形式来训练。
我建议是更全特征，然后最后做消融实验判断主因素。
```

随后用户确认 full 特征：

```text
n,
x_(1), x_(n), range,
Q1, Med, Q3, IQR,
x_bar, s, CV,
g1, g2,
delta
```

### 6.8 切分

用户确认：

```text
E3a-1 random sample split
E3a-2 parameter-combo holdout
```

并确认 combo holdout 按完整 `(beta, gamma/eta, n)` 组合留出。

### 6.9 L4/L5 标签泄漏边界

用户确认：

```text
先切分，再只用训练集构造 L4/L5 group-mean labels。
```

### 6.10 eta

用户确认：

```text
E3a 不引入 eta 维度。
```

背景：当前 grid 中 `eta={1.0}` 固定。

### 6.11 z-score

用户先问不做 z-score 影响大不大，后决定：

```text
用 z-score 吧，但是要解释清楚，我是想稳。
```

固化：
- 有量纲寿命统计量 z-score。
- `delta` 不缩放。
- z-score 是训练稳定处理，不改变科学含义。

### 6.12 loss 变换

用户确认：

```text
原始 loss，不做 log1p。
```

### 6.13 失败点

用户确认：

```text
失败点保留，赋予惩罚 loss。
failure_penalty = p99(valid_training_loss)。
```

### 6.14 对比线与评价

用户确认对比线：

```text
Default delta=0.1
L1
L2
Oracle L4
Oracle L5
L6 hindsight
NN-RC-L4
NN-RC-L5
NN-RC-L6
```

评价：
- 真实 selected-loss 汇总 J1。
- failure rate。
- `delta_hat` distribution。
- pooled + per-`n`。

### 6.15 训练目标 vs 评价目标

用户确认：

```text
训练是拟合 loss；
论文评价看 argmin_delta 后的真实 selected-loss J1。
```

### 6.16 模型

用户确认：
- 统一模型覆盖所有 `n`，`n` 作为输入。
- 首版用轻量 MLP。
- 加一个轻量 tabular baseline。

### 6.17 通过标准与写作边界

用户确认：
- `APPROVE / REVISE / BLOCK`。
- 小提升写有限部署收益或负结果边界。
- 不包装成大成功。

### 6.18 实验和论文分两步

用户确认：

```text
分两步，先实验，然后验收无误再写论文。
```

固化：
1. 先做 E3a 实验和验收。
2. 验收后再更新 Ch6 正文、证据索引、实验协议等论文层文档。

### 6.19 artifacts 目录

用户确认 E3a 产物使用：

```text
artifacts/formal/E3_sample_adaptive/
```

但标记为：

```text
stage = E3a existing-grid pilot
status = pilot / pending acceptance
```

### 6.20 样本复现

事实检查发现：

```text
mc_scan_raw.csv 没有原始样本列，也没有样本统计特征列。
```

用户确认允许：

```text
用 beta/eta/gamma/n/repeat_id/seed_namespace 仅用于复现样本并计算可观测统计特征。
```

硬边界：
- 这些字段不能进入模型输入。

## 7. 已创建或修改的文件

### 已新增

`coworker/plans/2026-07-08-study01-e3a-risk-curve-pilot.md`

作用：E3a 执行合同。规定目标、事实、边界、特征、标签、切分、失败处理、评价、产物、stop conditions 和验收标准。

`coworker/handoffs/2026-07-08-study01-e3a-risk-curve-hermes.md`

作用：给 Hermes/执行 agent 的短 handoff。指向 plan 和 report 路径。

`Study/01-study-MDM最小偏移量优化研究/E3-risk-curve-新窗口交接.md`

作用：本文件。给新窗口恢复上下文。

### 已修改

`Study/01-study-MDM最小偏移量优化研究/03-论文骨架.md`

修改点：
- 总体逻辑把 E3 改为 sample-adaptive risk-curve。
- Ch5 边界强化：L6 不是理论上限/部署目标/单一正确训练目标。
- Ch6 改成 risk-curve learning 五字段骨架。
- 图表清单更新为 risk-curve 自适应选择流程图。
- 决策记录加入 E3a 关键决策。
- 待确认问题改为结果验收后的解释口径。

## 8. 下一步给新窗口的任务建议

如果新窗口要继续执行，建议按这个顺序：

1. 不要重新讨论 E3a 基本合同，先读本文件和 E3a plan。
2. 检查当前工作树，确认上述文件存在且未被后续改动覆盖。
3. 若用户要交给 Hermes，使用：

```text
coworker/handoffs/2026-07-08-study01-e3a-risk-curve-hermes.md
```

4. 若要 Codex 本窗口直接执行 E3a，则按：

```text
coworker/plans/2026-07-08-study01-e3a-risk-curve-pilot.md
```

5. 执行后先验收 artifacts，不要直接写 Ch6 正文。
6. 验收时用 `APPROVE / REVISE / BLOCK`，尤其检查：
   - 是否泄漏真参数；
   - L4/L5 标签是否先切分后构造；
   - combo holdout 是否按完整 `(beta,gamma/eta,n)`；
   - J1 是否用真实 selected loss 计算；
   - failure penalty 是否只来自训练集；
   - 是否 pooled + per-`n` 汇报。

## 9. 一句话结论

当前阶段已经把 E3 从“预测最优 `delta*`”重构为 **risk-curve learning 的样本自适应 `delta` 选择实验**。E3a 的设计已经讨论完并写成执行合同；整个 E3 的科学结论还没产生，必须等 E3a 实验和验收之后再决定是否推进 E3b/E3c，以及 Ch6 最终写成功、有限收益还是负结果边界。

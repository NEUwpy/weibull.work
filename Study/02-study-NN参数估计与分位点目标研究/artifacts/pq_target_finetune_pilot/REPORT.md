# 目标分位点微调 pilot

状态：描述性 pilot，不作为正式论文推断。

## 问题与最小设计

检验在已经获得稳定 Weibull 参数表示后，把训练目标从参数误差切换为
`x0.95` 相对平方误差，能否提高留出测试上的 `x0.95` 准确性。

固定 fold 1，在 `n={7,10,15,20}` 和三个 seed 上得到 12 个共同 P checkpoint，
再从每个 checkpoint 分叉：

- P-base：共同起点；
- P-continue：参数损失续训；
- Q-finetune：目标分位点损失续训。

两条续训路线均为 100 epochs、学习率 `1e-4`，并把未续训的 epoch 0 保留为
候选 checkpoint。

## 结果

| 路线 | pooled x0.95 rRMSE |
|---|---:|
| P-base | 0.2324 |
| P-continue | 0.2307 |
| Q-finetune | 0.2496 |

- Q-finetune 优于 P-base：0/12 单元；
- Q-finetune 优于 P-continue：1/12 单元；
- Q-finetune 在 12/12 单元都选择了 epoch 0 之后的 checkpoint：它确实改善了
  训练域 validation 的 Q 损失，但在 held-out gamma 层级上全部恶化；
- Q 参数没有再次严重塌缩：beta_hat 中位数 3.40、eta_hat 中位数 908，说明结果
  不能再归因于 Q 从随机初始化进入极端非辨识捷径。

## 判断

当前 Study02 fold 留出完整 gamma/eta 层级，评价的是对未见位置参数层级的外推，
不是普通同分布预测。参数监督提供的结构约束在这种外推任务上有利；Q 微调能够降低
已见层级的 validation 目标损失，却损害未见层级测试表现。

因此本 pilot 不支持“在跨 gamma 层级外推下，分位点目标优化优于参数目标优化”。
它也不能回答同分布条件下的该假设。若原研究问题是同分布分位点准确性，下一步应先
明确改用覆盖全部参数组合、仅留出独立 repeats 的分层随机 split；这是研究合同变化，
不能在看见本结果后静默替换。

# P、Q、QCP 当前结果报告

## 研究问题

当最终任务是三参数 Weibull 的 $x_{0.95}$ 时，直接目标监督 Q 能否优于参数监督 P；在 Q 只提供一个标量监督、三个内部参数可相互补偿时，P 可行域约束能否形成更稳定的 QCP 解。

## 同预算结果

三条路线统一使用最多 600 epochs、patience 60。10 seeds、4 个样本量和 5 folds 形成 200 个配对模型单元，每条路线包含 480,000 条 held-out 预测。

| 路线 | 测试 rRMSE |
|---|---:|
| P | 0.164320 |
| Q | 0.160921 |
| QCP | **0.158406** |

| 比较 | rRMSE 相对改善 | 设计级经验 bootstrap 95% CI | 有利单元 | 有利 seed |
|---|---:|---:|---:|---:|
| Q vs P | 2.069% | [1.280%,2.811%] | 172/200 | 10/10 |
| QCP vs Q | 1.562% | [1.241%,1.898%] | 196/200 | 10/10 |
| QCP vs P | 3.599% | [3.027%,4.180%] | 200/200 | 10/10 |

## 机制判断

Q 按当前预测点的寿命误差与目标敏感度更新网络，因此修正了 P 与最终寿命点之间的度量错位。但一个寿命点只提供一个标量约束，不能独立识别三个内部参数。Q 的平均参数损失为 71.714，参数补偿指数为 0.915，说明低目标误差可与严重内部补偿并存。

QCP 求解

$$
\min_\theta L_Q(\theta)
\quad\text{s.t.}\quad
L_P(\theta)\le\tau_{\mathrm{cell}}.
$$

QCP 的平均参数损失降至 0.05522，补偿指数降至 0.34532，接近 P 的 0.05385 和 0.33226；200/200 个 checkpoint 满足参数约束。现有证据支持的机制是：Q 决定目标方向，P 可行域排除参数补偿过大的近等目标解。

## 代价与边界

QCP 的目标精度最低且约束全部满足，但求解成本更高。QCP 最佳 epoch 的中位数为 159.5，90% 分位数为 362.3，3/200 个单元达到 600-epoch 上限；单 fit 中位运行时间为 87.2 s，P/Q 分别为 41.4/29.6 s。

该三路线汇总从已冻结证据派生，没有新增训练。由于既有测试结果已经打开，它属于当前论文叙事所需的 post-test sensitivity，不称为新的首次封存确认。当前 P 约束依赖仿真真参数；真实数据应用必须改用无需真参数的统计或物理结构约束。

## 证据入口

- 合同：`protocols/18-PQ-QCP同预算当前分析合同.md`
- 汇总：`artifacts/qcp_main_analysis/analysis/summary.json`
- 模型单元：`artifacts/qcp_main_analysis/analysis/model_cells.csv`
- 资源单元：`artifacts/qcp_main_analysis/analysis/resource_cells.csv`
- manifest 与哈希：`artifacts/qcp_main_analysis/manifest.json`、`SHA256SUMS`
- 主图：`figures/qcp-main/fig_qcp_main_results.png`、`.pdf`

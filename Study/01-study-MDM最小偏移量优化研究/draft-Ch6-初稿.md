# 第6章 样本自适应偏移量选择

第 5 章表明，L3-L5 oracle 层级在数值上降低了 MDM 偏移量选择的联合参数误差，且 cross-fit 审计下的 L2→L3 J₁ 降幅为 7.53%；但这些层级依赖真参数信息，不能直接用于实际部署。L6 逐样本 hindsight 又进一步降低 J1，却只能在事后知道每个样本在整个 delta 网格上的真实损失后才能选出。因此，本章的问题不是“能否用神经网络替代 MDM”，而是更具体的部署问题：

> 在真参数不可见时，能否仅凭样本可观测统计特征，为新样本选择比固定 `delta = 0.1` 和 L2 查表更合适的偏移量？

本章使用 Formal E3 的 existing-grid 证据回答这一问题。E3a 是轻量 scalar risk-curve pilot，用于验证样本特征和候选 delta 到 loss 的学习信号；E3b 是更严格的 vector-output MLP follow-up，用 5-fold full `(beta, gamma/eta, n)` combo holdout 检验未见参数组合上的选择质量。当前正文主张限定为：**在本文正式离散网格内，样本可观测特征含有实质的可部署偏移量选择信号**。本章不把 E3b 外推为 continuous-space 泛化结论，也不自动完成第 7 章的边界与稳健性验证。

因此，NN 在本章中的位置需要准确表述：它不是为了把论文改写成一个机器学习模型论文而引入的装饰性方法，而是当前用来解决样本自适应 offset selection 的主要求解器。E3b 选择 vector-output MLP，是因为本章要学习的是"样本统计特征 -> 整条 delta 风险曲线 -> 选择 delta"这一非线性映射；其他回归器或显式规则未来也可以服务同一问题，但本章的正式结果来自该 MLP 方案。

## §1 从 oracle 参照到可部署选择器

L3-L5 的最优 delta 是按真参数分组得到的。例如 L5 按 `(beta, gamma/eta, n)` 给出组级最优 delta。实际使用时，新样本的 `beta` 和 `gamma/eta` 正是待估参数，不能作为输入。因此，样本自适应选择器只能使用下列可观测信息：

```text
n,
x_(1), x_(n), range,
Q1, Med, Q3, IQR,
x_bar, s, CV,
g1, g2
```

E3a 采用 scalar risk-curve 形式：输入 `sample_features + candidate delta`，输出该候选 delta 的 raw loss。E3b 改为 vector-output MLP：输入样本特征一次性输出 26 维 loss curve，再通过 `argmin_delta` 选择偏移量。E3b 不把 candidate `delta` 放进 vector 模型输入，这更接近部署时“给定一个样本，一次性预测其风险曲线”的使用方式。

训练标签使用单样本未开方联合损失 $\ell_i(\delta)$（即 raw loss）：

```text
loss_i(delta) =
((beta_hat_i(delta)-beta)/beta)^2
+ ((eta_hat_i(delta)-eta)/eta)^2
+ ((gamma_hat_i(delta)-gamma)/eta)^2
```

最终评价仍使用全文主指标：

```text
J1 = sqrt(mean_i loss_i(delta_hat_i))
```

也就是说，模型训练拟合的是由 $\ell_i(\delta)$ 组成的 26 点单样本损失曲线，论文评价的是用预测曲线选出的 `delta_hat` 在真实 MDM 估计结果上的 $J_1=\sqrt{\operatorname{mean}_i\ell_i(\hat\delta_i)}$。predicted-loss MSE 不是本章主指标，也不将 $\ell_i$ 称为“单样本 $J_1$”。这样的写法保留了 NN 方法的必要细节，但判断标准仍是 MDM 偏移量选择是否改善，而不是模型预测误差本身是否好看。

**图 8** 将部署推断与离线训练/评价分开，概括 E3b vector-output MLP 的方法流程。

![Figure 8: E3b vector-output MLP workflow](artifacts/formal/figures/fig_ch6_vector_mlp_workflow.png)

**Figure 8.** E3b 样本自适应偏移量选择流程。部署路径只使用新寿命样本及其 13 个可观测统计特征；vector-output MLP（13–256–128–64–26）一次性预测 26 个正式候选 $\delta_j=0.02j$ 的损失，再通过 $\hat\delta_i=\arg\min_{\delta_j}\hat\ell_i(\delta_j)$ 选择偏移量。candidate $\delta$、真 $\beta$、真 $\gamma/\eta$、配置 ID、seed 和 `repeat_id` 均不进入模型输入。下方虚线仅表示离线训练标签与评价路径：训练使用 formal MC 的 raw per-sample 26 点损失曲线，评价在所选 $\hat\delta_i$ 上计算真实 selected-loss 并跨样本汇总为 $J_1$。图中不展示结果数字，定量比较以表 5 为准。

## §2 E3b 实验合同与来源

E3b 复用 E1/E2 的正式 MC 扫描数据，不重跑 MDM。正式网格为 `beta={1.5,2.0,2.5,4.0,5.0}`、`eta=1.0`、`gamma/eta={0.1,0.5,1.0}`、`n={7,10,20}`、`delta=0.00:0.02:0.50`、每个参数组合 `R=1000`。主判断采用 5-fold full `(beta, gamma/eta, n)` combo holdout，每折留出 9 个完整参数组合，合计 45,000 个测试样本。

E3b 比较以下方法：

- **Default**：固定 `delta = 0.1`。
- **L1**：全局最优常数。
- **L2**：按 `n` 查表。
- **L3-L5 oracle**：按真参数分组的参照层级。
- **L6 hindsight**：逐样本扫描网格内 hindsight benchmark。
- **Vector-MLP-L4/L5/L6**：vector-output MLP，差异在于监督粒度；这是本章主要样本自适应方法。
- **Tabular-L6**：scalar tabular baseline，用于判断向量 MLP 是否真的利用了样本特征。

数据溯源如下：

- 代码入口：`code/run_E3b_vector_mlp.py`
- 产物目录：`artifacts/formal/E3b_vector_mlp/`
- 主结果：`model_comparison.csv`
- 稳定性：`seed_stability.csv`
- 诊断：`endpoint_diagnostics.csv`、`near_optimal_diagnostics.csv`
- Ch7/E4a 消融 pilot 来源：`feature_ablation.csv`（fold 1、seed 42；不作为本章正式特征贡献结论）
- 验收报告：`E3b_acceptance_report.md`
- 契约测试：`python/tests/test_study01_e3b_contract.py`，11 passed, 0 skipped, 0 failed

需要注意 provenance 口径：`manifest.json` 记录的 `git_commit=04e99c5` 是生成时的基础 HEAD，且 `workspace_dirty=true`，因为 E3b 脚本和产物是在提交前同轮新建。最终可审计封存点是 `bedd65a`，该提交包含 E3b 脚本、产物、run log、contract tests 和 coworker 报告。正文引用时应写成“E3b package sealed at `bedd65a`”，而不是写成 `manifest.git_commit` 指向生成器提交。

## §3 主结果：样本特征在当前网格上优于简单可部署层级

E3b 的定量主判断由**表 5**承担。原 pooled J1 柱状图 `artifacts/formal/E3b_vector_mlp/plots/model_j1_comparison.png` 保留为补充诊断图，不再与主结果表重复占用主文图位。

**Table 5.** E3b combo holdout pooled 结果

| 方法 | J1 ↓ | failure rate | n=7 J1 | n=10 J1 | n=20 J1 | 性质 |
|------|-----:|-------------:|-------:|--------:|--------:|------|
| L6-hindsight | 0.494530 | 0.000 | 0.591115 | 0.503582 | 0.361479 | hindsight |
| **Vector-MLP-L6** | **0.547003** | **0.000** | **0.657558** | **0.549815** | **0.403679** | 可部署输入 |
| Tabular-L6 | 0.557849 | 0.000 | 0.666695 | 0.563795 | 0.413813 | 可部署输入 |
| L5-oracle | 0.571170 | 0.000 | 0.676581 | 0.579700 | 0.429992 | oracle |
| L4-oracle | 0.582090 | 0.000 | 0.685935 | 0.591759 | 0.442494 | oracle |
| L3-oracle | 0.585068 | 0.000 | 0.690009 | 0.592188 | 0.447339 | oracle |
| Vector-MLP-L5 | 0.596829 | 0.000 | 0.708311 | 0.605144 | 0.448010 | 可部署输入 |
| Vector-MLP-L4 | 0.606229 | 0.000 | 0.712337 | 0.617645 | 0.462204 | 可部署输入 |
| L2 | 0.632541 | 0.000 | 0.739286 | 0.644520 | 0.488235 | 可部署查表 |
| L1 | 0.632913 | 0.000 | 0.739733 | 0.645104 | 0.488235 | 可部署常数 |
| Default | 0.633219 | 0.000 | 0.739286 | 0.644520 | 0.490866 | 经验基线 |
| MLE anchor | 1.1009 | 0.304 | — | — | — | 绝对精度锚点 |

结果显示，`Vector-MLP-L6` 的 pooled J1 为 0.547003，比 L2 的 0.632541 低 0.085538，相对降幅为 13.52%。它也低于 `Tabular-L6`（0.557849），说明 vector-output MLP 不是只复现一个普通 tabular baseline，而是在同一输入边界下通过整条 risk curve 取得了更低的 selected-loss。

更重要的是，`Vector-MLP-L6` 落在 oracle 阶梯内部：它优于 L3/L4/L5 组级 oracle 参照，但仍未达到 L6 hindsight。这个结果并不矛盾。L5 是按真参数组合查表的组级 oracle，不包含同一参数组合内的逐样本形状差异；而样本统计特征包含每个样本的 order statistics、分位数、离散度和形状信息，可以在 existing-grid 上利用一部分组内差异。因此，`Vector-MLP-L6` 数值上优于 L5，不能被解读为“超过理论上界”，也不能被解读为使用了真参数输入。真正不可部署的 hindsight 参照仍是 L6，其 J1=0.494530。

## §4 按 n 分层：三个样本量方向一致

第 4 章已经说明，`n` 单独作为查表变量几乎不能带来系统改进；但 `n` 仍然是部署时已知且审稿人最关心的小样本维度。E3b 因此必须检查每个 `n` 下的方向是否一致。

`Vector-MLP-L6` 在三个样本量下均优于 L2：

- `n=7`：0.657558 vs L2 0.739286
- `n=10`：0.549815 vs L2 0.644520
- `n=20`：0.403679 vs L2 0.488235

这一结果说明，样本自适应信号不是由某一个 `n` 分层单独拉动的。小样本 `n=7` 仍是误差最高的场景，但改善方向与 `n=10`、`n=20` 一致。换言之，E3b 支持的是“在当前离散正式网格内，样本特征能够跨样本量提供更细的 delta 选择信息”，而不是“某一个样本量偶然受益”。

## §5 稳定性与网格边缘诊断

E3b 对 `Vector-MLP-L6` 进行了 3 seed 稳定性检查。

**Table 6.** `Vector-MLP-L6` seed stability

| seed | pooled J1 ↓ | n=7 J1 | n=10 J1 | n=20 J1 | extreme rate |
|-----:|------------:|-------:|--------:|--------:|--------------:|
| 42 | 0.547003 | 0.657558 | 0.549815 | 0.403679 | 0.4881 |
| 2026 | 0.546133 | 0.657899 | 0.549735 | 0.399680 | 0.4884 |
| 3407 | 0.544009 | 0.657170 | 0.545974 | 0.397339 | 0.5624 |

三组 seed 的 pooled J1 为 0.547003 / 0.546133 / 0.544009，均低于 L2=0.632541，因此本章可以写“E3b 主 J1 结论在三 seed 下方向一致且数值稳定”。但 extreme rate 有一定波动，尤其 seed 3407 上升到 0.5624，说明模型的具体 delta 分布仍具有训练敏感性。这里的 extreme rate 是 $P(\hat\delta\in\{0,0.02,0.48,0.50\})$，不是精确 endpoint rate。该敏感性不推翻 selected-loss 结论，但提示后续 E4 或 E3c 若要形成更强部署推荐，必须继续检查网格边缘行为的稳健性。

为避免合并后的 extreme/near-boundary rate 掩盖两个精确端点的不同含义，主文用**表 7**分别报告 $P(\hat\delta=0)$、$P(\hat\delta=0.50)$ 和 extreme/near-boundary rate。完整的预测 delta 分布图降为补充诊断图（当前源文件为 `artifacts/formal/E3b_vector_mlp/plots/delta_distribution_comparison.png`，最终补充图号待投稿版冻结）。

**Table 7.** `Vector-MLP-L6` 网格边缘诊断（primary seed 42）

| 汇总层级 | exact $P(\hat\delta=0)$ | exact $P(\hat\delta=0.50)$ | extreme/near-boundary rate |
|----------|------------------------:|---------------------------:|---------------------------:|
| pooled | 0.1408 | 0.0106 | 0.4881 |
| $n=7$ | 0.1139 | 0.0080 | 0.4647 |
| $n=10$ | 0.1455 | 0.0117 | 0.5065 |
| $n=20$ | 0.1628 | 0.0121 | 0.4932 |

其中 extreme/near-boundary rate 定义为 $P(\hat\delta\in\{0,0.02,0.48,0.50\})$。表 7 的精确端点拆分来自 primary seed 42；三 seed 的 pooled $J_1$ 与合并边缘率稳定性仍由表 6 单独承担，不把 seed 42 的精确端点率误写成多 seed 结果。

extreme/near-boundary rate 高不能直接判为缺陷，因为 L6 hindsight 本身的 extreme rate 为 0.6474。但这一合并指标不能混淆两个精确端点：L6-hindsight 的 $P(\delta=0)=0.4746$ 对应有方法含义的无偏移候选，而 $P(\delta=0.50)=0.0657$ 则提示人为上界可能截断了部分损失曲线。`Vector-MLP-L6` 本身精确选择上端点的比例只有 0.0106。因此，当前正确的判断标准仍是 selected-loss J1 和 near-optimal/regret，但对网格充分性的疑问必须交给 Ch7 的扩展上界敏感性检查。

## §6 near-optimal 诊断

E3b 的 near-optimal 诊断进一步支持主结果。相对 L2，`Vector-MLP-L6` 降低了平均 regret；near-5% hit rate 由 0.1878 提高到 0.4090，增加 22.12 个百分点。

**Table 8.** Near-optimal / regret 诊断

| 方法 | mean regret ↓ | mean relative regret ↓ | near 1% | near 2% | near 5% |
|------|--------------:|-----------------------:|--------:|--------:|--------:|
| **Vector-MLP-L6** | **0.054652** | **2.155035** | **0.3138** | **0.3481** | **0.4090** |
| Tabular-L6 | 0.066636 | 3.173833 | 0.2854 | 0.3083 | 0.3587 |
| L2 | 0.155548 | 7.427484 | 0.0919 | 0.1221 | 0.1878 |

这说明 `Vector-MLP-L6` 的优势并非只来自少数极端样本拉低 J1；它在更广泛样本上提高了接近逐样本最优 delta 的概率。L2 的 near 5% 仅为 0.1878，而 `Vector-MLP-L6` 为 0.4090。

本章不进一步判断 13 个可观测特征中哪些信息组承担主要贡献。现有 fold 1、seed 42 的 `feature_ablation.csv` 只作为 Ch7/E4a 正式消融的 pilot 来源，不在 Ch6 提前写成特征重要性结论。Ch7 将在跨 fold、seed 和 $n$ 的正式合同下比较 full features、`n only`、scale/quantile 与 shape 等特征组，再判断样本内部信息是否稳定超越仅使用 $n$ 的选择器，以及形状信息能否承接第 5 章观察到的 $\beta$ 主效应。

## §7 本章边界

本章的结论必须保持四个边界。

第一，E3b 是 **existing-grid** 结论。训练和测试均来自本文正式离散网格，只是通过 full-combo holdout 避免同一参数组合的 repeat 同时出现在训练和测试中。因此，E3b 可以支撑“当前正式离散网格上存在可部署样本自适应信号”，但不能单独支撑“连续参数空间上稳定泛化”的部署推荐。

第二，E3b 的模型输入没有真参数泄漏。真参数和 `repeat_id` 只用于复现样本、计算可观测样本统计特征和离线 loss 标签；模型输入不包含 `beta`、`eta`、`gamma`、`gamma/eta`、参数组合 ID、seed 或 `repeat_id`。这一点已由 contract tests 验证。

第三，E3b 不是把 NN 作为论文目的，但也不能把 NN 写到可有可无。NN/Vector-MLP 是本章解决样本自适应 delta 选择问题的主要方法；本章真正回答的是：当 Default/L1/L2 收益很小、L3-L5 又不可部署时，样本可观测特征能否经由这种风险曲线学习器提供中间桥梁。E3b 的答案是肯定的，但限定在现有正式离散网格内。

第四，当前 $\delta\le0.50$ 是已冻结的 existing-grid 合同，不是已证明充分的连续搜索上界。L6 在上端点的 6.57% 质量要求 Ch7 单独检查扩大上界后的风险曲线与选择敏感性；在该检查完成前，Ch6 只报告当前网格内的选择质量。

## §8 本章小结

本章从 Ch5 的 oracle 参照出发，检验了真参数不可见条件下的样本自适应偏移量选择。E3b 的核心结果是：

- `Vector-MLP-L6` pooled J1=0.547003，比 L2=0.632541 低 13.52%，也低于 L1=0.632913 和 Default=0.633219。
- `Vector-MLP-L6` 在 `n=7/10/20` 三个分层上均优于 L2，说明收益不是单一样本量驱动。
- 3 seed 下 pooled J1 为 0.547003 / 0.546133 / 0.544009，主 J1 结论稳定。
- near-optimal 诊断显示，`Vector-MLP-L6` 相比 L2 更常选到接近逐样本最优的 delta，说明 MLP 学到的是有用的选择信号，而不是单纯复现固定查表。
- extreme/near-boundary 选择率较高，但它不等于 exact endpoint rate。L6 的下端点质量反映无偏移候选的价值，上端点质量则提示网格截断；二者必须分开报告并与 selected-loss 共同解释。

结论：**在本文正式离散网格内，样本可观测特征能够为 MDM 偏移量选择提供实质性信息；`Vector-MLP-L6` 相对 L2 的 pooled J1 降幅为 13.52%，且在三个 $n$ 分层和三个训练 seed 下方向一致。** 这说明 L3-L6 oracle 阶梯中的一部分收益可以通过可部署样本特征近似获得。这里报告的是效应幅度与稳健性，不使用未定义的“统计显著”措辞。下一章需要回答的是：这种 existing-grid 信号在更宽参数范围、边界样本量、失败处理和计算成本约束下是否仍然可靠。

---

【作者备注】

- Ch6 的主文/补充层级已冻结：Figure 8 由可复现的 vector-output MLP 方法流程图承担；原 pooled J1 柱状图与 delta distribution diagnostic plot 均降为补充图。主文定量证据由主结果表、三 seed 稳定性表和分列 exact $P(\delta=0)$、exact $P(\delta=0.50)$、extreme/near-boundary rate 的紧凑表承担。最终补充图号和表格版式仍待投稿版统一冻结。
- 若后续不启动 E3c/E4，Ch7 和 Discussion 必须把本章结论限定为 existing-grid，不写成连续空间部署推荐。
- `Vector-MLP-L6` 超过 L5-oracle 时，正文必须强调 L5 是组级 oracle，不是逐样本上界；避免审稿人误解为层级定义矛盾。

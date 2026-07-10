# 06 grill-me 论文完善续接记录

> 更新日期：2026-07-11
> 用途：在新 Codex 窗口、上下文压缩或多 agent 并行时，无损续接 Ch1–Ch6 的 `grill-me` 论文完善工作。本文件是续接摘要，精确公式、数值与证据仍以各正文草稿、`01-证据索引.md`、`02-实验协议.md` 和正式 artifacts 为准。

## 新窗口最小读取顺序

1. 根目录 `README.md`。
2. 本 Study 的 `README.md`。
3. 本文件。
4. `03-论文骨架.md` 的“决策记录”。
5. 当前要继续审计的章草稿；需要核对证据时再读 `01-证据索引.md` 和 `02-实验协议.md`。

## 不可偏移的论文主线

本文是 MDM 系列的第三步推进：把前作中经验设定的 offset `delta=0.1` 推进为一个可按信息层级定义、评价和选择的决策问题。主要贡献顺序是：

1. 建立 Default–L6 信息层级，区分可部署、oracle 和 hindsight。
2. 用正式 MC 证据评估各层级的收益与边界。
3. 在真参数不可见时，以 NN/Vector-MLP 作为主要求解器，学习“样本可观测特征 → 26 点损失曲线 → 选择 delta”。

NN 是 Ch6 的主要实现方法，但不是论文目的。Ch1–Ch6 完成 formal existing-grid 主体闭环；Ch7 以后负责稳健性、外推边界和真实数据适用性。

## 截至第 26 问的已确认决策

| 项 | 已锁定决策 | 落地位置 |
|---:|---|---|
| 1 | 论文首先是 MDM offset 选择的层级化完善与正式评估，NN 是求解方法 | `00`、`03`、Ch1、Ch6 |
| 2 | Ch1–Ch6 构成 existing-grid 主体闭环；Ch7+ 处理泛化、边界和真实数据 | `00`、`03` |
| 3 | Ch1 从 MDM 系列第三步起笔，不制造全面 MLE/LSE 横评预期 | Ch1、`03` |
| 4 | 真实数据采用较大寿命数据，重复抽取 $n=7/10/20$ 小样本，其余样本留出评价 | `00`、`02`、`03` |
| 5 | 真实数据主证据是留出分布表现；完整数据参数估计只作辅助，不称为真值 | `00`、`02`、`03` |
| 6 | 真实数据主指标为留出经验 CDF 距离；支撑集违规、寿命分位数等作辅助 | `02`、`03` |
| 7 | Ch1 结尾用一个自然段收束全文路线，不写编号贡献列表 | Ch1、`03` |
| 8 | Ch1 直接点明神经网络是主要实现，但不把论文改写为 ML 目的 | Ch1、Ch6、`03` |
| 9 | Ch1 不配图；机制图归 Ch2，层级框架归 Ch3 | Ch1、`03` |
| 10 | Figure 1 证明 delta 改变 gamma 搜索判据与有限样本分布；0.1 不是逐样本必然改善 | Ch2、Figure 1 provenance |
| 11 | Figure 1 为真实 gradient traces + gamma-hat ECDF + 配对绝对归一化误差散点 | Ch2、`plot_fig_diagnostics.py` |
| 12 | 区分“工程求解器返回候选估计”与“约束域内始终存在内部 root”；后者不成立 | Ch2、`03` |
| 13 | 尊重第二篇 MDM 原文，继续使用 $\nabla\gamma$，并定义为 $\sigma_{\eta,\min}(\gamma)$ 对 gamma 的离散梯度 | Ch2、作者备注 |
| 14 | Figure 1 保留 $W(2,1000,1000),n=7$ 展示尺度；B/C 来自尺度等变的 $W(2,1,1)$ 正式 MC | Ch2、provenance |
| 15 | Figure 1 Panel A 用对称规则选取“变化最小、改善组中位、变差组中位” | provenance、图脚本 |
| 16 | Ch3 Table 1 是权威层级合同；Figure 2 只是极简视觉路线图 | Ch3、Figure 2 |
| 17 | Figure 2 只呈现最终论文逻辑，不呈现 completed/pending 或 E3a/E3b/E3c 内部状态 | Ch3、`plot_fig1.py` |
| 18 | 区分单样本损失 $\ell_i(\delta)$、L1–L5 组级风险 $R_L(g,\delta)$ 和已选规则的汇总 $J_1$；L6 逐样本最小化 $\ell_i$ | Ch3、Ch5、Ch6、`02` |
| 19 | L1 的“全局”是 45 个正式设计格点等权的 pooled optimum，不代表真实参数出现频率 | Ch3、Ch4、`02`、`03` |
| 20 | 补出 MDM 尺度等变性推导，并用 $c=1000$、$\delta=0/0.1/0.5$ 回归测试锁定；据此固定 $\eta=1$ | Ch2、Ch3、`test_mdm_s49.py` |
| 21 | 分开 exact $P(\delta=0)$、exact $P(\delta=0.50)$ 和 extreme/near-boundary rate；扩大上界敏感性交给 Ch7 | Ch5、Ch6、`02`、E3c/E4 备忘 |
| 22 | 使用现有 MC 缓存对 L1–L5 做 5 折 repeat-level cross-fit 选点/评价分离审计；L6 保持 hindsight | `E1_E2_crossfit/`、Ch3–Ch5、`01`、`02` |
| 23 | 未定义显著性检验时不用“显著”作普通形容词；改报效应幅度、按 n 一致性和多 seed 稳定性 | Ch4、Ch6、`03` |
| 24 | Ch6 的完整 delta distribution diagnostic plot 降为补充图；主文用紧凑表按 pooled/n 分列 exact 下端点、exact 上端点和 extreme/near-boundary rate；三 seed 表继续只承担稳定性职责 | Ch6、`03`、`04` |
| 25 | Ch6 主文 Figure 8 改为 vector-output MLP 方法流程图；原 pooled J1 柱状图降为补充图，Table 5 继续承担定量结果权威 | Ch6、`plot_ch6_workflow.py`、Figure 8、`03`、`04` |
| 26 | 正式 feature-group ablation 归 Ch7/E4a；Ch6 删除原 Table 9，只保留前向说明，不在单 fold pilot 上提前作稳定特征贡献结论 | Ch6、`01`、`02`、`03`、`04`、`05` |

## 长期工作规则

- 使用 `grill-me` 时一次只问一个问题，给出推荐答案，等待用户明确锁定。
- 可从代码、artifacts 或原文发现的事实不反问用户；先核对，再就需要作者判断的部分提问。
- 每次确认后立即同步相关草稿、骨架、协议或进度文档，不只留在对话中。
- 替换旧图前必须将旧 PNG/SVG/PDF、源脚本和恢复说明完整归档到 `history/figures/`；不直接删除或覆盖后不留恢复路径。
- 尊重 MDM 原文术语和记号；如需更正严谨性，优先增加定义与边界，不无故改名。

## 本轮已产生的关键可恢复产物

### Figure 1

- 当前图：`artifacts/formal/figures/fig_offset_mechanism.{png,svg,pdf}`。
- 生成脚本：`code/plot_fig_diagnostics.py`。
- provenance：`code/_fig1_sample_provenance.md`。
- 历史版本：
  - `history/figures/2026-07-10-fig_offset_mechanism-rev4/`
  - `history/figures/2026-07-10-fig_offset_mechanism-rev5/`

### Figure 2

- 当前图：`artifacts/formal/figures/fig1_framework.{png,svg,pdf}`。
- 生成脚本：`code/plot_fig1.py`。
- 历史版本：`history/figures/2026-07-10-fig1_framework-rev1/`。

### Figure 8

- 当前主图：`artifacts/formal/figures/fig_ch6_vector_mlp_workflow.{png,svg,pdf}`。
- 生成脚本：`code/plot_ch6_workflow.py`。
- 图形合同：`code/_fig_ch6_workflow_contract.md`。
- 原 pooled J1 柱状图保留在 `artifacts/formal/E3b_vector_mlp/plots/model_j1_comparison.png`，现为补充诊断图，未删除或覆盖。

### E1/E2 cross-fit 审计

- 代码：`code/analyze_E1_E2_crossfit.py`。
- 测试：`python/tests/test_study01_e1_e2_crossfit.py`。
- 产物：`artifacts/formal/E1_E2_crossfit/`。
- 核心结果：
  - L1 = 0.632913，L2 = 0.632732，L3 = 0.585068，L4 = 0.582585，L5 = 0.571924。
  - 相对同批选点/评价，L2/L4/L5 仅上调 0.030% / 0.085% / 0.132%。
  - L1 五折都选 0.08；L3 的 5 个 beta 选点五折全部稳定。
  - L6 不进入 cross-fit，仍是 existing-grid hindsight benchmark。

## 当前验证状态

最近联合命令：

```text
python -m pytest python/tests/test_study01_e1_e2_crossfit.py python/tests/test_mdm_s49.py python/tests/test_study01_framework_figure_contract.py python/tests/test_study01_figure1_contract.py -q
```

第 25 问新增 Figure 8 合同测试后，最近联合命令还应加入：

```text
python/tests/test_study01_ch6_workflow_figure_contract.py
```

最近结果：第 26 问同步并完成 Ch6/Ch7 消融归属检查后重新运行，**18 passed**。此后若继续修改，新窗口必须重新运行而不直接沿用该数字。

## 当前共享工作区的所有权边界

当前分支为 `main`，工作区尚未提交。同一共享工作区中已有 Hermes/E4 并行工作，包括但不限于：

- `E4-validation-suite-状态交接.md`
- `code/run_E4_formal_validation.py`
- `code/run_E4_mc_generation.py`
- `artifacts/formal/E4_robustness/`
- `coworker/reports/2026-07-10-study01-e4-step2-mc-generation-hermes.md`

当前 `git status` 还可见 E4 chunk 的删除/重建状态。这些均不属于本轮 Ch1–Ch6 所有权。新窗口不得回退、删除、覆盖、暂存或提交它们；如需集成，先单独核对 Hermes 分支与交接文档。

## 下一窗口的续接点

- 第 24 问已确认并落地：Ch6 的完整 delta distribution diagnostic plot 降为补充图；主文改用 pooled/按 $n$ 分层的精确上下端点与 near-boundary 紧凑表，三 seed 表保持稳定性职责。
- 第 25 问已确认并落地：Ch6 Figure 8 改为可复现的 vector-output MLP 方法流程图；原 pooled J1 柱状图降为补充图，Table 5 保持结果权威。
- 第 26 问已确认并落地：正式 feature-group ablation 归 Ch7/E4a；Ch6 删除原 Table 9，只保留前向说明，当前 fold 1、seed 42 结果只作 Ch7 实验设计的 pilot 来源。
- 第 27 问尚未提出。继续时从 Ch4–Ch6 的剩余主张、图表和证据对齐开始，仍保持一次一问。
- 本轮改动尚未提交或暂存；不要因开新窗口而默认它们已封存。

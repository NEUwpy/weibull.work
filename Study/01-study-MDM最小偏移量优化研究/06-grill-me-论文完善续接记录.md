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

## 截至第 61 问的已确认决策

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
| 27 | Ch6 第一主张锚定相对最佳简单可部署层级 L2 的 13.52% pooled $J_1$ 降幅及其跨 $n$/seed 一致性；低于组级 L5 只作参照定位，不写成“超越 oracle”；L6 保持为逐样本 hindsight 参照 | Ch6、`03` |
| 28 | MLE 退出 Ch3 独立小节、Ch5 Figure 5、Table 4 和 Ch6 Table 5；仅在 Ch5 正文保留简短绝对精度背景，成对报告收敛样本 $J_1$ 与失败率，不展开横向排名；实现合同保留在 `02`，需要分层完整数字时只放补充表 | Ch3、Ch5、Ch6、`02`、`03`、`05`、`plot_fig3_fig4.py` |
| 29 | Figure 4 保留在 Ch4 主文，专门证明按 $n$ 条件化后 $\beta$ 异质性仍未消失，因而 L2 仍难产生收益；Figure 3 只承担 L1 全局抵消解释，两图不重复泛化的 $\beta$ 主效应口径 | Ch4、`03`、`04` |
| 30 | Figure 5 Panel A 只展示 Default–L6 绝对 $J_1$；Panel B 从相对 Default 的累计改善曲线改为相邻层级的逐级相对 $J_1$ 降幅，与 Table 4 同口径；L2→L3=7.51%，L5→L6=13.42% | Ch5、`03`、`04`、`plot_fig3_fig4.py`、`test_study01_fig3_ladder_contract.py` |
| 31 | L2→L3 命名为引入 $\beta$ 组级信息的主要增益；L5→L6 单独命名为 hindsight gap，表示从组级选择到逐样本事后选择的决策粒度变化，不将两者写成同质信息跳点 | Ch5、`03`、`04`、`plot_fig3_fig4.py`、`test_study01_fig3_ladder_contract.py` |
| 32 | Figure 7 保留在 Ch5 主文，唯一职责是解释 hindsight gap 的逐样本来源与不可部署性；Panel A 展示上下精确端点质量，Panel B 显示给定 $\beta$ 后仍有组内逐样本分散，不重复 Figure 6 的 $\beta$/$n$ 选点跨度比较，不将 L6 分布写成部署查表 | Ch5、`03`、`04` |
| 33 | Ch6 Table 6 只保留 pooled 与分 $n$ 的 $J_1$ 跨 seed 稳定性；三 seed 的 extreme/near-boundary rate 移至新建 `draft-补充材料.md` 的 Supplementary Table S1；Ch6 只保留 selected-loss 稳定不等于选择分布完全稳定的限制性说明 | Ch6、`03`、`04`、`draft-补充材料.md` |
| 34 | Ch6 Table 7 保留主文，唯一职责是拆解 primary seed 42 下精确上下端点与 near-boundary 构成；不承担跨 seed 稳健性判断，也不构成部署推荐 | Ch6、`03`、`04` |
| 35 | Ch6 Table 8 从主文删除 mean relative regret，只保留 mean regret 与 near-1%/2%/5% hit rate；完整 relative-regret 诊断继续留在正式 artifact | Ch6、`03`、`04` |
| 36 | Ch6 Table 8 只说明模型差异同时体现在 pooled $J_1$ 与 near-hit 比例，删除“并非由少数极端样本驱动”的强判断；后者需逐样本损失差分布证据 | Ch6、`03`、`04` |
| 37 | Tabular-L6 从 Ch6 方法清单、Table 5、Table 8 与正文比较中移除，代码和 sealed artifact 只作 provenance 保留；公平方法比较推迟到 Ch7 正式消融完成之后 | Ch6、`01`、`03`、`04` |
| 38 | Ch6 Table 5 删除所有方法均为 0 的 failure-rate 列，正文只用一句说明当前 selected-point failure rate 均为 0；更宽范围的失败处理稳健性留给 Ch7 | Ch6、`03`、`04` |
| 39 | Ch6 Table 5 保留 Default、L1–L6 参照与 Vector-MLP-L4/L5/L6 全部 10 行，完整展示当前比较景观；正文仍以 L2、L5、L6 为主张锚点 | Ch6、`03`、`04` |
| 40 | Ch6 解释 Vector-MLP-L4/L5/L6 的 pooled $J_1$ 与逐级降幅，但限定为 primary E3b 的描述性监督粒度对应关系；只有 L6 有三-seed检查，正式消融仍归 Ch7 | Ch6、`03`、`04` |
| 41 | Ch6 Table 5 继续按 pooled $J_1$ 从低到高排列以直观显示效果，不按信息角色重排；方法名、`性质`列与正文承担信息边界区分 | Ch6、`03`、`04` |
| 42 | Ch6 Table 5 `性质`列显式区分 Vector-MLP 的可部署输入与 L4/L5/L6 离线监督标签，并把 L3–L5/L6 标为组级 oracle/逐样本 hindsight 参照 | Ch6、`03`、`04` |
| 43 | Ch6 分 $n$ 段用相对 L2 的 11.05%/14.69%/17.32% 降幅替代重复的绝对值，并限定三个正式 $n$ 水平的递增只作描述、不外推单调规律 | Ch6、`03`、`04` |
| 44 | Ch6 三-seed稳定性改报 pooled $J_1$ 范围 0.544009–0.547003、最大差值 0.002994（均值的 0.55%）及相对 L2 降幅 13.52%–14.00%；逐-seed值留在 Table 6 | Ch6、`03`、`04` |
| 45 | Ch6 开篇、结论与骨架删除“实质信号”“明显优于”等抽象判断，直接写相对 L2 的 13.52% pooled $J_1$ 降幅及跨 $n$/三-seed方向一致，并保留 existing-grid 边界 | Ch6、`03`、`04` |
| 46 | Ch4 将“样本量强烈影响 $J_1$ 水平”改为 L2 下 $n=20$ 相对 $n=7$ 低 33.96%，同时指出最优 $\delta$ 仅由 0.10 移至 0.08 | Ch4、`03`、`04` |
| 47 | Ch4 删除 $\gamma/\eta$ 差异可能源于“搜索敏感性”的机制猜测，只保留次级经验模式并声明现有证据不识别其形成机制 | Ch4、`03`、`04` |
| 48 | Ch4 用各 $\beta$ 下的改善组合数与精确改善/恶化范围替代“稳定改善约2%–4%”，直接量化 L1 相对 Default 的方向反转 | Ch4、`03`、`04` |
| 49 | Ch4 删除“工程上可忽略”“几乎没有收益”“收益极小”等未定义阈值判断；改报 0.048%/0.059%，并与按 $\beta$ 分组的 0.77%–8.11% 变化比较 | Ch4、`03`、`04` |
| 50 | 用 300 个正式 seed 样本轻量审计 Ch5 的 $\beta$–profile 解释；局部梯度斜率跨 $n$ 方向一致，只保留“与机制解释一致”而不作因果证明 | Ch5、`E2_beta_profile_audit/`、`01`、`03`、`04` |
| 51 | Ch5 删除“迅速衰减”“边际递减区”；将 7.51%→0.51%→1.88% 写成后两级均低于 L2→L3但彼此不单调 | Ch5、`01`、`03`、`04` |
| 52 | Ch5 删除 L3 $\delta^*$ 与 $\beta$“强负相关”的形容；改报 5 个设计点 0.36/0.20/0.12/0.04/0.04、单调不增与 $\rho=-0.975$，不外推总体相关性 | Ch5、`03`、`04` |
| 53 | Ch5 Figure 6 删除“$\beta$ 主效应、$n$ 微弱调节”；改报跨 $\beta$/$n$ 平均跨度 0.37/0.08、比值 4.67 和 L3→L4 pooled $J_1$ 降幅 0.51% | Ch5、`03`、`04` |
| 54 | Ch5 L5 删除“$\gamma/\eta$ 效应同样微弱”和单例概括；改报 15 个 $(\beta,n)$ 单元内跨度分布与 L4→L5 pooled $J_1$ 降幅 1.88% | Ch5、`03`、`04` |
| 55 | Ch5 删除对 13.42% hindsight gap 中结构性与随机性来源比例的无证据归因；端点质量与组内分散只支撑不可部署边界 | Ch5、`03`、`04` |
| 56 | Ch5 cross-fit 段删除“留出 $J_1$ 只轻微上调”；改报 L2/L4/L5 上调 0.030%/0.085%/0.132%、最大 0.132% 和 L2→L5 留出顺序 | Ch5、`03`、`04` |
| 57 | Ch5 将“最大逐级增益”限定于 L2→L5 组级信息层级；L2→L3=7.51%，L5→L6=13.42% hindsight gap 不参与该排序 | Ch5、`03`、`04` |
| 58 | Ch5 §2 标题改为“引入 $\beta$ 组级信息带来 7.51% 的逐级降幅”；提问改为 $\beta$ 分组对应的选点与 profile 几何变化 | Ch5、`03`、`04` |
| 59 | Ch6 区分“部署时可获得的输入”与“模型或选择信号已经可部署”；E3b 只支撑 Vector-MLP 在正式离散网格 combo-holdout 上取得改进，后者仍待 Ch7 与真实数据验证 | Ch6、`03`、`04` |
| 60 | Ch6 将 near-5% hit rate 从 18.78% 提高到 40.90% 限定为选点改善的逐样本诊断证据，不据此识别 MLP 内部表示或排除未经测试的固定规则 | Ch6、`03`、`04` |
| 61 | Ch4–Ch6 删除“无法系统性超越”“几乎不能系统改进”；统一报告 L1 相对 Default、L2 相对 L1 的 0.048%/0.059% 降幅，并与按 $\beta$ 分组的 0.77%–8.11% 变化作量级比较 | Ch4–Ch6、`03`、`04` |

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

### Ch5 β–profile 轻量机制审计

- 合同：`code/_ch5_beta_profile_audit_contract.md`。
- 计划：`code/_ch5_beta_profile_audit_plan.md`。
- 代码：`code/analyze_beta_profile_audit.py`。
- 测试：`python/tests/test_study01_beta_profile_audit.py`。
- 产物：`artifacts/formal/E2_beta_profile_audit/`。
- 固定设计：$\eta=1$、$\gamma/\eta=0.5$，5 个 $\beta$ × 3 个 $n$ × 20 repeats，共 300 个正式 `study01_v1` seed 样本；每个样本只运行一次 `MDM.run(trace=True, offset=0.1)`。
- 核心结果：局部梯度斜率与 $\beta$ 的 Spearman $\rho$ 在 $n=7/10/20$ 下分别为 −0.463、−0.495、−0.529；真实 $\gamma$ 处梯度方向不一致。
- 解释边界：支持“profile 曲线几何随 $\beta$ 系统变化，与机制解释一致”，不支持“尾部形态因果地决定最优 $\delta$”或“机制已证明”。

## 当前验证状态

最近联合命令：

```text
python -m pytest python/tests/test_study01_beta_profile_audit.py python/tests/test_study01_e1_e2_crossfit.py python/tests/test_mdm_s49.py python/tests/test_study01_framework_figure_contract.py python/tests/test_study01_figure1_contract.py python/tests/test_study01_ch6_workflow_figure_contract.py python/tests/test_study01_fig3_ladder_contract.py -q
```

最近结果：第 61 问将 Ch4–Ch6 的“无法系统性超越”“几乎不能系统改进”统一改为 L1/L2 的 0.048%/0.059% 降幅及其与按 $\beta$ 分组 0.77%–8.11% 变化的量级比较后重新运行，**27 passed**；禁用措辞已从 Ch4–Ch6 正文清除，骨架叙述已同步，旧词只保留在决策记录的“已删除”历史说明中，同轮 `git diff --check` 通过。此后若继续修改，新窗口必须重新运行而不直接沿用该数字。

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
- 第 27 问已确认并落地：Ch6 第一主张锚定 L2 可部署对比；组级 L5 和逐样本 L6 只按各自信息边界承担参照职责，不使用“超越 oracle”标题化口径。
- 第 28 问已确认并落地：MLE 只作 Ch5 正文背景锚点，不再进入 Figure 5 或 Ch5/Ch6 主表；旧 Figure 5 图像与脚本已完整归档到 `history/figures/2026-07-11-fig3_ladder-rev1/`。
- 第 29 问已确认并落地：Figure 3 解释 L1 全局抵消，Figure 4 保留主文并专门解释为何按 $n$ 条件化后 L2 仍难改进。
- 第 30 问已确认并落地：Figure 5 Panel A 展示绝对 $J_1$，Panel B 展示逐级相对 $J_1$ 降幅，与 Table 4 保持同一改善口径；修改前的无 MLE 累计曲线版本已归档到 `history/figures/2026-07-11-fig3_ladder-rev2/`。
- 第 31 问已确认并落地：L2→L3 是主要信息增益，L5→L6 是 hindsight gap，两者不再并称为同质跳点；修改前的“two major jumps”版本已归档到 `history/figures/2026-07-11-fig3_ladder-rev3/`。
- 第 32 问已确认并落地：Figure 7 保留 Ch5 主文，只用于解释 hindsight gap 的逐样本来源及不可部署性，不把 L6 选点分布写成部署推荐。
- 第 33 问已确认并落地：Table 6 只承担跨 seed 主 $J_1$ 稳定性；边界选择率跨 seed 数值移至 Supplementary Table S1，Ch6 只保留一句限制性说明。
- 第 34 问已确认并落地：Table 7 保留 Ch6 主文，只承担 primary seed 42 的边界选择构成解释；跨 seed 稳健性与部署推荐均不由该表承担。
- 第 35 问已确认并落地：Table 8 删除对小分母敏感的 mean relative regret，主文只保留 mean regret 与 near-1%/2%/5% hit rate；完整诊断继续保留在正式 artifact。
- 第 36 问已确认并落地：Table 8 的解释收紧为 pooled $J_1$ 之外的 near-hit 补充观测，不再用现有表格排除少数极端样本驱动。
- 第 37 问已确认并落地：Ch6 不再使用 Tabular-L6 作学习器比较，保持样本自适应 MDM 偏移量选择主线；方法比较推迟到 Ch7 正式消融之后。
- 第 38 问已确认并落地：Table 5 删除不区分方法的 failure-rate 列，当前零失败率转为正文边界说明。
- 第 39 问已确认并落地：Table 5 不压缩为四行，保留全部 10 行比较；表格完整展示与正文主张聚焦分开处理。
- 第 40 问已确认并落地：Vector-MLP-L4/L5/L6 三行获得描述性解释，但不升级为已稳定验证的监督粒度消融结论。
- 第 41 问已确认并落地：Table 5 保持按 $J_1$ 排序，效果可读性优先；排序不表示不同信息边界的方法可无条件横向等价。
- 第 42 问已确认并落地：Table 5 `性质`列现在承担部署输入、离线监督、oracle 与 hindsight 的边界区分。
- 第 43 问已确认并落地：分 $n$ 正文改报效应幅度，绝对值留在 Table 5，并加入不外推单调规律的边界。
- 第 44 问已确认并落地：三-seed“稳定”改为范围、差值、相对均值比例与效应区间的具体量化。
- 第 45 问已确认并落地：Ch6 首尾主张统一为具体效应幅度、一致性证据与 existing-grid 边界。
- 第 46 问已确认并落地：Ch4 用33.96%量化样本量对误差水平的影响，并与最优偏移方向变化有限分开表述。
- 第 47 问已确认并落地：Ch4 的 $\gamma/\eta$ 结果回到观测层，不再承担未经验证的机制解释。
- 第 48 问已确认并落地：Ch4 的 $\beta$ 方向反转改由组合计数和精确幅度范围支撑。
- 第 49 问已确认并落地：Ch4 的 L1/L2 小幅收益不再使用未定义工程阈值，而改用 0.048%/0.059% 与 0.77%–8.11% 的量级比较。
- 第 50 问已确认并落地：Ch5 的 $\beta$–profile 解释经 300 样本轻量审计后保留为一致性证据，但因果链仍明确未识别。
- 第 51 问已确认并落地：Ch5 的后续组级收益改为精确、非单调表述，不再使用“迅速衰减”或“边际递减区”。
- 第 52 问已确认并落地：Ch5 的 L3 $\beta$–$\delta^*$ 关系改为 5 个设计点上的单调不增与 $\rho=-0.975$，并明确末两点并列及总体外推边界。
- 第 53 问已确认并落地：Ch5 Figure 6 改用跨 $\beta$/$n$ 的精确选点跨度与 L3→L4 效应幅度，不再使用“主效应/微弱调节”的术语判断。
- 第 54 问已确认并落地：Ch5 L5 改用 15 个 $(\beta,n)$ 单元的跨 $\gamma/\eta$ 选点跨度分布及 1.88% 逐级收益，不再用“同样微弱”或单个组合代表整体。
- 第 55 问已确认并落地：Ch5 不再声称 13.42% hindsight gap 中有“相当部分”来自偶然性，明确当前未分解结构性与随机性来源。
- 第 56 问已确认并落地：Ch5 cross-fit 段用精确偏差幅度和留出 $J_1$ 顺序替代“轻微上调”。
- 第 57 问已确认并落地：Ch5 的“最大逐级增益”只在 L2→L5 组级信息层级内比较，13.42% hindsight gap 明确排除在该排序之外。
- 第 58 问已确认并落地：Ch5 §2 标题和机制提问直接对应7.51%组级收益、选点与 profile 几何证据，不再使用“主要驱动/主要分层变量”。
- 第 59 问已确认并落地：Ch6 不再把 existing-grid combo-holdout 改进直接称为“可部署样本自适应信号”，而是区分部署时可获得的输入与尚待验证的模型可部署性。
- 第 60 问已确认并落地：Ch6 的 near-optimal 诊断只承担逐样本选点改善证据，不再声称识别了 MLP 内部表示或排除了未经测试的固定规则。
- 第 61 问已确认并落地：Ch4–Ch6 不再把正向但幅度较小的 L1/L2 降幅写成“无法系统性超越”，而是统一报告精确幅度及其与按 $\beta$ 分组变化的量级差异。
- 本轮 Ch4–Ch6 `grill-me` 主张一致性拷问已收口，当前没有待提出的下一问；后续如进入投稿全文复核，应另开一轮审查并继续保持一次一问。
- 本轮改动尚未提交或暂存；不要因开新窗口而默认它们已封存。

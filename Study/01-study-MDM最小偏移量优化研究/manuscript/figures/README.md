# Study01 论文图表工作区

这个目录集中保存论文 Markdown 稿件实际引用的图像、表格、制图入口和数据来源说明。它是论文写作侧的工作区，不替代 `D:/weibull` 中已经封存的正式实验产物。

## 目录

| 目录 | 内容 |
|---|---|
| `main/` | 正文图 1–9 |
| `supplementary/` | 补充材料图 |
| `tables/` | 正文与补充材料表格的 Markdown/CSV 版本 |
| `scripts/` | 投稿图唯一绘制入口和自动质检程序 |
| `data/` | 数据不复制入本目录，只记录正式数据库和计算后数据的准确位置 |
| `provenance/` | 当前正式图表包的 manifest、哈希清单和原始说明快照 |
| `archive/` | 已被新版替换但暂不删除的旧图、旧源数据与版本快照 |

每张图的结论、来源和生成函数见 [`figure-index.md`](figure-index.md)，机器可读配置见 [`figure_sources.json`](figure_sources.json)。

## Markdown 引用

从当前活动稿 `../Study01论文初稿-v1.5.md` 引用正文图：

```markdown
![正偏移量与固定基准](figures/main/fig1_offset_baseline.png)

![样本自适应偏移量选择流程](figures/main/fig2_adaptive_selection_method.png)

![固定宽度参数域与统一低风险偏移量](figures/main/fig3_beta_domain_sensitivity.png)

![不同信息条件下的参数空间划分](figures/main/fig4_information_spaces.png)

![不同信息条件下的估计风险](figures/main/fig5_information_level_results.png)

![不同样本量下的联合估计误差](figures/main/fig6_per_n_J1.png)

![偏移量选择机制](figures/main/fig7_selector_mechanism.png)

![样本实现对MDM偏移量的影响](figures/main/fig8_decision_mechanism.png)

![支撑验证汇总](figures/main/fig9_support_validation.png)
```

补充材料图使用 `figures/supplementary/文件名.png`。表格可直接复制 `tables/*.md`，CSV 保留为数值核对源。

## 当前质量状态

当前活动稿使用 16 张图，另保留一张初始化稳定性复核图，均已按 SCI 投稿图标准完成重画：

- 图 1 同时呈现全局风险曲线、低风险区放大，以及无偏移与固定正偏移量在 160 个参数组合内的重复抽样稳定性；
- 图 2 分开训练与应用流程，消除了裁切、文字碰撞和职责混淆；
- 图 3 先在 $\beta$–$\gamma/\eta$–$n$ 完整设计空间中标出两个相邻的 $\beta$ 参数域，再以原始 $J_1$ 三维地形和俯视图展示离散最低点的移动及 1% 近优谷底的宽度；
- 图 4 用五个等大三维面板定义 L1–L5 如何把同一 160 组合参数空间划分为 1、4、8、32 和 160 个分组；性能由正文表 2 单独报告；
- 图 5 将 Default 与 L1–L6 的 pooled 及分样本量风险放在同一视图，直接显示新增信息带来的风险下降，并将 L6 作为事后参照分隔；
- 图 6 同时展示 seed 42 在四个样本量下的总体误差、Default–L6 观测差距和样本级改善分布；训练随机性的检查只保留在附录中；
- 图 7 解释网络如何从预测风险曲线选择偏移量，并给出全样本选择对应关系和超额损失分布；
- 图 8 用真实 MDM 梯度轨迹、条件超额损失曲线和单元内相关解释同一参数条件下偏移量为何随样本改变；
- 图 9 用一张复合图概括未见参数、传统估计方法和可靠度寿命三类支撑验证；
- 7 张稿件引用的补充图统一了方法颜色、字号、线宽、图例和误差范围定义；原 E10 条件风险图转入附录，seed 稳定性由附录表 B2 报告，另保留一张可复核但不在稿件重复引用的稳定性图；
- 每张图均导出 PNG、SVG、PDF 和 600 dpi TIFF，SVG 文本保持可编辑；
- 数值和导出检查由 `scripts/qa_submission_figures.py` 自动完成，结果见 `provenance/submission_figure_qa.json`。

SCI 图像应当“信息丰富而不拥挤”。目前九张正文图依次承担固定偏移量基准、方法流程、参数域敏感性、信息空间定义、信息层级结果、核心效果、选择过程、MDM 内部机制和支撑验证，七张稿件引用的补充图保存可追问的分层细节。后续不再为装饰性丰富增加重复面板。

## 使用原则

1. 正式数据和计算后结果只从 `D:/weibull/Study/01-study-MDM最小偏移量优化研究/artifacts/formal/` 读取。
2. 不在本目录复制 48,000 个样本或 1,248,000 条损失的大文件。
3. 不直接修改正式封存图表；在这里重画并经人工确认后，稿件只引用这里的版本。
4. 图表数值不得手工录入；必须由 `figure_sources.json` 指向的数据派生。
5. 投稿图同时保留 PNG（预览）、SVG/PDF（排版）和 TIFF（投稿备用）。
6. 被替换的图及其派生数据移入 `archive/replaced/`，不直接删除；活动稿件只引用 `main/` 与 `supplementary/` 中的当前版本。

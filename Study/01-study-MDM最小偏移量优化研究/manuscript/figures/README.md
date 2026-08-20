# Study01 论文图表工作区

这个目录集中保存论文 Markdown 稿件实际引用的图像、表格、制图入口和数据来源说明。它是论文写作侧的工作区，不替代 `D:/weibull` 中已经封存的正式实验产物。

## 目录

| 目录 | 内容 |
|---|---|
| `main/` | 正文图 1–6 |
| `supplementary/` | 补充材料图 |
| `tables/` | 正文与补充材料表格的 Markdown/CSV 版本 |
| `scripts/` | 投稿图唯一绘制入口和自动质检程序 |
| `data/` | 数据不复制入本目录，只记录正式数据库和计算后数据的准确位置 |
| `provenance/` | 当前正式图表包的 manifest、哈希清单和原始说明快照 |
| `archive/` | 已被新版替换但暂不删除的旧图、旧源数据与版本快照 |

每张图的结论、来源和生成函数见 [`figure-index.md`](figure-index.md)，机器可读配置见 [`figure_sources.json`](figure_sources.json)。

## Markdown 引用

从同级的当前活动稿 `Study01论文初稿-v1.2.md` 引用正文图：

```markdown
![样本自适应偏移量选择流程](figures/main/fig1_method_structure.png)

![整体偏移量与联合估计误差](figures/main/fig2_overall_delta_risk.png)

![不同样本量下的联合估计误差](figures/main/fig3_per_n_J1.png)

![偏移量选择机制](figures/main/fig4_selector_mechanism.png)

![样本实现对MDM偏移量的影响](figures/main/fig5_decision_mechanism.png)

![支撑验证汇总](figures/main/fig6_support_validation.png)
```

补充材料图使用 `figures/supplementary/文件名.png`。表格可直接复制 `tables/*.md`，CSV 保留为数值核对源。

## 当前质量状态

当前活动稿使用 13 张图，另保留一张初始化稳定性复核图，均已按 SCI 投稿图标准完成重画：

- 图 1 分开训练与应用流程，消除了裁切、文字碰撞和职责混淆；
- 图 2 同时呈现全局风险曲线、低风险区放大和三类决策参照；
- 图 3 同时展示 seed 42 在四个样本量下的总体误差、Default–L6 观测差距和样本级改善分布；训练随机性的检查只保留在附录中；
- 图 4 解释网络如何从预测风险曲线选择偏移量，并给出全样本选择对应关系和超额损失分布；
- 图 5 用真实 MDM 梯度轨迹、条件超额损失曲线和单元内相关解释同一参数条件下偏移量为何随样本改变；
- 图 6 用一张复合图概括未见参数、传统估计方法和可靠度寿命三类支撑验证；
- 7 张稿件引用的补充图统一了方法颜色、字号、线宽、图例和误差范围定义；原 E10 条件风险图转入附录，seed 稳定性由附录表 B2 报告，另保留一张可复核但不在稿件重复引用的稳定性图；
- 每张图均导出 PNG、SVG、PDF 和 600 dpi TIFF，SVG 文本保持可编辑；
- 数值和导出检查由 `scripts/qa_submission_figures.py` 自动完成，结果见 `provenance/submission_figure_qa.json`。

SCI 图像应当“信息丰富而不拥挤”。目前六张正文图依次承担方法、统一规则、核心效果、选择过程、MDM 内部机制和支撑验证，七张稿件引用的补充图保存可追问的分层细节。后续不再为装饰性丰富增加重复面板。

## 使用原则

1. 正式数据和计算后结果只从 `D:/weibull/Study/01-study-MDM最小偏移量优化研究/artifacts/formal/` 读取。
2. 不在本目录复制 48,000 个样本或 1,248,000 条损失的大文件。
3. 不直接修改正式封存图表；在这里重画并经人工确认后，稿件只引用这里的版本。
4. 图表数值不得手工录入；必须由 `figure_sources.json` 指向的数据派生。
5. 投稿图同时保留 PNG（预览）、SVG/PDF（排版）和 TIFF（投稿备用）。
6. 被替换的图及其派生数据移入 `archive/replaced/`，不直接删除；活动稿件只引用 `main/` 与 `supplementary/` 中的当前版本。

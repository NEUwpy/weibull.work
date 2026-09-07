<!-- 当前图件入口：Word 与中文 Markdown 共用 figures/word/assembly-manifest.json 中的 PNG；原目录为历史来源。 -->
> **Word 图件（2026-09-07）**：[word/README.md](word/README.md)。正文与附录已使用该目录的 10 张重绘图，生成代码、PNG、可编辑 SVG 和装配清单一并保留。正文与附录 Markdown 已同步引用同一套 `word/` 图件；以下原目录说明保留为历史资产记录。

> Markdown 图1已根据用户反馈再次重画：神经元与全连接网络、P/Q/QCP监督路径、梯度回传及验证选点示意。对应生成器为 `structure-drawio/build_neural.py`；此前分类框版已归档。

> 图1已按用户要求改为draw.io可编辑结构图：中文 `structure-drawio/study02-framework-zh.drawio`，英文 `structure-drawio/study02-framework-en.drawio`，同目录PNG/SVG/PDF。正文Markdown已引用新图；下表旧fig1文件仅保留为此前输出，其余图不变。

# Study02 v2.7.0 图件

中文图件位于本目录，英文同源图位于 `../submission/figures/`。P统一灰色、Q蓝色、QCP绿色，配合不同标记；对比量的颜色与具体图例对应。全部10张图均提供PNG、PDF和保留文本的SVG。

| 图 | 任务 |
|---|---|
| 图1 `main/fig1_research_design` | 共用预测流程、分别训练与研究递进；早期P验证损失决定QCP阈值 |
| 图2 `main/fig2_parameter_compensation` | 等寿命点切片、真实验证平均约束、参数贡献与逐预测抵消 |
| 图3 `main/fig3_cross_life_performance` | 三点总体误差及配对区间，目标小效应局部放大 |
| 图4 `main/fig4_cell_heterogeneity` | 160真值单元效应与净收益集中性 |
| 图B1 `appendix/figB1_common_budget_results` | 补偿与选定轮次，避免重复主文精度面板 |
| 图B2 `appendix/figB2_sample_size_equivalence` | 样本量规律和经验等效观测数 |
| 图B3 `appendix/figB3_extended_reliability` | 较宽可靠度曲线及参数RMSE对数点图 |
| 图B4 `appendix/figB4_regional_gains` | 四个样本量的参数区域热图及前五净收益单元 |
| 图C1 `appendix/figC1_target_sensitivity_mechanism` | 早期300/20预算的静态敏感度代理检验 |
| 图D1 `appendix/figD1_error_distribution` | 早期300/20预算P/Q的误差方向与尾部 |

当前生成器为 `../tools/figures_v270.py`，英文标签由 `../tools/figure_english_v270.py` 统一转换。复用 `figures_v260.py` 的计算及布局函数和项目级 `paper_figures.py` 的历史数据计算，但保存至当前目录。来源与输出哈希、验证约束、贡献分位数和前五单元见 `../../artifacts/manuscript_figures_v270/`。

图像改动不修改预测数据。图2B使用验证集平均量，不能解读为每个预测满足参数误差上界；图2C的分位范围不是置信区间；图4/B4是事后收益定位，不是可部署的区域选择规则。C1/D1不能与600/60主结果混池。

v2.6.0当时的完整图件保存在 `../../归档/旧稿/v2.6.0/figures/`，不使用当前输出反查历史输出哈希。

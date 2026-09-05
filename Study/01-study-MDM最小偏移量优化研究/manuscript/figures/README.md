# Study01 论文图表

当前正文 v1.12 使用七张图，附录 v1.10 使用十张图；另有两张复核图。当前稿件图号与稳定资产文件名的对应以 [figure-index.md](figure-index.md) 和 `figure_sources.json` 为准。`main/` 与 `supplementary/` 是资产存储位置，不单独决定稿件归属。

当前图表已经过技术规范检查，但作者对改后视觉效果不满意；视觉修订和验收尚未完成。v1.10 只改正文论述，沿用当前图件，后续以原图为参照逐图处理。

## 当前图像

正文依次呈现方法数据流、固定偏移基准、参数域风险、空间分组、信息条件风险、主效果及样本轨迹机制。图 3 与图 4 按作者要求恢复原版三维表达；表 A2 保留分组定义，预测曲线与超额损失放入附录图 B1。机制图包含全范围与明确标记的局部区域；完整轨迹没有被局部窗口替代。

训练示意曲线仅说明流程；数值结论来自封存结果。各图均有 PNG、可编辑 SVG、PDF 和 600 dpi TIFF。图注直接对应当前稿件，详见 [captions-and-citations.md](captions-and-citations.md)。

## 生成与验证

`scripts/build_figures.py` 默认只读取既有证据并在论文侧重建图表，随后运行 `qa_submission_figures.py`。不要启用 `--regenerate-formal` 来处理文字或版面修订。源数据、估计结果和正式模型保持封存。

数值及导出检查结果见 `provenance/submission_figure_qa.json`，哈希及生成器记录见 `provenance/manifest.json`。自动检查不等于目标期刊整篇排版验收；最终 PDF 尚待期刊确定后制作。

## 历史

正文 v1.7、附录 v1.6 以及修订前图表和生成器已保存为完整快照：`archive/replaced/pre-v1.8-20260905/`。原稿文本也按原字节保存在 `../shelve/`。历史图不得作为当前稿件图号依据。

2026-09-05 通用字号整理：普通文字至少 8.6 pt，以导出文件原生尺寸阅读；数学上下标另行核查。表格使用可编辑文本，HTML 预览采用三线表。修订前完整快照见 `archive/replaced/pre-font-standardization-20260905/`。

v1.9 / 附录 v1.8 沿用本套字号规范化图像，全部图件字节未变；叙述修订检查见 `../revision-v1.9-qa.json`。

## 图 1：draw.io 重绘

正文 v1.10 的图 1 已改为 [draw.io 源文件](drawio/fig1_adaptive_selection/fig1_adaptive_selection.drawio)及其 [PNG](main/fig1_adaptive_selection_drawio.png)、[SVG](main/fig1_adaptive_selection_drawio.svg)、[PDF](main/fig1_adaptive_selection_drawio.pdf)导出。PDF 宽度为 180 mm。旧版方法图保留，原批量绘图脚本不会覆盖新的独立文件。正文其他图本轮未改。复核与来源见 `drawio/fig1_adaptive_selection/`。

## v1.11 注释清理

当前图 1 的可编辑源文件为 `drawio/fig1_adaptive_selection_v111/fig1_adaptive_selection.drawio`。图 1 及附图 D1、E2、F2、F3 删除重复备注；符号、阴影和误差线的含义集中写入图注。F3 横轴修正为每个样本量模型的训练样本数。旧版资产保留，当前映射见 `figure_sources.json`。图 2 沿用两面板合并版，其余数据图沿用原文件。

当前图 3、图 4 使用 `main/*restored_3d.*`，由 Git `95c797d7` 原样恢复；源程序保存在 `archive/replaced/pre-v1.8-20260905/figures/scripts/`，原文件与导出哈希已逐项核对。

v1.12 完善偏移量调节含义与条件偏差—方差解释；图 2 增加联合风险分解，图 7 对照同样本交点与候选损失，原逐参数 SD 分布移入附录 A.6。原版三维图、信息层级及主自适应比较保留；本轮复用现有数据，没有新增训练或独立确认实验。 新图生成入口：`scripts/plot_offset_revision_v112.py`。

图 7 最新版本按样本分列，上排位置估计、下排联合损失；分组及相关性证据为附录图 F4。当前图 7 生成器为 `scripts/plot_fig7_sample_columns.py`。

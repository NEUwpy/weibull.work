# Study01 论文图表

当前正文 v1.8 使用六张图，附录 v1.7 使用八张图；另有三张复核图。当前稿件图号与稳定资产文件名的对应以 [figure-index.md](figure-index.md) 和 `figure_sources.json` 为准。`main/` 与 `supplementary/` 是资产存储位置，不单独决定稿件归属。

## 当前图像

正文依次呈现方法数据流、固定偏移基准、参数域风险、信息条件、主效果及样本轨迹机制。旧空间分组图改为可编辑表 A2；预测曲线与超额损失放入附录图 B1。参数域图按约 18 cm 宽度绘制，不再缩放大尺寸三维画布。机制图包含全范围与明确标记的局部区域；完整轨迹没有被局部窗口替代。

训练示意曲线仅说明流程；数值结论来自封存结果。各图均有 PNG、可编辑 SVG、PDF 和 600 dpi TIFF。图注直接对应当前稿件，详见 [captions-and-citations.md](captions-and-citations.md)。

## 生成与验证

`scripts/build_figures.py` 默认只读取既有证据并在论文侧重建图表，随后运行 `qa_submission_figures.py`。不要启用 `--regenerate-formal` 来处理文字或版面修订。源数据、估计结果和正式模型保持封存。

数值及导出检查结果见 `provenance/submission_figure_qa.json`，哈希及生成器记录见 `provenance/manifest.json`。自动检查不等于目标期刊整篇排版验收；最终 PDF 尚待期刊确定后制作。

## 历史

正文 v1.7、附录 v1.6 以及修订前图表和生成器已保存为完整快照：`archive/replaced/pre-v1.8-20260905/`。原稿文本也按原字节保存在 `../shelve/`。历史图不得作为当前稿件图号依据。

2026-09-05 通用字号整理：普通文字至少 8.6 pt，以导出文件原生尺寸阅读；数学上下标另行核查。表格使用可编辑文本，HTML 预览采用三线表。修订前完整快照见 `archive/replaced/pre-font-standardization-20260905/`。

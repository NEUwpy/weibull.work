# 制图程序

`build_figures.py` 是论文侧统一入口：

- 默认先同步正式表格和 provenance，再运行投稿版制图程序及 fail-closed QA；
- 正文和补充图由 `make_submission_figures.py` 生成，正式实验目录中的旧 PNG 不会覆盖投稿图；
- 使用 `--regenerate-formal` 时，才先调用仓库内正式证据生成程序；
- `qa_submission_figures.py` 核对 44 个导出文件、矢量文本、图像尺寸和核心数值，并验证图 3 的逐样本配对分布及附录 B3 的三参数误差分解。

```powershell
python .\figures\scripts\build_figures.py
python .\figures\scripts\build_figures.py --regenerate-formal
```

正式封存图表的历史生成实现：

`D:/weibull/Study/01-study-MDM最小偏移量优化研究/code/generate_paper_figures.py`

依赖：`paper_support.py`、`dim_raw_config.py`。准确路径和复制清单由上级目录的 `figure_sources.json` 管理。

当前投稿图的唯一绘制入口是本目录的 `make_submission_figures.py`；它只读取正式封存数据并在论文侧生成 6 张正文图和 5 张补充图。投稿图全部使用 Python/matplotlib 生成，导出 PNG、SVG、PDF 和 TIFF。正式封存数据保持只读；不要直接修改正式目录中的 PNG。被替换的旧图保存在 `../archive/replaced/`，不直接删除。

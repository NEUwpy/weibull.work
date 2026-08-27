# 制图程序

`build_figures.py` 是论文侧统一入口：

- 默认直接从 `figure_sources.json` 声明的封存数据派生表格和图，再运行 fail-closed QA；
- 正文和补充图由 `make_submission_figures.py` 生成，正式实验目录中的旧 PNG 不会覆盖投稿图；
- 使用 `--regenerate-formal` 时，才先调用仓库内正式证据生成程序；
- `qa_submission_figures.py` 核对 56 个导出文件、矢量文本、图像尺寸和核心数值，并验证图 1 的组合内稳定性分布、图 3 的逐样本配对分布、正文表 4 与附录 B3 的逐参数误差。

```powershell
python .\figures\scripts\build_figures.py
python .\figures\scripts\build_figures.py --regenerate-formal
```

正式主结果的紧凑派生入口为 `code/prepare_mean_normalized_main_evidence.py`。准确路径和数据源由上级目录的 `figure_sources.json` 管理。

当前投稿图的唯一绘制入口是本目录的 `make_submission_figures.py`；它只读取正式封存数据并在论文侧生成 6 张正文图和 5 张补充图。投稿图全部使用 Python/matplotlib 生成，导出 PNG、SVG、PDF 和 TIFF。正式封存数据保持只读；不要直接修改正式目录中的 PNG。被替换的旧图保存在 `../archive/replaced/`，不直接删除。

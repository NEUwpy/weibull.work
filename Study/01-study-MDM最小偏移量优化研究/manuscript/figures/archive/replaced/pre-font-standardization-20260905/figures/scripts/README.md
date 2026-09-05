# 制图程序

统一入口为 `build_figures.py`，默认仅从封存证据派生论文图表并执行自动质检。`--regenerate-formal` 会重建正式证据，不属于稿件修订步骤。

`make_submission_figures.py` 生成 17 个稳定图像资产；其中正文 v1.8 使用六张、附录 v1.7 使用九张，另外两张只供复核。函数名与文件名前缀沿用旧编号，稿件编号映射由 `../figure_sources.json` 指定。

- `plot_fig3_beta_domain_sensitivity.py`：二维实际格点风险与离散最低点/近优范围。
- `plot_fig4_information_spaces.py`：附录 A1 的紧凑分组定义，同时保留 160 单元分组基数核对。
- `plot_fig5_information_level_results.py`：当前正文图 4 的信息条件风险。
- `qa_submission_figures.py`：检查 68 个导出文件、可编辑 SVG、尺寸及核心数值。自动数值检查使用稳定资产名，不能替代逐张视觉检查。

```powershell
python .uild_figures.py
```

正式实验目录保持只读。修订前生成器和图表保存在 `../archive/replaced/pre-v1.8-20260905/`。

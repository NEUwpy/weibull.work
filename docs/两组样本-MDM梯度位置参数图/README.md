# MDM 梯度-位置参数图

本目录使用 `docs/两组样本-画图.docx` 中的实际表格数据，调用项目当前
`python/methods/mdm.py` 生成 MDM 参数估计过程中的梯度-位置参数曲线。

## 数据核对

- 附件前两张表：样本量 `n=7`，共 30 组。
- 附件后两张表：样本量 `n=15`，共 30 组。
- 因此附件中的第二批不是 `n=30`；本目录按 Word 表格的真实结构标为 `n=15`。

## 画法

- 参考文献 182-046 的图 5：每个样本量叠加 30 条黑色曲线。
- 横轴：位置参数。
- 纵轴：尺度参数估计值标准差梯度。
- 红色点划线：偏移判据 `delta=0.1`。
- 显示范围：横轴 `0-1800`，纵轴按本次要求调整为 `-0.8-1.6`。
- 曲线来自当前 MDM 实现的 `profile_gradient`，不是手绘或平滑模拟曲线。

## 文件

- `mdm_gradient_gamma_n7.*`：`n=7` 的 30 曲线叠加图。
- `mdm_gradient_gamma_n15.*`：`n=15` 的 30 曲线叠加图。
- `mdm_gradient_gamma_comparison.*`：两种样本量的并排比较图。
- `input_samples.csv`：从 Word 提取的长表样本数据。
- `mdm_gradient_curves.csv`：完整梯度曲线源数据。
- `mdm_parameter_estimates.csv`：`delta=0.1` 下的 60 组参数估计摘要。

每张图均导出 PNG、SVG 和 PDF。复现命令：

```powershell
python .\docs\两组样本-MDM梯度位置参数图\plot_mdm_gradient_gamma.py
```

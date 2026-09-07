# Study02 Word 图件

2026-09-07 标注更正：所有原有字母子图编号统一为 `(a)`、`(b)` 等，标题组放在子图上方居中；公共实现为仓库 `scripts/documents/panel_labels.py`。

2026-09-07：正文 4 图、附录 6 图已按 Word 阅读尺寸重绘并嵌入手稿。

- `main/`：正文图，PNG 与可编辑 SVG 同名配对。
- `appendix/`：附录 B1、B2、B3、B4、C1、D1 图。
- `derived/`：原绘图模块产生的中间输出，不用于直接插入 Word。
- `assembly-manifest.json`：文档图序、原图身份、尺寸和输出文件 SHA-256。
- 生成代码：[render_word_figures.py](../../tools/render_word_figures.py)，调用同目录 `figures_v260.py`、`figures_v270.py` 及已有研究数据。

插入宽度为 17.49 cm；普通文字五号（10.5 pt），中文宋体、英文及数字 Times New Roman，正体、不加粗。公式上下标保留正常比例缩小。PNG 为 600 dpi；SVG 保留文本与矢量对象。图 1 保留网络、P/Q/QCP 路径、反馈与验证选点示意；图 2 保留参数补偿、约束与抵消分析。

从仓库根目录执行（Python 需安装 numpy、pandas、scipy、matplotlib、Pillow、lxml）：

```powershell
python "Study/02-study-NN参数估计与分位点目标研究/manuscript/tools/render_word_figures.py"
```

只读取已有结果重绘，不启动模型训练。更新 Word 前先备份，然后运行：

```powershell
python scripts/documents/assemble_manuscript_figures.py "Study/02-study-NN参数估计与分位点目标研究/manuscript/figures/word/assembly-manifest.json" "Study/02-study-NN参数估计与分位点目标研究/manuscript"
```

装配脚本保留正文、原生公式及引用字段，并设置图片居中及图题同页。随后应检查 Word 分页。此次修改前的 Word 已保存在 `../../backup/20260906-143123/`。


2026-09-07：Study02 图 1 恢复作者原先的神经网络与三路监督结构图；PNG/SVG、Word、Markdown 所引资产及汇报更新版同步恢复，生成器改为保留原图。

# Study01 Word 图件

图4现为上排 L1–L3、下排 L4–L5 的“上三下二”布局，下排居中；图中不含额外解释性注释。

2026-09-07 图1更正：按作者反馈保留原图结构和原插入尺寸（宽 15.24 cm）；后续仅将两段子图标题编号改为 `(a)`、`(b)` 并居中，框线和箭头未重排。生成器使用 `preserve_framework()` 处理该图。其余 16 图沿用下面的 Word 字号规范。

2026-09-07 标注更正：图4删除右下角解释性注释。所有原有字母子图编号统一为 `(a)`、`(b)` 等，标题组放在子图上方居中；公共实现为仓库 `scripts/documents/panel_labels.py`。

2026-09-07：正文 7 图、附录 10 图已按 Word 阅读尺寸重绘并嵌入手稿。正文第三、第四图保留三维表达。

- `main/`：正文图，PNG 与可编辑 SVG 同名配对。
- `supplementary/`：附录图，按 `assembly-manifest.json` 对应文档与图序；文件名沿用原资产身份。
- `derived/`：生成过程使用的派生数据与中间输出，不用于直接插入 Word。
- `assembly-manifest.json`：文档图序、原图身份、尺寸和输出文件 SHA-256。
- `figure-report.json`：字体和图像尺寸记录。
- 生成代码：[render_word_figures.py](../scripts/render_word_figures.py)，调用同目录原绘图模块及项目已有结果数据。

插入宽度为 17.49 cm；普通文字五号（10.5 pt），中文宋体、英文及数字 Times New Roman，正体、不加粗。公式上下标保留正常比例缩小。PNG 为 600 dpi；SVG 保留文本与矢量对象。请勿在 Word 中额外缩小图片，否则字号会一起缩小。

从仓库根目录执行（Python 需安装 numpy、pandas、scipy、scikit-learn、matplotlib、Pillow、lxml）：

```powershell
python "Study/01-study-MDM最小偏移量优化研究/manuscript/figures/scripts/render_word_figures.py"
```

只重绘已有研究结果，不启动模型训练。部分图从固定种子重建样本以计算原有绘图统计量。更新 Word 前先备份，然后运行：

```powershell
python scripts/documents/assemble_manuscript_figures.py "Study/01-study-MDM最小偏移量优化研究/manuscript/figures/word/assembly-manifest.json" "Study/01-study-MDM最小偏移量优化研究/manuscript"
```

装配脚本保留正文、原生公式及引用字段，并设置图片居中及图题同页。随后应检查 Word 分页。此次修改前的 Word 已保存在 `../../backup/20260906-143123/`。

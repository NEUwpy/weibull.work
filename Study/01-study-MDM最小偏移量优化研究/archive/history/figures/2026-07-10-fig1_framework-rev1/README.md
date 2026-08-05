# fig1_framework rev1 归档说明

- **归档日期**：2026-07-10
- **来源**：以 `main@ccacd35` 为基线的活动 Figure 2，进入无结果数字路线图重构前归档
- **旧版内容**：左侧 L1-L6 层级框包含 J₁ 与改善百分比；L3-L5 标注“requires NN”；L6 标注“upper bound”；右侧混合实验映射与内部研究状态。
- **替换原因**：实验设计章不应提前泄漏 Ch4-Ch5 结果；L3-L5 和 L6 标签与已确认的证据边界冲突；新图只保留最终论文逻辑。

## 文件校验

| 文件 | SHA-256 |
|------|---------|
| `fig1_framework.png` | `DDF87BA5D25137989B6D5C7196550F96A00AA406D91B0E39F3153854AFDD78EF` |
| `fig1_framework.svg` | `276DE18BE193C5326ECF1F365A1CF03671D1C59CDAADDE31239D1884829805FA` |
| `fig1_framework.pdf` | `21BFF562B7A4509573798DB7186A54AC7C1DD9119429C9C392236B5A1F663357` |
| `plot_fig1-rev1.py` | `CE3FAAFC5E2524087D9F491335BC1A17E16DB52B8C28D88714C1D68F5719CC8D` |

## 恢复方法

如需恢复 rev1，将三个图文件复制回 `artifacts/formal/figures/`，并将归档脚本复制回 `code/plot_fig1.py`。恢复后必须同步回滚 Ch3 图注和论文骨架，禁止旧图与新合同混用。

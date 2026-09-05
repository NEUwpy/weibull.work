# Study02 manuscript v2.7.0

本目录保存当前中英文工作稿、可编辑图源及投稿准备材料。600条补充训练已完成并写入正文3.5和附录F，验证结果见[修订记录](../docs/v2.7.0-投稿修订与验证.md)。

| 入口 | 内容 |
|---|---|
| [中文正文](Study02论文初稿-v2.7.0.md) | 任务对齐的收益、参数代价、约束修复及简单参照 |
| [中文附录](Study02论文附录-v2.7.0.md) | 完整结果、推导、历史预算、QP及补充对照 |
| [英文投稿工作包](submission/README.md) | 英文正文/附录、英文图、Highlights、Title page、Cover letter |
| [图件说明](figures/README.md) | 4张主图、6张附图，中英文同源生成 |
| [引用与完整性审计](引用与完整性审计.md) | 当前证据核验 |
| [本地复现包](../reproducibility/README.md) | 脚本、证据、环境和文件校验 |
| `tools/figures_v270.py` | 当前全部图件生成器，复用v260计算函数；不训练 |
| `tools/qp_comparison_v270.py` | 固定加权QP的三寿命点配对复算 |
| `tools/audit_zero_orphan.py` | 中英文正文引用双向检查 |
| [图1可编辑源文件](figures/structure-drawio/study02-framework-zh.drawio) | academic-figures-drawer重绘的研究框架图 |

当前正文与附录只保留v2.7.0。完整v2.6.0快照及33文件校验位于[归档](../归档/旧稿/v2.6.0)，其他旧稿与过程记录仍按原位置保留。v260脚本是当前生成器依赖的计算函数，不代表当前图件版本。

当前英文稿采用通用研究论文形式。期刊格式、作者资料与声明尚待真实信息；尚未投稿或上传公开资料库。历史核验书目和修订过程见[归档目录](../归档/过程记录/论文修订/README.md)。

图1当前采用draw.io版本，说明见[重绘说明](figures/structure-drawio/brief.md)。文档以Markdown交付，旧HTML为历史派生文件，不作为当前入口。

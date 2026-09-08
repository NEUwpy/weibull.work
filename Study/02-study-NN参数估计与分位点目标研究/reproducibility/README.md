# Study02 当前复算与恢复

设计、配置与脚本的唯一说明是[实验配置](../02-实验配置.md)，当前最小证据范围见[证据索引](../01-证据索引.md)。原v2.7.0 ZIP是当时的本地包，尚未公开；它不包含本轮全部新文档，不再称作当前交付包。ZIP在本worktree是134字节LFS指针，D盘主目录有377,564,001字节实体，已额外保存到Study02专属外部快照。

## 当前检查

从本项目根目录运行：

```powershell
python manuscript/tools/audit_current_evidence.py
```

检查四份稿件的表格/引用、当前图像与数据清单、600补充轨迹及200个Q复现身份、QP/主结果一致性、所有本轮改动Markdown的链接与锚点。报告输出到`snapshots/2026-09-08/validation.json`。历史`audit_revision_v270.py`和`s5b_revision --phase verify`保留原职责：前者还验证旧稿和全量权重，后者访问已退役continuous分支；不把历史包检查冒充当前最小证据检查。

## 环境和无训练复算

原锁定依赖见[requirements.txt](../requirements.txt)和[环境记录](environment.json)；绘图另需matplotlib、Pillow和CJK字体，检查需pytest。安装环境与数据本身是不同的复现条件。

从`code`目录执行（会写派生统计，建议在另一个干净副本操作）：

```powershell
$env:PQ_PROTOCOL='iid-v1'
python -m study02pq.qcp_main_analysis
python -m study02pq.qcp_cross_quantile_recovery
python -m study02pq.submission_controls_analysis
```

以上模块只消费保留的预测和元数据，不训练。协议25区间复算包含200,000次重采样，不能为了清理而重复正式训练。中文图入口为[render_word_figures.py](../manuscript/tools/render_word_figures.py)，英文图见[图表索引](../manuscript/figures/README.md)。旧主模型没有保存权重；可复算预测统计，但重新获得主模型需按原配置重训。协议25保存过600份权重；清理拟移除这些可从Git恢复的文件，实际状态以快照动作记录为准，现已移到外部待删除目录；现有fit元数据会使resume跳过已完成工作。

## 恢复而不回退整个项目

[研究快照](../07-认识清单与研究快照-20260908.md)记录Git标签、外部ZIP哈希、原位置、去留理由与实际操作。tracked文件从`snapshot/study02-before-lean-20260908`按确切路径恢复；大ZIP实体及非Git文件从`D:\weibull-backups\study02-20260908\non-git-and-lfs.zip`按`main/`、`external/`前缀恢复。先提取到独立目录核验哈希，再按需恢复个别文件。

QP/QCP相似精度、同数据补充及固定尺度边界保留。打包和哈希一致只证明材料对应，不是新数据确认或公开发布。本轮不重建大ZIP、不推送、不对外上传。

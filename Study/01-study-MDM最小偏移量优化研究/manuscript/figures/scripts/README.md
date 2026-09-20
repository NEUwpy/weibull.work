# 图件程序入口

当前资产、章节和缺项见[新稿图表索引](../figure-index.md)。本目录程序沿用历史输出名，不把文件前缀当作新稿图号。

- `make_submission_figures.py`：基础旧结果图，完整执行可能重新生成已退役版本。
- `plot_offset_revision_v112.py`：固定偏移风险分解及相关附图。
- `plot_fig7_sample_columns.py`：现有样本轨迹与损失图，尚无实际AMDM选点。
- `plot_fig5_information_level_results.py`：信息条件比较。
- `clean_annotations_v111.py`：旧图注释与标注修订。
- `render_word_figures.py`：旧17图排版，不代表新稿装配。

其余程序保留为来源或依赖；`qa_typography.py`属于旧排版审计。`figure_sources.json`的旧字段仍供这些程序读取，新稿映射在 `current_manuscript` 和Markdown索引。重跑前核对输入与输出，优先独立输出目录，避免把旧图重新堆回活动目录。历史图已从磁盘清理；历史数据、程序和当前必要可编辑源保留。

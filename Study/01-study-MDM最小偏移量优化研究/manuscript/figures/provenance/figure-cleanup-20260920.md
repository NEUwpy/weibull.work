# Study01 图件清理记录

日期：2026-09-20
清理前 Git HEAD：`4e3dc94d5ab57c68760ac245d4023dd900f086c6`

本次只清理与新稿 v2.0 当前图位无直接用途的旧媒体文件；实验数据、绘图程序、可编辑源、图表数据和来源记录未删除。删除前逐文件核对工作区字节与 HEAD 对应对象一致。

| 范围 | 文件数 | 体积 |
|---|---:|---:|
| `archive/` | 264 | 44.15 MiB |
| `drawio/` | 8 | 2.07 MiB |
| `main/` | 35 | 12.62 MiB |
| `supplementary/` | 20 | 4.62 MiB |

删除范围：
- `archive/` 中已替换旧图、复核图和旧导出媒体；文字、脚本、数据与清理记录保留。
- `main/`、`supplementary/` 中未被当前图表索引或新稿规划引用的旧导出版本。
- `drawio/fig1_adaptive_selection/` 中旧版本导出媒体；`v111` 可编辑源和当前导出保留。

恢复：
- 单文件可从 `4e3dc94d5ab57c68760ac245d4023dd900f086c6` 用 `git restore --source=4e3dc94d5ab57c68760ac245d4023dd900f086c6 -- <路径>` 恢复。
- 本记录对应的删除清单和 SHA256 保存在当前任务的临时核验文件中；Git 对已跟踪文件提供正式恢复路径。

当前图件入口：[`figure-index.md`](../figure-index.md)。

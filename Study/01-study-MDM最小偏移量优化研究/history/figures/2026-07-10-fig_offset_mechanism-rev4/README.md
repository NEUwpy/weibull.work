# fig_offset_mechanism rev4 归档说明

- **归档日期**：2026-07-10
- **来源**：`main@ccacd35`
- **活动图路径**：`artifacts/formal/figures/fig_offset_mechanism.{png,svg,pdf}`
- **旧版内容**：Panel A 为真实 MDM trace；Panel B/C 分别使用 `gamma_hat` 与归一化误差的重叠直方图。
- **替换原因**：Panel B/C 在固定尺度下信息重复，且 `delta=0` 的边界密度尖峰压缩主体分布；rev5 改用 ECDF 与严格配对误差散点。

## 文件校验

| 文件 | SHA-256 |
|------|---------|
| `fig_offset_mechanism.png` | `4CED1B07026A1CA34934997EE70E9C231EE7CDBB558134C90BD965C8265B2294` |
| `fig_offset_mechanism.svg` | `AFD0F8088D87AEA44231179A4D9798AE95EF51EC5473C4D9C7CB3BFA8A2B70BC` |
| `fig_offset_mechanism.pdf` | `1DB6F32BB5FD73311C50EBAF903389648CBB1539AEC98D866DCC159359F66A9A` |

## 恢复方法

如需临时恢复查看，将本目录中的三个同名文件复制回 `artifacts/formal/figures/`。恢复后必须同时复核 Ch2 正文、Figure 1 图注和 `code/_fig1_sample_provenance.md`，避免旧图与 rev5 文字混用。

旧版绘图脚本可从来源提交 `ccacd35` 的 `code/plot_fig_diagnostics.py` 追溯；本目录不复制脚本，避免形成第二活动代码源。

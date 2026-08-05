# fig_offset_mechanism rev5 归档说明

- **归档日期**：2026-07-10
- **来源**：以 `main@ccacd35` 为基线的当前工作树，进入 rev6 对称选样修改前归档
- **活动图路径**：`artifacts/formal/figures/fig_offset_mechanism.{png,svg,pdf}`
- **rev5 内容**：Panel B 已改为 `gamma_hat` ECDF，Panel C 已改为严格配对误差散点；Panel A 仍使用 near-neutral、largest-improvement、mild-worsening 三种不对称选择规则。
- **替换原因**：largest-improvement 是结果导向的极端样本，存在选择偏倚观感；rev6 改为近中性、改善组中位和变差组中位的对称代表规则。

## 文件校验

| 文件 | SHA-256 |
|------|---------|
| `fig_offset_mechanism.png` | `EC1E1E3531E84E1CC04746AB97B58FA2AFBDA932C0A582BC5D0109B0447F5233` |
| `fig_offset_mechanism.svg` | `BE4A932B4DAFC26BA386A0142D93E0DFC714DE0C8ED66F5AE7ED4C52E6AE9F10` |
| `fig_offset_mechanism.pdf` | `CB0492BD023E437099770EA7D0372BAEBAFB09C4D5F55567770D190211470C39` |
| `plot_fig_diagnostics-rev5.py` | `015F5849DAF34CD44394B0C5932B424549BBFEC09C9EB374414D989FC9CDB486` |
| `_fig1_sample_provenance-rev5.md` | `023FA1A3EC8E13576AFF579DC39BC023A177C28536FDDFF28A5FA0206438DEC0` |

## 恢复方法

如需恢复 rev5，将三个图文件复制回 `artifacts/formal/figures/`，将归档脚本复制回 `code/plot_fig_diagnostics.py`，并用归档溯源记录复核正文图注。恢复行为只能用于追溯或显式回滚，不得让 rev5 与 rev6 文字混用。

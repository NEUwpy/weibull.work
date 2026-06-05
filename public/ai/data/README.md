# AI 训练数据目录

> **⚠ S4.9 历史数据标识**：本目录中的数据文件主要生成于 S4.9 默认 MDM 改造之前，使用的是旧版 MDM 实现（两段均匀网格 + `no_intersection` 失败机制）。

## 数据说明

### MDM 相关数据

以下文件中的 MDM 结果基于 S4.9 前的旧版 MDM 实现：

- `route2_convergence.csv` — 包含 669 处 `mdm_failed`，是旧版 MDM 的 `no_intersection` 失败
- `mdm_baseline_comparison.json` — 旧版 MDM 成功率 80-84%
- `m1_vs_m3_best.json` — 旧版 MDM 对比数据
- `direct_estimation_mdm_baseline.json` — 旧版 MDM baseline 数据

### S4.9 后的变化

S4.9 已完成默认 MDM 重写：
- 使用几何加密网格替代两段均匀网格
- 使用约束边界规则替代 `no_intersection` 失败
- 详细说明见 `docs/S4.9_MDM默认实现与可视化一致性改造进程控制.md`

### 后续计划

这些数据目前保留作为历史参考。如需用于 S4/S2R/S3 实验，建议：
1. 使用 S4.9 后的默认 MDM 重新生成
2. 或在使用时明确标注为"历史旧口径数据"

---

*最后更新：2026-06-05*

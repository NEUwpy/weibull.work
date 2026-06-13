# AI 训练数据目录

> **历史数据标识**：本目录中的数据文件主要生成于当前 full-v1 baseline 之前，部分 MDM 对比数据来自 S4.9 默认 MDM 改造之前的旧版 MDM 实现（两段均匀网格 + `no_intersection` 失败机制）。
> 当前 AI 重构路线见 `docs/AI辅助三参数威布尔参数估计重构当前路线图.md`。本目录数据尚未接入 full-v1、`python/studies/common/` 统一流水线和 Bias/SD/RMSE/MAE 默认主口径，不能直接作为当前正式研究结论。

## 数据说明

### MDM 相关数据

以下文件中的 MDM 结果基于 S4.9 前的旧版 MDM 实现：

- `route2_convergence.csv` — 包含 669 处 `mdm_failed`，是旧版 MDM 的 `no_intersection` 失败
- `mdm_baseline_comparison.json` — 旧版 MDM 成功率 80-84%
- `m1_vs_m3_best.json` — 旧版 MDM 对比数据
- `direct_estimation_mdm_baseline.json` — 旧版 MDM baseline 数据

### 当前统一底座后的变化

- 默认 MDM 已固定为 `python/methods/mdm.py`，工程约束 `gamma >= 0`。
- `python/studies/common/` 已成为统一样本生成、方法调用、指标聚合和实验输出入口。
- full-v1 baseline 位于 `python/output/truth_sampling/full/`，阶段说明见 `docs/MDM真值抽样估计full-v1阶段总结.md`。
- 当前默认主指标为 Bias、SD、RMSE、MAE；S2R/MdAPE/P95 等保留为 diagnostics。

### 后续计划

这些数据目前保留作为历史参考。如需用于当前 AI 模块建设，建议：
1. 使用 `python/studies/common/` 统一流水线重新生成或重新评估。
2. 使用与 full-v1 一致的 seed namespace、参数网格和质量控制口径。
3. 将生成产物保存为 `results.csv / summary.json / manifest.json`，再设计到 `public/ai/data/` 的发布转换。
4. 在页面和报告中明确标注数据版本，避免旧口径数据和当前正式结论混用。

---

*最后更新：2026-06-13*

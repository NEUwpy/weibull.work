# 结果分析开发说明

> 建设目的与准则见[结果分析](../建设规范/02-参数估计方法/04-结果分析.md)。

[现行工作簿](#现行工作簿入口) · [旧分片数据与接口](#旧分片数据) · [旧适用范围页面](../history/旧适用范围页面.md)

## 现行工作簿入口

方法页入口为 `/methods/{methodId}/analysis`。旧 `/methods/{methodId}/applicability` 地址保留查询参数并转到「预计算结果」。`MethodResultAnalysis` 选择来源，所有来源和计算过程的归档选择器共用 `WorkbookResults`。

- 预计算结果由 `MonteCarloWorkbookViewer` 从工作簿目录和读取接口取得，工作表选择随 URL 保存。有效记录与统计口径见[结果分析规范](../建设规范/02-参数估计方法/04-结果分析.md#工作簿与统计)。
- 现场计算由 `AnalysisSampleCard` 接入[共享计算卡片](../../src/components/calculator/README.md#批次和归档)，MDM 沿用卡片的固定或 AI 偏移量。接到已有批次后，首次估计时优先完成待估计的组。
- 现场工作簿以实际进入估计的样本为数据源，使用共享有效性检查和指标函数，支持下载当前工作表 CSV。

预计算批次按 [Research00 工作簿登记](../data/README.md#research00-工作簿登记2026-11-02)读取。导出通过登记的批次 ID 定位原件，与当前显示的方法、样本量及工作表选择独立。

## 旧分片数据

方法对比仍读取[旧研究分片](../data/README.md#旧研究分片)。旧适用范围页面的布局和交互见[历史记录](../history/旧适用范围页面.md)。

# 共享计算卡片

[AnalysisCard](AnalysisCard.tsx) 负责卡片界面、当前组和整批结果表的展示。界面要求见[计算器建设规范](../../../docs/建设规范/01-威布尔计算器.md#计算卡片的输入与输出)。

## 接入和状态

| 调用方 | 持有的业务状态 |
|--------|--------------|
| [首页计算器](../../app/page.tsx) | 卡片列表、各卡片的方法、抽样设置、样本、估计及请求状态 |
| [方法页](../methods/MethodPage.tsx) | 当前方法的样本、同次计算记录及归档读取 |
| [现场结果分析](../methods/shared/studies/AnalysisSampleCard.tsx) | 抽样批次及估计，按共同抽样参数生成现场工作簿 |
| [MDM 过程量优化](../../app/ai/process-optimization/mdm/page.tsx) | 同一批样本的偏移量预测、估计和固定偏移量对照 |

调用方通过 props 和回调连接业务状态。卡片管理计算方向和切组交互，优先使用调用方传入的抽样参数。需要与计算过程或工作簿联动时，通过 `activeDataSourceIndex` 和 `onActiveDataSourceChange` 控制当前组。批量生成通过 `onDataSourcesChange` 交回样本。`generatedFrom` 保留样本实际生成条件。空样本保留抽样样本量设置。

## 批次和归档

- 默认参数和单组抽样在 [calculator-state.ts](../../lib/calculator-state.ts)。多组生成、继承、逐组估计和工作簿导入共用 [calculator-batch.ts](../../lib/calculator-batch.ts)。每组的原始观测、估计、失败信息和同次过程记录按 [DataSource](../../lib/weibull.ts) 对应。继承样本另建组标识并等待重新估计，保留观测和生成来源。
- 导入工作簿时按原重复编号关联样本与估计，`archive` 保存工作簿 ID、样本量、偏移量和重复编号。复算生成新的运行结果。冻结数据和历史计算记录的维护见[外部运行数据](../../../docs/data/README.md#计算记录)。
- 多组跳转到计算过程通过 `sampleBatch` 传递批次 ID。结果分析仅在各组样本有共同抽样参数、样本量一致且均为完整失效观测时转交整批，使用 `analysisBatch`。交接保留当前组和相应设置。接收方切换方法时可沿用原观测，原方法的估计、归档和过程记录随之失效。
- 会话内优先复用内存里的完整结果。刷新时从 `sessionStorage` 恢复原样本和来源。现场分析交接还保留轻量估计与失败信息。恢复计算过程时，MDM 归档按原身份读取，缺少过程记录的 3P 非归档批次可用原观测补算。

## 失效与验证

调用方用请求身份判断结果是否仍对应当前样本、方法与设定。逐组估计在请求前后检查身份，一组失败仍保留样本和诊断并继续下一组。[卡片播放](useCardSequence.ts)读取已完成组数，计算由调用方执行。

从项目根运行定向测试，覆盖参数切换、批次身份、迟到响应、交接恢复和归档导入。

```powershell
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --experimental-strip-types --test scripts/tests/calculator-state.test.mjs scripts/tests/calculator-batch.test.mjs scripts/tests/analysis-flow.test.mjs
```

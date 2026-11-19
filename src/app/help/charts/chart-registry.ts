/**
 * 图表使用注册表
 *
 * 记录图表在现行功能中的使用位置。
 * 公开数据可预览，运行时 API 和固定示例记录来源。
 *
 * 展示范式、表格范式和视觉语义定义见 charts-spec.ts；
 * 本文件只维护真实实例、数据源和实例级 props。
 */

export type DataSource =
  | { type: 'csv'; path: string }
  | { type: 'json'; path: string }
  | { type: 'api'; endpoint: string }
  | { type: 'example'; path: string }

export interface ChartUsage {
  id: string
  label: string
  location: string
  description: string
  dataSource: DataSource
  props: Record<string, unknown>
}

export type ChartRegistry = Record<string, ChartUsage[]>

const mmleExample = { type: 'example', path: 'src/data/method-process-examples/mmle.json' } as const

export const chartRegistry: ChartRegistry = {

  // ============================================================
  // ScatterPlot
  // ============================================================
  ScatterPlot: [
    ...['mle', 'wmle', 'mmle'].map(method => ({
      id: `${method}-scale-calculation`, label: `${method.toUpperCase()} 逐样本尺度计算`,
      location: 'PowerScaleCalculation / shared ProcessChart',
      description: '逐样本距离的幂次贡献、汇总量及尺度代入；数值过大或过小时使用等价归一化式。',
      dataSource: method === 'mmle' ? mmleExample : { type: 'api' as const, endpoint: 'POST /calculate' },
      props: { methodId: method, source: 'calculation.details.scale_calculation', exampleOnly: method === 'mmle' },
    })),
  ],

  // ============================================================
  // Histogram
  // ============================================================
  Histogram: [
    ...['β', 'η', 'γ'].map((symbol, index) => ({
      id: `workbook-error-${index}`,
      label: `结果分析 ${symbol} 估计差值分布`,
      location: 'WorkbookResults',
      description: '按当前批次、样本量与方法设置显示估计值减真值。归档取完整估计，现场取有效估计。',
      dataSource: { type: 'api' as const, endpoint: '/api/monte-carlo/{id} / POST /calculate' },
      props: { xLabel: `${symbol}̂ − ${symbol}`, yLabel: '频数', color: '#b58a45', axisFontSize: 14 },
    })),
    {
      id: 'm3-performance-beta',
      label: 'M3 β 误差分布',
      location: 'PerformanceTab',
      description: '直接估计 β 误差频率分布',
      dataSource: { type: 'json', path: '/ai/data/direct_estimation_a1_preprocessed.json' },
      props: { xLabel: 'β 误差', yLabel: '频数', color: '#10b981' },
    },
  ],

  // ============================================================
  // LineChart (AIChartLine)
  // ============================================================
  LineChart: [
    ...['mle', 'wmle', 'lse', 'lre', 'mm', 'mmle'].map(method => ({
      id: `calculation-${method}`,
      label: `${method.toUpperCase()} 本次计算与选择判据`,
      location: method === 'mm' ? 'MomentProcessViewer' : 'RecordedCalculationProcess / ProcessChart',
      description: '按求参关系分配图表、实际输入输出及关键数值代入；位置联动与回归在对应步骤中阅读，详细操作数按需展开。',
      dataSource: method === 'mmle' ? mmleExample : { type: 'api' as const, endpoint: 'POST /calculate' },
      props: { contract: 'calculation/schema_version=1', methodId: method, source: method === 'mmle' ? 'fixed-example' : 'backend-owned', interpolation: method === 'mm' ? 'empirical stepAfter' : 'linear display only', exampleOnly: method === 'mmle' },
    })),
    {
      id: 'calculation-mdm',
      label: 'MDM 形状寻优与位置梯度判据双图',
      location: 'MDMVisualizer / SigmaBetaChart / GradientGammaChart',
      description: '同一位置下的伪尺度标准差曲线与条件最小点，联动标记位置梯度判据；外推位置不画作真实交点。',
      dataSource: { type: 'api', endpoint: 'POST /calculate' },
      props: { contract: 'calculation/schema_version=1 + trace_data', methodId: 'mdm', source: 'backend-owned', interpolation: 'linear display only' },
    },
    {
      id: 'method-compare-estimates-density',
      label: '不同方法的估计值密度曲线',
      location: 'CompareResultsView',
      description: '在相同真值和样本量下，按参数查看各方法的估计值密度。数据来自匹配的预计算分片或页面发起的模拟。',
      dataSource: { type: 'api', endpoint: 'GET /api/studies/{methodId}/chunks；POST /api/studies/simulate' },
      props: {},
    },
    {
      id: 'mdm-process-optimization-loss-curve',
      label: 'MDM 偏移量预测损失曲线',
      location: '/ai/process-optimization/mdm',
      description: '当前样本在 26 个候选偏移量下的模型预测损失',
      dataSource: { type: 'api', endpoint: 'POST /ai/process-optimization/mdm' },
      props: { xLabel: '偏移量 δ', yLabel: '预测损失', color: '#7c3aed', showDots: true },
    },
    {
      id: 'm3-training-loss',
      label: 'M3 损失收敛曲线',
      location: 'TrainingTab',
      description: '直接估计模型训练损失',
      dataSource: { type: 'json', path: '/ai/data/direct_estimation_n10_metrics.json' },
      props: { xLabel: 'Epoch', yLabel: 'Loss', color: '#10b981' },
    },
  ],

  // ============================================================
  // BoxPlot (ai)
  // ============================================================
  BoxPlot: [
    {
      id: 'm3-performance-boxplot',
      label: 'M3 误差箱型图',
      location: 'PerformanceTab',
      description: '按样本量分组的估计误差分布',
      dataSource: { type: 'json', path: '/ai/data/direct_estimation_a1_preprocessed.json' },
      props: { xLabel: '样本量', yLabel: '误差', color: '#10b981' },
    },
  ],

  // ============================================================
  // MultiLineChart
  // ============================================================
  MultiLineChart: [
    {
      id: 'm3-scheme-compare',
      label: 'M3 方案精度对比',
      location: 'CompareTab',
      description: '8 种预处理方案的精度对比曲线',
      dataSource: { type: 'json', path: '/ai/data/m3_scheme_comparison.json' },
      props: { xLabel: '样本量', yLabel: 'total_relative_mse', color: '#10b981' },
    },
  ],

  // ============================================================
  // BarChart
  // ============================================================
  BarChart: [],

  // ============================================================
  // GroupedBar — 无系统使用位置
  // ============================================================
  GroupedBar: [],

  // ============================================================
  // ScatterWithLine — 无系统使用位置
  // ============================================================
  ScatterWithLine: [],

  // ============================================================
  // DistributionMark — 无系统使用位置
  // ============================================================
  DistributionMark: [],

  // 当前保留范式示例，页面未登记实际使用。
  BoxPlotChart: [],
  HeatmapChart: [],
  DensityChart: [],
  ConvergenceChart: [],

  // ============================================================
  // ContourChart (shared)
  // ============================================================
  ContourChart: [],

  // ============================================================
  // ObjectiveSurface3D (shared)
  // ============================================================
  ObjectiveSurface3D: [],
}

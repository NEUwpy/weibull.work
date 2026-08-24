/**
 * 图表使用注册表
 *
 * 记录每种图表类型在系统中的所有使用位置。
 * 展开时按 dataSource 加载真实数据渲染。
 *
 * 展示范式、表格范式和视觉语义定义见 charts-spec.ts；
 * 本文件只维护真实实例、数据源和实例级 props。
 */

export type DataSource =
  | { type: 'csv'; path: string }
  | { type: 'json'; path: string }
  | { type: 'api'; endpoint: string }

export interface ChartUsage {
  id: string
  label: string
  location: string
  description: string
  dataSource: DataSource
  props: Record<string, unknown>
}

export type ChartRegistry = Record<string, ChartUsage[]>

export const chartRegistry: ChartRegistry = {

  // ============================================================
  // ScatterPlot
  // ============================================================
  ScatterPlot: [],

  // ============================================================
  // Histogram
  // ============================================================
  Histogram: [
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

  // ============================================================
  // BoxPlotChart (shared)
  // ============================================================
  BoxPlotChart: [
    {
      id: 'methods-study-boxplot',
      label: '适用范围箱型图',
      location: 'GenericStudyViewer',
      description: '各参数组合下估计值分布（min/max/P1/P99/median）',
      dataSource: { type: 'csv', path: '/studies/{methodId}/chunks/{chunkFile}' },
      props: { yLabel: 'β̂', trueValue: 2.0 },
    },
  ],

  // ============================================================
  // HeatmapChart (shared)
  // ============================================================
  HeatmapChart: [
    {
      id: 'methods-study-heatmap',
      label: '适用范围热力图',
      location: 'GenericStudyViewer',
      description: 'β-η 参数空间的偏差热力图',
      dataSource: { type: 'csv', path: '/studies/{methodId}/chunks/{chunkFile}' },
      props: { dataKey: 'bias_beta', maxAbs: 0.15 },
    },
  ],

  // ============================================================
  // DensityChart (shared)
  // ============================================================
  DensityChart: [
    {
      id: 'methods-study-density',
      label: '适用范围密度图',
      location: 'GenericStudyViewer',
      description: '估计值的 KDE 概率密度分布',
      dataSource: { type: 'csv', path: '/studies/{methodId}/chunks/{chunkFile}' },
      props: { paramId: 'beta', trueValue: 2.0, color: '#3b82f6' },
    },
  ],

  // ============================================================
  // ConvergenceChart (shared)
  // ============================================================
  ConvergenceChart: [
    {
      id: 'methods-study-convergence',
      label: '适用范围收敛图',
      location: 'GenericStudyViewer',
      description: '统计量随蒙特卡洛仿真次数的收敛趋势',
      dataSource: { type: 'csv', path: '/studies/{methodId}/chunks/{chunkFile}' },
      props: { statType: 'mean', trueValue: 2.0, yLabel: 'β̂ 均值' },
    },
  ],

  // ============================================================
  // ContourChart (shared)
  // ============================================================
  ContourChart: [
    {
      id: 'methods-contour',
      label: '目标函数等高线',
      location: 'MDMVisualizer',
      description: '目标函数在参数空间的等值线 + 优化路径',
      dataSource: { type: 'api', endpoint: 'POST /calculate_3d_surface' },
      props: { xLabel: 'β', yLabel: 'γ', title: '目标函数等高线', height: 260 },
    },
  ],

  // ============================================================
  // ObjectiveSurface3D (shared)
  // ============================================================
  ObjectiveSurface3D: [
    {
      id: 'methods-surface3d',
      label: '3D 目标函数曲面',
      location: 'MDMVisualizer',
      description: '目标函数的三维可视化',
      dataSource: { type: 'api', endpoint: 'POST /calculate_3d_surface' },
      props: { height: 260 },
    },
  ],
}

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
  ScatterPlot: [
    {
      id: 'm1-r1-delta-accuracy',
      label: 'M1-R1 偏移量精度',
      location: 'DeltaAccuracyTab',
      description: 'AI 预测 δ vs 蒙特卡洛最优 δ',
      dataSource: { type: 'csv', path: '/ai/data/validation_predictions_n10.csv' },
      props: { xLabel: '最优 δ', yLabel: 'AI δ', showDiagonal: true, color: '#8b5cf6' },
    },
    {
      id: 'm1-r1-param-beta',
      label: 'M1-R1 参数精度 (β)',
      location: 'ParamAccuracyTab',
      description: 'β 真实值 vs AI δ 估计值',
      dataSource: { type: 'csv', path: '/ai/data/param_accuracy_comparison.csv' },
      props: { xLabel: 'β 真实', yLabel: 'β 估计(AI δ)', showDiagonal: true, color: '#3b82f6' },
    },
    {
      id: 'm1-r1-param-eta',
      label: 'M1-R1 参数精度 (η)',
      location: 'ParamAccuracyTab',
      description: 'η 真实值 vs AI δ 估计值',
      dataSource: { type: 'csv', path: '/ai/data/param_accuracy_comparison.csv' },
      props: { xLabel: 'η 真实', yLabel: 'η 估计(AI δ)', showDiagonal: true, color: '#6366f1' },
    },
    {
      id: 'm1-r1-verification',
      label: 'M1-R1 可信性验证',
      location: 'VerificationTab',
      description: '验证案例：AI δ 预测 vs 最优 δ',
      dataSource: { type: 'csv', path: '/ai/data/verification_cases.csv' },
      props: { xLabel: '最优 δ', yLabel: 'AI δ', showDiagonal: true, color: '#10b981' },
    },
    {
      id: 'm1-r1-data-scatter',
      label: 'M1-R1 训练数据散点',
      location: 'DataTab',
      description: 'δ vs 样本均值的对应关系',
      dataSource: { type: 'csv', path: '/ai/data/training_data_n10.csv' },
      props: { xLabel: '样本均值', yLabel: '最优 δ', color: '#8b5cf6' },
    },
    {
      id: 'm1-r2-delta-accuracy',
      label: 'M1-R2 偏移量精度',
      location: 'DeltaAccuracyTab',
      description: 'R2 迭代收敛后 δ 精度',
      dataSource: { type: 'csv', path: '/ai/data/route2_convergence.csv' },
      props: { xLabel: '最优 δ', yLabel: 'AI δ', showDiagonal: true, color: '#8b5cf6' },
    },
    {
      id: 'm1-r2-param-beta',
      label: 'M1-R2 参数精度 (β)',
      location: 'ParamAccuracyTab',
      description: 'R2 收敛后 β 估计精度',
      dataSource: { type: 'csv', path: '/ai/data/route2_convergence.csv' },
      props: { xLabel: 'β 真实', yLabel: 'β 估计', showDiagonal: true, color: '#3b82f6' },
    },
    {
      id: 'm1-r2-verification',
      label: 'M1-R2 可信性验证',
      location: 'VerificationTab',
      description: 'R2 验证案例精度',
      dataSource: { type: 'csv', path: '/ai/data/route2_convergence.csv' },
      props: { xLabel: '最优 δ', yLabel: 'AI δ', showDiagonal: true, color: '#10b981' },
    },
  ],

  // ============================================================
  // Histogram
  // ============================================================
  Histogram: [
    {
      id: 'm1-r1-delta-error',
      label: 'M1-R1 δ 误差分布',
      location: 'DeltaAccuracyTab',
      description: 'AI 预测 δ 的误差分布直方图',
      dataSource: { type: 'csv', path: '/ai/data/validation_predictions_n10.csv' },
      props: { xLabel: '误差', yLabel: '频数', color: '#8b5cf6', showMean: true },
    },
    {
      id: 'm1-r1-param-beta-error',
      label: 'M1-R1 β 误差分布',
      location: 'ParamAccuracyTab',
      description: 'AI δ 下 β 估计误差分布',
      dataSource: { type: 'csv', path: '/ai/data/param_accuracy_comparison.csv' },
      props: { xLabel: 'β 误差', yLabel: '频数', color: '#3b82f6', showMean: true },
    },
    {
      id: 'm1-r1-data-delta-dist',
      label: 'M1-R1 最优 δ 分布',
      location: 'DataTab',
      description: '训练数据中最优 δ 的分布',
      dataSource: { type: 'csv', path: '/ai/data/training_data_n10.csv' },
      props: { xLabel: '最优 δ', yLabel: '频数', color: '#6366f1' },
    },
    {
      id: 'm1-r2-delta-error',
      label: 'M1-R2 δ 误差分布',
      location: 'DeltaAccuracyTab',
      description: 'R2 迭代后 δ 误差分布',
      dataSource: { type: 'csv', path: '/ai/data/route2_convergence.csv' },
      props: { xLabel: '误差', yLabel: '频数', color: '#8b5cf6', showMean: true },
    },
    {
      id: 'm1-r2-param-error',
      label: 'M1-R2 参数误差分布',
      location: 'ParamAccuracyTab',
      description: 'R2 收敛后参数误差分布',
      dataSource: { type: 'csv', path: '/ai/data/route2_convergence.csv' },
      props: { xLabel: '误差', yLabel: '频数', color: '#3b82f6', showMean: true },
    },
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
      id: 'm1-r1-training-loss',
      label: 'M1-R1 损失收敛曲线',
      location: 'TrainingTab',
      description: '训练/验证损失随 epoch 变化',
      dataSource: { type: 'json', path: '/ai/data/n10_metrics.json' },
      props: { xLabel: 'Epoch', yLabel: 'Loss', color: '#8b5cf6' },
    },
    {
      id: 'm1-r1-sweep-mse',
      label: 'M1-R1 δ Sweep MSE 曲线',
      location: 'CompareTab',
      description: '不同 δ 值下的 MSE 变化',
      dataSource: { type: 'csv', path: '/ai/data/comparison_sweep.csv' },
      props: { xLabel: 'δ', yLabel: 'Mean MSE', color: '#8b5cf6' },
    },
    {
      id: 'm1-r2-training-loss',
      label: 'M1-R2 损失收敛曲线',
      location: 'TrainingTab',
      description: 'R2 模型训练损失曲线',
      dataSource: { type: 'json', path: '/ai/data/delta_from_params_metrics.json' },
      props: { xLabel: 'Epoch', yLabel: 'Loss', color: '#8b5cf6' },
    },
    {
      id: 'm1-r2-iteration-trace',
      label: 'M1-R2 迭代收敛轨迹',
      location: 'IterationTab',
      description: 'δ 随迭代步数的收敛过程',
      dataSource: { type: 'csv', path: '/ai/data/route2_iteration_traces.csv' },
      props: { xLabel: '迭代步', yLabel: 'δ', color: '#3b82f6' },
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
    {
      id: 'm1-vs-m3',
      label: 'M1 vs M3 最优方案对比',
      location: 'CompareTab',
      description: '关系建立 vs 直接估计的跨模块对比',
      dataSource: { type: 'json', path: '/ai/data/m1_vs_m3_best.json' },
      props: { xLabel: '样本量', yLabel: 'total_relative_mse' },
    },
  ],

  // ============================================================
  // BarChart
  // ============================================================
  BarChart: [
    {
      id: 'm1-r1-no-solution-rate',
      label: 'M1-R1 无解率',
      location: 'DataTab',
      description: '各参数组合下的无解率柱状图',
      dataSource: { type: 'csv', path: '/ai/data/training_data_n10.csv' },
      props: { xLabel: '参数组合', yLabel: '无解率', showValue: true },
    },
  ],

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

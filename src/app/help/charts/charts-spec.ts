/**
 * 图表/表格展示规范源
 *
 * 职责：定义 /help/charts 可读规范数据，供页面渲染。
 * 本文件是图表与表格展示规则的事实源；页面只负责渲染，不拥有规范事实。
 *
 * 真实使用实例见：chart-registry.ts。
 * 可执行渲染实现见：src/components/ai/charts 与 src/components/shared/charts。
 */

export type ChartComponentKey =
  | 'ScatterPlot'
  | 'ScatterWithLine'
  | 'Histogram'
  | 'DistributionMark'
  | 'BoxPlot'
  | 'BoxPlotChart'
  | 'DensityChart'
  | 'LineChart'
  | 'MultiLineChart'
  | 'ConvergenceChart'
  | 'BarChart'
  | 'GroupedBar'
  | 'HeatmapChart'
  | 'ContourChart'
  | 'ObjectiveSurface3D'
  | 'ChartCard'

export interface ChartPatternDef {
  name: ChartComponentKey
  nameCn: string
  path: string
  purpose: string
  dataShape: string
  visualSemantics: string
  registryKey?: ChartComponentKey
}

export interface ChartPatternGroup {
  id: string
  title: string
  description: string
  charts: ChartPatternDef[]
}

export interface TablePatternDef {
  id: string
  name: string
  purpose: string
  dataShape: string
  recommendedComponent: string
  visualSemantics: string
  currentUses: string[]
}

export interface UsageMapRow {
  tab: string
  chart: string
  data: string
  src: string
}

export interface UsageMapGroup {
  id: string
  title: string
  accent: string
  rows: UsageMapRow[]
}

export interface VisualSemanticDef {
  id: string
  usage: string
  color: string
  name: string
}

export interface DevNormDef {
  id: string
  content: string
}

export const PAGE_DESCRIPTION = '统一系统图表与表格的展示范式。使用或新增展示前，先查阅本页对应范式；新增真实使用位置时同步 chart-registry.ts。点击「展开」可查看该图表在系统中的真实使用实例。'

export const REGISTRY_RELATIONSHIP = 'charts-spec.ts 定义展示范式、数据契约和视觉语义；chart-registry.ts 记录真实使用位置、数据来源和实例 props；页面从两者读取后渲染。'

export const CHART_DISPLAY_GROUPS: ChartPatternGroup[] = [
  {
    id: 'relationship',
    title: '关系展示',
    description: '两个变量之间的对应关系。',
    charts: [
      {
        name: 'ScatterPlot',
        nameCn: '散点图',
        path: 'ai/charts',
        purpose: '真实值 vs 估计值，带对角线参考线。',
        dataShape: '{ x: number, y: number }[]',
        visualSemantics: '对角线表示理想一致；点云偏离方向表示系统性高估或低估。',
      },
      {
        name: 'ScatterWithLine',
        nameCn: '散点+拟合线',
        path: 'ai/charts',
        purpose: '散点数据 + 拟合曲线。',
        dataShape: 'scatterData: { x, y }[]; lineData: { x, y }[]',
        visualSemantics: '散点呈现实测关系，线条只表示拟合或参考趋势。',
      },
    ],
  },
  {
    id: 'distribution',
    title: '分布展示',
    description: '数据的频率分布与统计特征。',
    charts: [
      {
        name: 'Histogram',
        nameCn: '直方图',
        path: 'ai/charts',
        purpose: '误差分布或估计值频率分布。',
        dataShape: 'number[]',
        visualSemantics: '横轴为误差或估计值，纵轴为频数；均值线仅作分布中心参考。',
      },
      {
        name: 'DistributionMark',
        nameCn: '分布标记',
        path: 'ai/charts',
        purpose: '直方图 + 垂直标记线，展示预测值在分布中的位置。',
        dataShape: 'distributionValues: number[]; markValue: number',
        visualSemantics: '标记线必须代表当前案例值，不用于替代总体分布。',
      },
      {
        name: 'BoxPlot',
        nameCn: '箱型图（AI）',
        path: 'ai/charts',
        purpose: '按分组展示估计值分布，中位数、四分位、异常值。',
        dataShape: '{ label, min, q1, median, q3, max, mean?, count? }[]',
        visualSemantics: '箱体表示 IQR，中位线表示稳健中心，异常值计数用于尾部风险提示。',
      },
      {
        name: 'BoxPlotChart',
        nameCn: '箱型图（Methods）',
        path: 'shared/charts',
        purpose: '适配适用范围数据格式：min/max/P1/P99/median。',
        dataShape: 'rows with est_<param>_min/max/p01/p99/median',
        visualSemantics: '参考线表示真值；P1/P99 用于减少极端值主导视觉判断。',
      },
      {
        name: 'DensityChart',
        nameCn: '密度图',
        path: 'shared/charts',
        purpose: '估计值的 KDE 概率密度分布。',
        dataShape: 'rawData rows + paramId + displayDimension',
        visualSemantics: '曲线高度表示相对密度；真值线用于观察偏移方向。',
      },
    ],
  },
  {
    id: 'trend-comparison',
    title: '趋势与对比',
    description: '随变量变化的趋势或方案间对比。',
    charts: [
      {
        name: 'LineChart',
        nameCn: '折线图',
        path: 'ai/charts',
        purpose: '单系列趋势，如 delta sweep MSE 曲线。',
        dataShape: '{ x: number, y: number }[] or loss history',
        visualSemantics: '横轴是有序变量；折线连接不代表未观测点的真实连续过程，除非数据本身为连续扫描。',
      },
      {
        name: 'MultiLineChart',
        nameCn: '多系列折线图',
        path: 'ai/charts',
        purpose: '多方案精度对比曲线。',
        dataShape: 'rows with xKey plus named numeric series',
        visualSemantics: '同一指标、同一尺度下比较；不同指标不得混在同一纵轴。',
      },
      {
        name: 'ConvergenceChart',
        nameCn: '收敛图',
        path: 'shared/charts',
        purpose: '统计量随蒙特卡洛仿真次数的收敛趋势。',
        dataShape: 'curves: { id, label, data: { mcRuns, value }[] }[]',
        visualSemantics: '真值线用于判断收敛方向；曲线波动不等同于最终误差。',
      },
      {
        name: 'BarChart',
        nameCn: '柱状图',
        path: 'ai/charts',
        purpose: '分类数据对比。',
        dataShape: '{ label: string, value: number, color? }[]',
        visualSemantics: '柱高只比较同一量纲的数值；排序应服务于比较问题。',
      },
      {
        name: 'GroupedBar',
        nameCn: '分组柱状图',
        path: 'ai/charts',
        purpose: '多指标并列对比。',
        dataShape: 'rows with xKey plus grouped numeric metrics',
        visualSemantics: '组内用于同一类别的多个指标对照；指标量纲不一致时拆图。',
      },
    ],
  },
  {
    id: 'spatial',
    title: '空间展示',
    description: '参数空间或目标函数可视化。',
    charts: [
      {
        name: 'HeatmapChart',
        nameCn: '热力图',
        path: 'shared/charts',
        purpose: '二维参数空间的偏差或精度展示。',
        dataShape: 'stats rows + two displayDimensions + dataKey',
        visualSemantics: '发散配色用于带方向误差；单向风险指标使用单调配色。',
      },
      {
        name: 'ContourChart',
        nameCn: '等高线图',
        path: 'shared/charts',
        purpose: '目标函数在参数空间的等值线 + 优化路径。',
        dataShape: 'contourData: { x: number[], y: number[], z: number[][] }',
        visualSemantics: '等高线表示目标函数水平；路径点必须来自真实优化轨迹或明确标注为示意。',
      },
      {
        name: 'ObjectiveSurface3D',
        nameCn: '3D 曲面图',
        path: 'shared/charts',
        purpose: '目标函数的三维可视化。',
        dataShape: 'surfaceData: { betas: number[], gammas: number[], values: number[][] }',
        visualSemantics: '高度表示目标函数值；只用于空间形态认知，不替代表格指标。',
      },
    ],
  },
  {
    id: 'container',
    title: '容器',
    description: '布局与包装组件。',
    charts: [
      {
        name: 'ChartCard',
        nameCn: '图表容器',
        path: 'shared/charts',
        purpose: '统一标题、边框、间距的容器组件。',
        dataShape: 'React children',
        visualSemantics: '只提供布局语义，不拥有指标、图表类型或数据解释。',
      },
    ],
  },
]

export const TABLE_PATTERNS: TablePatternDef[] = [
  {
    id: 'summary-table',
    name: 'Summary table',
    purpose: '展示单个方法、模块或方案的核心结论。',
    dataShape: 'rows: { label, value, unit?, status? }[]',
    recommendedComponent: 'HTML table / compact stat grid',
    visualSemantics: '用于快速扫描，字段少而稳定；状态色只提示判定，不替代数值。',
    currentUses: ['M3 可信性验证精度汇总', '方法结果摘要'],
  },
  {
    id: 'comparison-table',
    name: 'Comparison table',
    purpose: '横向比较多个方法、方案或样本量。',
    dataShape: 'rows keyed by method/scheme; columns keyed by shared metrics',
    recommendedComponent: 'HTML table with fixed metric columns',
    visualSemantics: '同一列必须同一指标同一量纲；主排序指标应在列名或说明中明确。',
    currentUses: ['方法对比', 'AI 方案对比'],
  },
  {
    id: 'diagnostic-table',
    name: 'Diagnostic table',
    purpose: '呈现有效率、尾部风险、异常解和边界状态。',
    dataShape: 'rows with diagnostic metric, value, threshold?, note?',
    recommendedComponent: 'HTML table / alert table',
    visualSemantics: '用于解释主指标背后的风险；不要用诊断表替代主指标表。',
    currentUses: ['可信性验证', '适用范围诊断'],
  },
  {
    id: 'parameter-grid-table',
    name: 'Parameter grid table',
    purpose: '展示 beta/eta/gamma/n 等参数网格与实验配置。',
    dataShape: 'rows or matrix keyed by parameter dimensions',
    recommendedComponent: 'HTML table / scrollable matrix',
    visualSemantics: '参数维度必须保持命名一致；网格表描述实验设计，不声称结果优劣。',
    currentUses: ['适用范围配置', '蒙特卡洛研究设置'],
  },
]

export const CHART_USAGE_MAP_GROUPS: UsageMapGroup[] = [
  {
    id: 'methods',
    title: '参数估计方法（Methods）',
    accent: 'text-blue-700',
    rows: [
      { tab: '计算过程', chart: '直方图', data: 'beta/eta/gamma 估计值分布', src: 'Recharts BarChart' },
      { tab: '计算过程', chart: '折线图', data: 'MSE/Std 随偏移量变化', src: 'Recharts LineChart' },
      { tab: '计算过程', chart: '散点图', data: '估计值 vs 真实值', src: 'Recharts ScatterChart' },
      { tab: '适用范围', chart: '箱型图', data: '各参数组合下估计值分布', src: 'shared BoxPlotChart' },
      { tab: '适用范围', chart: '热力图', data: 'beta-eta 参数空间偏差', src: 'shared HeatmapChart' },
      { tab: '适用范围', chart: '密度图', data: '估计值概率密度', src: 'shared DensityChart' },
      { tab: '可信性验证', chart: '折线图', data: '梯度曲线（MDM）', src: 'mdm GradientGammaChart' },
      { tab: '方法对比', chart: '折线图', data: '多方法精度对比', src: 'Recharts LineChart' },
    ],
  },
  {
    id: 'process-optimization',
    title: '过程量优化',
    accent: 'text-purple-700',
    rows: [
      { tab: 'MDM 偏移量优化', chart: '折线图', data: '候选偏移量—预测损失曲线', src: 'ai AIChartLine' },
    ],
  },
  {
    id: 'direct-estimation',
    title: '直接估计',
    accent: 'text-emerald-700',
    rows: [
      { tab: '性能展示', chart: '散点图', data: '真实 vs 预测', src: 'ai ScatterPlot' },
      { tab: '性能展示', chart: '箱型图', data: '误差分布', src: 'ai BoxPlot' },
      { tab: '性能展示', chart: '直方图', data: '误差频率分布', src: 'ai Histogram' },
      { tab: '可信性验证', chart: '表格', data: '精度汇总表', src: 'HTML table' },
      { tab: '方法对比（方案间）', chart: '折线图', data: '8 方案精度对比', src: 'ai MultiLineChart' },
    ],
  },
]

export const VISUAL_SEMANTICS: VisualSemanticDef[] = [
  { id: 'beta', usage: 'beta 参数（形状参数）', color: '#3b82f6', name: 'blue-500' },
  { id: 'eta', usage: 'eta 参数（尺度参数）', color: '#6366f1', name: 'indigo-500' },
  { id: 'gamma', usage: 'gamma 参数（位置参数）', color: '#a855f7', name: 'purple-500' },
  { id: 'ai-prediction', usage: 'AI 预测结果', color: '#8b5cf6', name: 'violet-500' },
  { id: 'fixed-baseline', usage: '固定值基线', color: '#f59e0b', name: 'amber-500' },
  { id: 'best-reference', usage: '最优值参考', color: '#10b981', name: 'emerald-500' },
  { id: 'positive-error', usage: '误差正值（高估）', color: '#ef4444', name: 'red-500' },
  { id: 'negative-error', usage: '误差负值（低估）', color: '#3b82f6', name: 'blue-500' },
]

export const CHART_DEV_NORMS: DevNormDef[] = [
  { id: 'spec-first', content: '新增图表或表格展示范式时，先更新 charts-spec.ts，定义用途、数据 shape、视觉语义和推荐组件。' },
  { id: 'registry-first', content: '新增图表真实使用位置时，同步更新 chart-registry.ts，记录 location、dataSource 和 props。' },
  { id: 'reuse', content: '使用图表时优先复用已有组件，用 props 控制差异；相同数据含义禁止创建功能重复的图表。' },
  { id: 'semantics', content: '同一参数、误差方向、参考线和基线应复用本规范的视觉语义；不同量纲不要混用同一坐标轴。' },
  { id: 'page-role', content: 'Help 页面只渲染规范源和 registry，不在 TSX 中新增规范事实。' },
]

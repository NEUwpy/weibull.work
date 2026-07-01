/**
 * 指标/公式权威规范源
 *
 * 职责：定义指标规范数据，供 /help/metrics 页面渲染。
 * 本文件是指标说明文字的唯一事实源；页面只负责渲染，不拥有数据。
 *
 * 可执行实现见：src/lib/metrics.ts + python/studies/common/metrics.py
 * 修改指标口径时必须同步上述模块。
 */

export interface MetricDef {
  id: string
  name: string
  nameCn: string
  latex: string
  description: string
  /** 公式变量定义：key = 符号，value = 含义 */
  variables: Record<string, string>
  /** 主指标 / 补充指标 / 诊断指标 */
  role: string
  /** 主指标 or 诊断指标 */
  category: 'primary' | 'supplementary' | 'diagnostic'
  /** 适用视角 */
  perspectives: string[]
  /** 可执行实现位置 */
  implementation: {
    ts: string
    py: string
  }
}

export interface PerspectiveDef {
  id: string
  title: string
  /** 视角级变量定义：key = 符号，value = 含义 */
  variables: Record<string, string>
  accent: string
  bg: string
  border: string
  formula: string
  body: string
}

export interface StatusDef {
  id: string
  label: string
  color: string
  borderColor: string
  description: string
}

export interface DevNormDef {
  id: string
  content: string
}

// ============================================================
// 核心指标族
// ============================================================

export const METRICS: MetricDef[] = [
  {
    id: 'bias',
    name: 'Bias',
    nameCn: '偏差',
    latex: '\\frac{1}{N}\\sum_i(\\hat\\theta_i-\\theta)',
    description: '主指标。回答估计值平均偏高还是偏低，必须关注符号。',
    variables: { 'θ̂_i': '第 i 次估计值', 'θ': '真值', 'N': '有效样本数' },
    role: '方向',
    category: 'primary',
    perspectives: ['参数视角', '工程寿命视角'],
    implementation: { ts: 'src/lib/metrics.ts:summarizeStandardErrors', py: 'python/studies/common/metrics.py' },
  },
  {
    id: 'sd',
    name: 'SD',
    nameCn: '标准差',
    latex: '\\sqrt{\\frac{1}{N-1}\\sum_i(\\hat\\theta_i-\\bar{\\hat\\theta})^2}',
    description: '主指标。回答重复抽样下估计值自身波动有多大。',
    variables: { 'θ̂_i': '第 i 次估计值', 'θ̄̂': '估计值均值', 'N': '有效样本数' },
    role: '稳定性',
    category: 'primary',
    perspectives: ['参数视角', '工程寿命视角'],
    implementation: { ts: 'src/lib/metrics.ts:summarizeStandardErrors', py: 'python/studies/common/metrics.py' },
  },
  {
    id: 'rmse',
    name: 'RMSE',
    nameCn: '均方根误差',
    latex: '\\sqrt{\\frac{1}{N}\\sum_i(\\hat\\theta_i-\\theta)^2}',
    description: '主指标。回答总体误差量级，需与 Bias 和 SD 成套阅读。',
    variables: { 'θ̂_i': '第 i 次估计值', 'θ': '真值', 'N': '有效样本数' },
    role: '综合',
    category: 'primary',
    perspectives: ['参数视角', '工程寿命视角'],
    implementation: { ts: 'src/lib/metrics.ts:summarizeStandardErrors', py: 'python/studies/common/metrics.py' },
  },
  {
    id: 'mae',
    name: 'MAE',
    nameCn: '平均绝对误差',
    latex: '\\frac{1}{N}\\sum_i|\\hat\\theta_i-\\theta|',
    description: '补充指标。与 RMSE 对照可提示尾部或极端误差。',
    variables: { 'θ̂_i': '第 i 次估计值', 'θ': '真值', 'N': '有效样本数' },
    role: '补充',
    category: 'supplementary',
    perspectives: ['参数视角', '工程寿命视角'],
    implementation: { ts: 'src/lib/metrics.ts:summarizeStandardErrors', py: 'python/studies/common/metrics.py' },
  },
]

// ============================================================
// 三种视角
// ============================================================

export const PERSPECTIVES: PerspectiveDef[] = [
  {
    id: 'param',
    title: '参数视角',
    variables: { 'e': '带符号误差', 'β / η / γ': '真实参数', 'β̂ / η̂ / γ̂': '估计参数' },
    accent: 'text-blue-700',
    bg: 'bg-blue-50/70',
    border: 'border-blue-100',
    formula: 'e_\\beta=\\hat\\beta-\\beta,\\quad e_\\eta=\\hat\\eta-\\eta,\\quad e_\\gamma=\\hat\\gamma-\\gamma',
    body: '对 beta、eta、gamma 分别报告 Bias、SD、RMSE、MAE。beta 和 eta 可附相对 Bias/RMSE；gamma 不使用相对指标。',
  },
  {
    id: 'lifetime',
    title: '工程寿命视角',
    variables: { 'x_R': '可靠度为 R 的寿命分位点', 'R': '可靠度水平', 'β / η / γ': '威布尔形状、尺度、位置参数' },
    accent: 'text-purple-700',
    bg: 'bg-purple-50/70',
    border: 'border-purple-100',
    formula: 'x_R=\\gamma+\\eta(-\\ln R)^{1/\\beta}',
    body: '默认关注 x0.95 与 x0.99。每个 R 单独报告 Bias、SD、RMSE、MAE 与相对 RMSE，不用参数排序替代寿命排序。',
  },
  {
    id: 'diagnostic',
    title: '诊断视角',
    variables: { 'MdAPE': '绝对百分误差中位数', 'P95(|e|)': '绝对误差第 95 百分位', 'Valid Rate': '有效估计率' },
    accent: 'text-emerald-700',
    bg: 'bg-emerald-50/70',
    border: 'border-emerald-100',
    formula: 'MdAPE,\\;MedRel,\\;[P_5,P_{95}],\\;P_{95}(|e|),\\;Valid\\;Rate',
    body: 'S2R 中位数族和尾部分位保留为风险诊断，用于发现 RMSE 表格可能掩盖的异常尾部和有效率问题。',
  },
]

// ============================================================
// 状态判定口径
// ============================================================

export const STATUS_DEFINITIONS: StatusDef[] = [
  {
    id: 'success',
    label: 'success / valid',
    color: 'text-emerald-700',
    borderColor: 'border-emerald-200',
    description: '数值有限、beta/eta 为正、方法收敛、未触发边界病态。误差很大但有效的解仍进入尾部统计。',
  },
  {
    id: 'failure',
    label: 'failure',
    color: 'text-red-700',
    borderColor: 'border-red-200',
    description: '不收敛、非有限值、beta/eta 非正，或 gamma 贴到样本最小值等边界病态。',
  },
]

// ============================================================
// 已废止旧指标
// ============================================================

export const DEPRECATED_METRICS = 'NE、NQE_R、RE_R、Outlier Rate、TRMSE 以及旧的均值型主排序口径不再属于当前评价体系。历史实验结果如包含这些字段，只作为旧版本资料，不再用于新研究结论。'

// ============================================================
// 开发规范
// ============================================================

export const DEV_NORMS: DevNormDef[] = [
  { id: 'primary', content: '横向比较默认主口径：Bias、SD、RMSE、MAE；工程寿命视角额外关注 x0.95 / x0.99 的相对 RMSE。S2R 的 MdAPE、方向、IQR、P95/P99 与有效估计率仅作诊断参考。' },
  { id: 'shared', content: '新增实验必须调用共享指标函数，禁止在组件或脚本中内联重复实现。' },
  { id: 'sync', content: '页面规范和共享模块必须双向同步；任何一方变更都要同时更新另一方。' },
  { id: 'goodness', content: '真实工程数据没有真值时，只能评价拟合优度；准确性指标仅用于蒙特卡洛或仿真标签已知场景。' },
]

// ============================================================
// 页面描述
// ============================================================

export const PAGE_DESCRIPTION = '当前系统默认采用第七轮报告的常用指标：参数视角报告 Bias、SD、RMSE、MAE；工程寿命视角报告 x_R 的 Bias、SD、RMSE、MAE 与相对 RMSE。S2R 的 MdAPE、方向、IQR、P95/P99 与有效估计率保留为诊断指标，用于识别尾部风险和异常解。前后端共享实现位于'

export const IMPLEMENTATION_PATHS = {
  ts: 'src/lib/metrics.ts',
  py: 'python/studies/common/metrics.py',
}

import { loadMethodFlow } from './method-flow.mjs'
import type { FlowReference, FlowSource, FlowStep, FlowVariable, MethodFlow } from '../method-flow'

/** Reuse the current workflow's stages, with evidence from the frozen implementation. */
export function archivedMDMFlow(source: FlowSource, base: FlowSource): MethodFlow {
  const current = loadMethodFlow('mdm') as MethodFlow | null
  if (!current?.workflow || current.steps.length !== 6) throw new Error('MDM 计算流程的六步定义缺失')
  const lines = source.lines
  function reference(file: FlowSource, label: string, from: string, until?: string): FlowReference {
    const start = file.lines.findIndex(line => line.trim().startsWith(from))
    const end = until ? file.lines.findIndex((line, index) => index > start && line.trim().startsWith(until)) : start + 1
    if (start < 0 || end <= start) throw new Error('归档 MDM 源码缺少定位：' + from)
    return { file: file.path, label, start, end }
  }
  function stage(label: string, first: number, next: number) {
    return reference(source, label, '# @step: ' + first + ' |', '# @step: ' + next + ' |')
  }
  const locate = stage('位置判据与 Brent 求根', 9, 11)
  const annotation = (key: string) => lines.slice(locate.start, locate.end).map(line => line.trim())
    .find(line => line.startsWith('# @' + key + ': '))?.slice(key.length + 5) ?? ''
  const variables = (key: string): FlowVariable[] => annotation(key).split(', ').map(field => {
    const [code, symbol, meaning] = field.split('|')
    if (!code || !symbol || !meaning) throw new Error('归档位置步骤的输入输出缺失')
    return { code, symbol, meaning }
  })
  const criterion = annotation('formula').split(/;\s*\\quad\s*/).at(-1)
  if (!criterion || !lines.slice(locate.start, locate.end).some(line => line.includes('method="brentq"'))) {
    throw new Error('归档位置步骤缺少公式或求解源码')
  }
  const shapeSearch = reference(source, '有界形状寻优', 'def find_best_beta_for_gamma(', 'def profile_sigma(')
  const ranked = stage('排序样本与经验概率', 1, 3)
  const result = reference(source, '计算拟合优度', 'r2 = self._calculate_r2(')
  const r2 = reference(base, '概率图决定系数', 'def _calculate_r2(')
  r2.end = reference(base, '返回决定系数', 'return 1 - (ss_res / ss_tot)').end
  const stages: Partial<FlowStep>[] = [
    { sources: [ranked, reference(base, '排序和校验', 'def __init__(', 'def log_step('),
      reference(base, 'Bernard 经验概率', 'def _median_ranks(', 'def _cdf_3p(')], primarySource: 0 },
    { sources: [stage('几何位置网格与逐点试算', 5, 7),
      reference(source, '伪尺度样本标准差', 'def calculate_eta_std(', '# @step: 4 |'), shapeSearch],
    formula: { ...current.steps[1].formula, symbols: current.steps[1].formula.symbols.map(variable => {
      if (variable.symbol === '\\beta') return { ...variable, meaning: '试算形状参数' }
      return variable.symbol === '\\sigma_\\eta' ? { ...variable, meaning: '伪尺度的样本标准差' } : variable
    }) }, primarySource: 0 },
    {
      description: '在差分梯度夹住偏移量的区间内，用 Brent 求解位置。',
      basis: 'Research00 冻结程序的 Brent 分支。', notes: '', primarySource: 0,
      formula: {
        expression: criterion,
        equations: [criterion, String.raw`g(\gamma)\approx\frac{\sigma_{\min}(\gamma+h)-\sigma_{\min}(\gamma-h)}{2h}`],
        explanation: '内部点用中心差分，靠近边界时用单边差分。',
        symbols: [
          { symbol: '\\gamma', meaning: '横轴，试算位置' },
          { symbol: 'g(\\gamma)', meaning: '纵轴，最小标准差对位置的差分梯度' },
          { symbol: '\\delta', meaning: '梯度偏移量' },
          { symbol: 'h', meaning: '程序按边界距离选取的差分步长' },
          { symbol: '\\hat\\gamma', meaning: 'Brent 采纳位置' },
        ],
      },
      inputs: variables('inputs').filter(input => input.code !== 'root_info'),
      outputs: variables('outputs'),
      sources: [locate, reference(source, '差分梯度', 'def profile_gradient(', 'def find_right_anchor(')],
    },
    { sources: [
      shapeSearch, { ...locate, label: '在 Brent 根处回代形状', start: lines.findIndex((line, index) =>
        index >= locate.start && line.trim().startsWith('found_gamma = float(root.root)')),
      end: lines.findIndex((line, index) => index >= locate.start && line.trim().startsWith('solution_strategy = "brent_root"')) },
    ], primarySource: 0 },
    { sources: [stage('逐样本反算尺度并取均值', 11, 12)], primarySource: 0 },
    { sources: [result, r2, reference(source, '返回归档估计值与状态', 'return float(found_beta)')], primarySource: 1 },
  ]
  const steps = current.steps.map((step, index) => ({ ...step, ...stages[index] }))
  if (steps.some(step => step.sources.some(ref => ref.start < 0 || ref.end <= ref.start))) throw new Error('归档 MDM 源码范围不完整')
  return { ...current, steps, sources: [source, base], implementation: 'Research00 归档程序', artifacts: [] }
}

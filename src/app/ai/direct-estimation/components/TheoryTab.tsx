/**
 * 原理说明 Tab — 直接估计
 *
 * 按方案显示特有的预处理原理和设计动机
 */
"use client"

import React from 'react'

const SCHEME_THEORY: Record<string, {
  title: string
  coreIdea: string
  inputFormat: string
  inputExample: string
  why: string
  pros: string[]
  cons: string[]
}> = {
  'a-1': {
    title: 'A-1 原始样本',
    coreIdea: '直接将排序后的失效时间样本输入网络，让网络自己学习尺度不变性。这是最朴素的方案，不施加任何预处理，作为其他方案的基线。',
    inputFormat: '[t₁, t₂, ..., tₙ]',
    inputExample: 'n=5: [234.5, 567.8, 890.1, 1234.5, 1567.8]',
    why: '网络具有足够的表达能力，理论上可以从原始样本中隐式提取分布特征。此方案的优势是实现最简单，且不引入任何信息损失。',
    pros: ['实现最简单，无需预处理', '无信息损失', '作为其他方案的基线对比'],
    cons: ['网络需要自行学习尺度不变性', '输入维度随 n 变化，需按 n 训练独立模型'],
  },
  'a-2': {
    title: 'A-2 除以均值',
    coreIdea: '将每个样本除以样本均值 t̄，消除尺度参数 η 的影响，再拼接 t̄ 保留尺度信息。网络只需学习 β 和 γ 的映射。',
    inputFormat: '[t₁/t̄, t₂/t̄, ..., tₙ/t̄, t̄]',
    inputExample: 'n=5: [0.31, 0.73, 1.15, 1.59, 2.02, 776.4]',
    why: 'Weibull 分布中 η 是尺度参数，除以均值相当于做尺度归一化。拼接 t̄ 是为了让网络能恢复 η 的估计值。',
    pros: ['消除 η 的尺度影响，降低学习难度', '拼接 t̄ 保留尺度信息'],
    cons: ['实际实验中对 η 的估计反而变差', '均值接近 0 时数值不稳定'],
  },
  'a-3': {
    title: 'A-3 去位置',
    coreIdea: '减去样本最小值 t_min，消除位置参数 γ 的影响。网络只需学习 β 和 η 的映射。',
    inputFormat: '[t₁-t_min, t₂-t_min, ..., tₙ-t_min]',
    inputExample: 'n=5: [0, 333.3, 655.6, 1000.0, 1333.3]',
    why: 'γ 是位置参数，减去最小值后分布起点归零，理论上可以简化学习任务。',
    pros: ['消除 γ 的位置影响', '网络只需学习 2 个参数'],
    cons: ['丢失了绝对尺度信息，MAE(β) 几乎翻倍', 't_min 本身是随机变量，引入额外噪声'],
  },
  'b-1': {
    title: 'B-1 填充 + 掩码',
    coreIdea: '将样本填充到固定最大长度 n_max=15，用掩码标记哪些位置是真实数据。一个统一模型覆盖所有 n。',
    inputFormat: '[t₁,...,tₙ, 0,...,0, mask₁,...,maskₙ, 0,...,0]',
    inputExample: 'n=5 → 30 维: [234.5,...,1567.8, 0,...,0, 1,1,1,1,1, 0,...,0]',
    why: '掩码让网络知道哪些位置是真实样本、哪些是填充。统一模型可以利用所有 n 的数据联合训练，参数效率更高。',
    pros: ['一个模型覆盖所有 n，实用性强', '精度与独立模型几乎相同', '联合训练增加数据多样性'],
    cons: ['输入维度较大（n_max×2=30）', '小 n 时大部分输入是填充'],
  },
  'b-2': {
    title: 'B-2 除以均值 + 掩码',
    coreIdea: '结合 A-2 的均值归一化和 B-1 的填充掩码。先除以均值消除 η 影响，再填充到 n_max 并加掩码。',
    inputFormat: '[t₁/t̄,...,tₙ/t̄, 0,...,0, t̄, mask₁,...,maskₙ, 0,...,0]',
    inputExample: 'n=5 → 31 维: [0.31,...,2.02, 0,...,0, 776.4, 1,1,1,1,1, 0,...,0]',
    why: '期望均值归一化能降低 η 的学习难度，同时掩码处理变长输入。',
    pros: ['统一模型 + 均值归一化', '理论上降低 η 学习难度'],
    cons: ['实际精度与 B-1 几乎相同', '额外的归一化步骤未带来显著收益'],
  },
  'c-1': {
    title: 'C-1 基础统计量',
    coreIdea: '不输入原始样本，只输入 4 个预计算的统计量：均值、标准差、最小值、最大值。维度固定为 4，与 n 无关。',
    inputFormat: '[mean, std, min, max]',
    inputExample: 'n=10: [776.4, 423.1, 234.5, 1567.8]',
    why: '这 4 个统计量是 Weibull 分布矩的充分统计量的近似。实验表明它们已经提取了足够的分布特征，精度与 A-1 几乎相同。',
    pros: ['维度固定为 4，极小', '与 A-1 精度几乎相同', '计算速度最快'],
    cons: ['丢失了样本的顺序信息', '统计量相同的分布可能参数不同'],
  },
  'c-2': {
    title: 'C-2 扩展统计量',
    coreIdea: '在 C-1 基础上增加偏度、峰度和中位数，共 7 个特征。试图捕获更多分布形态信息。',
    inputFormat: '[mean, std, min, max, skewness, kurtosis, median]',
    inputExample: 'n=10: [776.4, 423.1, 234.5, 1567.8, 0.32, -0.85, 712.3]',
    why: '偏度和峰度描述分布的形状，中位数提供位置信息的另一种度量。理论上这些额外信息应能提升估计精度。',
    pros: ['更多分布形态特征', '维度仍较小（7）'],
    cons: ['实验表明无额外优势', '偏度/峰度在小样本时估计不稳定'],
  },
  'c-3': {
    title: 'C-3 最大化统计量',
    coreIdea: '在 C-2 基础上增加 Q1、Q3、IQR 和变异系数 CV，共 11 个特征。最大化统计量输入的信息量。',
    inputFormat: '[mean, std, min, max, skew, kurt, median, Q1, Q3, IQR, CV]',
    inputExample: 'n=10: [776.4, 423.1, 234.5, 1567.8, 0.32, -0.85, 712.3, 412.5, 1089.2, 676.7, 0.545]',
    why: '分位数（Q1, Q3）和 IQR 提供分布尾部信息，CV 是标准化的离散度量。试图穷举所有可能有用的统计量。',
    pros: ['信息量最大的统计量方案', '包含分位数和变异系数'],
    cons: ['实验表明与 C-1 无显著差异', '更多特征不等于更多信息'],
  },
}

export function TheoryTab({ scheme = 'a-1' }: { scheme?: string }) {
  const theory = SCHEME_THEORY[scheme] || SCHEME_THEORY['a-1']

  return (
    <div className="space-y-6 max-w-3xl">
      {/* 核心思路 */}
      <div>
        <h3 className="text-lg font-bold text-slate-800 mb-3">原理说明 — {theory.title}</h3>
        <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
          <p className="text-sm text-cyan-800 font-medium leading-relaxed">{theory.coreIdea}</p>
        </div>
      </div>

      {/* 输入格式 */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-slate-700 mb-2">输入格式</h4>
        <div className="text-xs text-slate-600 space-y-2">
          <p className="font-mono bg-white px-3 py-2 rounded border border-slate-200">{theory.inputFormat}</p>
          <p className="text-slate-500">示例: <span className="font-mono">{theory.inputExample}</span></p>
        </div>
      </div>

      {/* 设计动机 */}
      <div>
        <h4 className="text-sm font-bold text-slate-700 mb-2">为什么这样设计？</h4>
        <p className="text-sm text-slate-600 leading-relaxed">{theory.why}</p>
      </div>

      {/* 优缺点 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-green-700 mb-2">优势</h4>
          <ul className="text-xs text-green-600 space-y-1.5">
            {theory.pros.map((p, i) => <li key={i}>• {p}</li>)}
          </ul>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-amber-700 mb-2">局限</h4>
          <ul className="text-xs text-amber-600 space-y-1.5">
            {theory.cons.map((c, i) => <li key={i}>• {c}</li>)}
          </ul>
        </div>
      </div>

      {/* 通用信息 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-cyan-700 mb-2">与传统方法的区别</h4>
          <ul className="text-xs text-cyan-600 space-y-1.5">
            <li><span className="font-bold">MLE</span>：需要迭代优化似然函数，可能陷入局部最优</li>
            <li><span className="font-bold">MDM</span>：需要选择偏移量 δ，依赖过程参数</li>
            <li><span className="font-bold">直接估计</span>：无迭代、无过程参数，一步到位</li>
          </ul>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-slate-700 mb-2">三参数 Weibull 分布</h4>
          <div className="text-xs text-slate-600 space-y-1.5">
            <p className="font-mono">F(t) = 1 - exp(-((t-γ)/η)^β), t ≥ γ</p>
            <p><span className="font-bold">β</span> 形状参数 | <span className="font-bold">η</span> 尺度参数 | <span className="font-bold">γ</span> 位置参数</p>
          </div>
        </div>
      </div>

      {/* 参数空间 */}
      <div>
        <h4 className="text-sm font-bold text-slate-700 mb-2">参数空间（V2）</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-50">
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">参数</th>
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">取值</th>
                <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">β</td><td className="border border-slate-200 px-3 py-2">0.5, 1, 2, 3, 5</td><td className="border border-slate-200 px-3 py-2 text-slate-500">形状参数（5 个值）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">η</td><td className="border border-slate-200 px-3 py-2">100, 500, 1000, 3000, 5000</td><td className="border border-slate-200 px-3 py-2 text-slate-500">尺度参数（5 个值）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">γ</td><td className="border border-slate-200 px-3 py-2">50, 100, 200, 1000</td><td className="border border-slate-200 px-3 py-2 text-slate-500">位置参数（4 个值）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">n</td><td className="border border-slate-200 px-3 py-2">5, 7, 10, 15</td><td className="border border-slate-200 px-3 py-2 text-slate-500">样本量（4 个值）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">MC</td><td className="border border-slate-200 px-3 py-2">500</td><td className="border border-slate-200 px-3 py-2 text-slate-500">每组参数模拟次数</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

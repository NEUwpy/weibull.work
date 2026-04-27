import React from 'react'

export function TheoryTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-4">
      <h2 className="text-lg font-bold text-slate-900">原理说明 — M1-R2 迭代逼近</h2>
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800 font-medium">
          核心思路：从初始 δ₀=0.5 开始，用 MDM 估计参数，再用网络预测新 δ，迭代直到收敛。
          不需要直接学习&quot;样本→δ&quot;，而是利用 MDM 自身的估计结果作为真值的近似。
        </p>
      </div>

      <h3 className="text-base font-bold text-slate-800">迭代流程</h3>
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <div className="text-sm font-mono text-slate-600 space-y-1">
          <p>1. 初始 δ₀ = 0.5</p>
          <p>2. 用 δ₀ 运行 MDM → 得到估计参数 (β̂, η̂, γ̂)</p>
          <p>3. 用 M1-R2 网络：输入 (β̂, η̂, γ̂) → 预测新 δ₁</p>
          <p>4. 用 δ₁ 运行 MDM → 新估计参数</p>
          <p>5. 重复直到 |δ_new - δ_old| &lt; 0.001 或达到最大 10 步</p>
        </div>
      </div>

      <h3 className="text-base font-bold text-slate-800">为什么可行？</h3>
      <p className="text-sm text-slate-600 leading-relaxed">
        M1-R2 网络学习的是&quot;参数真值 → 最优 δ&quot;的映射。实际使用时，虽然不知道真值，
        但 MDM 的估计结果是真值的近似。通过迭代，估计结果逐步逼近真值，δ 也随之收敛到最优值。
      </p>

      <h3 className="text-base font-bold text-slate-800">网络架构</h3>
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-blue-700 mb-2">M1-R2 模型（公共模型）</h4>
        <div className="text-xs font-mono text-blue-600 space-y-1">
          <p>Linear(3, 32) → ReLU</p>
          <p>Linear(32, 16) → ReLU</p>
          <p>Linear(16, 1) → Sigmoid</p>
        </div>
        <p className="text-xs text-blue-500 mt-2">
          输入：(β, η, γ) 参数估计值（3 个值）。输出：最优 δ。
          只需训练一个公共模型，不按 n 分。
        </p>
      </div>

      <h3 className="text-base font-bold text-slate-800">收敛判据</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-slate-50">
              <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">参数</th>
              <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">值</th>
              <th className="border border-slate-200 px-3 py-2 text-left font-bold text-slate-600">说明</th>
            </tr>
          </thead>
          <tbody>
            <tr><td className="border border-slate-200 px-3 py-2 font-mono">δ₀</td><td className="border border-slate-200 px-3 py-2">0.5</td><td className="border border-slate-200 px-3 py-2 text-slate-500">初始偏移量</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-mono">ε</td><td className="border border-slate-200 px-3 py-2">0.001</td><td className="border border-slate-200 px-3 py-2 text-slate-500">收敛阈值</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-mono">max_steps</td><td className="border border-slate-200 px-3 py-2">10</td><td className="border border-slate-200 px-3 py-2 text-slate-500">最大迭代步数</td></tr>
          </tbody>
        </table>
      </div>

      <h3 className="text-base font-bold text-slate-800">优势与局限</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-green-700 mb-2">优势</h4>
          <ul className="text-xs text-green-600 space-y-1">
            <li>• 只需一个公共模型，不按 n 分</li>
            <li>• 利用 MDM 自身反馈，理论上更准确</li>
            <li>• 可处理训练数据未覆盖的参数组合</li>
          </ul>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-amber-700 mb-2">局限</h4>
          <ul className="text-xs text-amber-600 space-y-1">
            <li>• 需要多次 MDM 调用，速度较慢</li>
            <li>• 收敛性不保证（可能振荡或发散）</li>
            <li>• 依赖初始值选择</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

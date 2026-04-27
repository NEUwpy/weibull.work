import React from 'react'

export function TheoryTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-4">
      <h2 className="text-lg font-bold text-slate-900">原理说明 — M1-R1 直接学习</h2>
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <p className="text-sm text-purple-800 font-medium">
          核心思路：通过蒙特卡洛模拟生成大量已知真值的样本，训练神经网络学习&quot;样本 → 最优 δ&quot;的映射关系。
          推广到实际数据时，直接用网络预测最优 δ。
        </p>
      </div>

      <h3 className="text-base font-bold text-slate-800">方法流程</h3>
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
        <div className="text-sm font-mono text-slate-600 space-y-1">
          <p>1. 已知真值 (β, η, γ)，蒙特卡洛生成样本</p>
          <p>2. 对每个 δ ∈ [0.001, 1.00]，运行 MDM 得到估计参数</p>
          <p>3. 计算相对 MSE，找到使 MSE 最小的 δ*（最优偏移量）</p>
          <p>4. 训练 M1-R1 网络：输入样本 → 输出 δ*</p>
          <p>5. 实际使用：输入真实失效数据 → 网络预测 δ → MDM 估计参数</p>
        </div>
      </div>

      <h3 className="text-base font-bold text-slate-800">为什么可行？</h3>
      <p className="text-sm text-slate-600 leading-relaxed">
        蒙特卡洛模拟中，我们知道每个样本的参数真值，因此可以精确搜索最优 δ。
        虽然实际数据没有真值，但神经网络可以学习到&quot;样本统计特征 → 最优 δ&quot;的规律，
        并推广到真实场景。
      </p>

      <h3 className="text-base font-bold text-slate-800">网络架构</h3>
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="text-sm font-bold text-purple-700 mb-2">M1-R1 模型（按 n 分别训练）</h4>
        <div className="text-xs font-mono text-purple-600 space-y-1">
          <p>Linear(n, 128) → ReLU → BatchNorm</p>
          <p>Linear(128, 64) → ReLU → BatchNorm</p>
          <p>Linear(64, 1) → Sigmoid</p>
        </div>
        <p className="text-xs text-purple-500 mt-2">
          Sigmoid 输出映射到 [0, 1]，对应 δ 的搜索范围 [0.001, 1.00]。
          按样本量 n=5, 7, 10, 15, 20 分别训练独立模型。
        </p>
      </div>

      <h3 className="text-base font-bold text-slate-800">指标方案</h3>
      <p className="text-sm text-slate-600 leading-relaxed">
        采用相对 MSE 作为最优 δ 的搜索目标：
      </p>
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 font-mono text-sm text-center">
        MSE(δ) = (β̂-β)²/β² + (η̂-η)²/η² + (γ̂-γ)²/γ²
      </div>
      <p className="text-sm text-slate-600 leading-relaxed">
        相对 MSE 消除了不同参数量纲的影响，使三个参数的误差具有可比性。
      </p>

      <h3 className="text-base font-bold text-slate-800">参数空间</h3>
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
            <tr><td className="border border-slate-200 px-3 py-2 font-mono">β</td><td className="border border-slate-200 px-3 py-2">1, 2, 5</td><td className="border border-slate-200 px-3 py-2 text-slate-500">形状参数</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-mono">η</td><td className="border border-slate-200 px-3 py-2">100, 1000, 5000</td><td className="border border-slate-200 px-3 py-2 text-slate-500">尺度参数</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-mono">γ</td><td className="border border-slate-200 px-3 py-2">1000</td><td className="border border-slate-200 px-3 py-2 text-slate-500">位置参数（固定）</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-mono">n</td><td className="border border-slate-200 px-3 py-2">5, 7, 10, 15, 20</td><td className="border border-slate-200 px-3 py-2 text-slate-500">样本量</td></tr>
            <tr><td className="border border-slate-200 px-3 py-2 font-mono">MC</td><td className="border border-slate-200 px-3 py-2">500</td><td className="border border-slate-200 px-3 py-2 text-slate-500">每组参数模拟次数</td></tr>
          </tbody>
        </table>
      </div>

      <h3 className="text-base font-bold text-slate-800">优势与局限</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-green-700 mb-2">优势</h4>
          <ul className="text-xs text-green-600 space-y-1">
            <li>• 预测极快（一次前向传播，&lt;1ms）</li>
            <li>• 不需要迭代，结果确定性高</li>
            <li>• 按 n 分模型，针对性强</li>
          </ul>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <h4 className="text-sm font-bold text-amber-700 mb-2">局限</h4>
          <ul className="text-xs text-amber-600 space-y-1">
            <li>• 精度受训练数据覆盖范围限制</li>
            <li>• 每个 n 需要独立模型</li>
            <li>• 外推能力有限</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

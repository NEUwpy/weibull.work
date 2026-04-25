"use client"

import React, { useState, useCallback } from 'react'
import Link from 'next/link'
import { ArrowLeft, GitBranch, BookOpen, Cpu, Database, Play, BarChart3, FlaskConical, GitCompare, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getApiBaseUrl, API_ENDPOINTS } from '@/lib/config'

const tabs = [
  { id: 'theory', label: '原理说明', icon: BookOpen },
  { id: 'training', label: '训练算法', icon: Cpu },
  { id: 'data', label: '训练数据', icon: Database },
  { id: 'playground', label: '在线使用', icon: Play },
  { id: 'performance', label: '性能展示', icon: BarChart3 },
  { id: 'verification', label: '可信性验证', icon: FlaskConical },
  { id: 'compare', label: '方法对比', icon: GitCompare },
]

export default function RelationshipPage() {
  const [activeTab, setActiveTab] = useState('theory')

  return (
    <section className="w-full max-w-[95%] xl:max-w-[1800px] mx-auto pl-[4.5rem] pr-[4rem] py-8 space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <Link href="/ai" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors">
          <ArrowLeft size={14} />
          返回 AI 方法总览
        </Link>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-600 text-white shadow-sm">
            <GitBranch size={22} />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-900">关系建立 — MDM 偏移量优化</h1>
            <p className="text-sm text-slate-500 font-medium">AI 学习"样本 → 最优偏移量 δ"的映射</p>
          </div>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="flex border-b border-slate-200 overflow-x-auto scrollbar-hide">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-5 py-3 text-sm font-bold whitespace-nowrap transition-all border-b-2",
                  activeTab === tab.id
                    ? "text-purple-600 border-purple-600 bg-purple-50/50"
                    : "text-slate-400 border-transparent hover:text-slate-600 hover:bg-slate-50"
                )}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Tab Content */}
        <div className="p-6 min-h-[400px]">
          {activeTab === 'theory' && <TheoryTab />}
          {activeTab === 'training' && <TrainingTab />}
          {activeTab === 'data' && <DataTab />}
          {activeTab === 'playground' && <PlaygroundTab />}
          {activeTab === 'performance' && <PerformanceTab />}
          {activeTab === 'verification' && <VerificationTab />}
          {activeTab === 'compare' && <CompareTab />}
        </div>
      </div>
    </section>
  )
}

function TheoryTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-4">
      <h2 className="text-lg font-bold text-slate-900">原理说明</h2>
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <p className="text-sm text-purple-800 font-medium">
          核心思路：MDM 方法需要手动选择偏移量 δ，不同样本的最优 δ 不同。
          本模块训练神经网络，直接从样本数据预测最优 δ，替代人工反复尝试。
        </p>
      </div>
      <h3 className="text-base font-bold text-slate-800">为什么需要这个模块？</h3>
      <p className="text-sm text-slate-600 leading-relaxed">
        MDM（最小差异法）中的偏移量 δ 是一个关键的过程参数，它控制梯度偏移判据的阈值。
        不同的 δ 值会导致完全不同的参数估计结果。传统做法是人工尝试多个 δ 值，
        但这既耗时又依赖经验。本模块用 AI 自动化这一过程。
      </p>
      <h3 className="text-base font-bold text-slate-800">AI 方法与传统方法的关系</h3>
      <p className="text-sm text-slate-600 leading-relaxed">
        本模块不替代 MDM 方法本身，而是替代"选择 δ"这一步。MDM 算法仍然负责参数估计，
        AI 只是给出一个更好的输入参数。这是一种"关系建立"型的 AI 辅助方式。
      </p>
      <h3 className="text-base font-bold text-slate-800">工作流程</h3>
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm font-mono text-slate-600 space-y-1">
        <p>离线阶段：蒙特卡洛模拟 → 遍历 δ 网格 → MSE 评价 → 训练神经网络</p>
        <p>在线阶段：用户输入样本 → AI 推理 → 输出最优 δ → 用户运行 MDM</p>
      </div>
    </div>
  )
}

function TrainingTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-6">
      <h2 className="text-lg font-bold text-slate-900">训练算法</h2>

      {/* 网络结构 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-2">网络结构</h3>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <div className="text-sm font-mono text-slate-700 space-y-1">
            <p>输入层: n 个神经元（排序后的失效时间，标准化）</p>
            <p>隐藏层 1: 64 个神经元, ReLU</p>
            <p>隐藏层 2: 32 个神经元, ReLU</p>
            <p>输出层: 1 个神经元, Sigmoid → 缩放到 [0.01, 0.50]</p>
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          按样本量 n 分别训练独立模型，每个模型输入维度固定 = n。
        </p>
      </div>

      {/* 数据预处理 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-2">数据预处理</h3>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-600 space-y-2">
          <p><strong>输入标准化</strong>：按列标准化为零均值、单位方差（从训练集计算参数）</p>
          <p><strong>目标缩放</strong>：δ 值从 [0.01, 0.50] 线性缩放到 [0, 1]</p>
          <p><strong>推理时</strong>：使用保存的标准化参数对输入做同样变换，输出反缩放回 δ 范围</p>
        </div>
      </div>

      {/* 训练策略 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-2">训练策略</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
            <div className="text-xs text-slate-400 mb-1">损失函数</div>
            <div className="text-sm font-bold text-slate-700">MSE（均方误差）</div>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
            <div className="text-xs text-slate-400 mb-1">优化器</div>
            <div className="text-sm font-bold text-slate-700">Adam, lr=0.01</div>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
            <div className="text-xs text-slate-400 mb-1">早停</div>
            <div className="text-sm font-bold text-slate-700">patience=20</div>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
            <div className="text-xs text-slate-400 mb-1">验证比例</div>
            <div className="text-sm font-bold text-slate-700">20%</div>
          </div>
        </div>
      </div>

      {/* 评价标准 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-2">最优 δ 评价标准</h3>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-sm text-purple-800">
          <p className="font-bold mb-1">MSE(β, η, γ)</p>
          <p>对每个候选 δ，运行 MDM 得到 est_β, est_η, est_γ，计算：</p>
          <p className="font-mono mt-1">MSE = (est_β - β)² + (est_η - η)² + (est_γ - γ)²</p>
          <p className="mt-1">使 MSE 最小的 δ 即为该样本的最优 δ*</p>
        </div>
      </div>
    </div>
  )
}

function DataTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-6">
      <h2 className="text-lg font-bold text-slate-900">训练数据</h2>

      {/* 数据生成方式 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-2">数据生成方式</h3>
        <p className="text-sm text-slate-600 leading-relaxed">
          蒙特卡洛模拟生成。对每组参数 (β, η, γ, n)，生成 MC 个 Weibull 分布样本，
          对每个样本遍历 δ 网格找到最优 δ*。
        </p>
      </div>

      {/* 参数空间 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-2">参数空间（精简方案）</h3>
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
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">β</td><td className="border border-slate-200 px-3 py-2">1, 2</td><td className="border border-slate-200 px-3 py-2 text-slate-500">形状参数</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">η</td><td className="border border-slate-200 px-3 py-2">1000</td><td className="border border-slate-200 px-3 py-2 text-slate-500">尺度参数（固定）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">γ</td><td className="border border-slate-200 px-3 py-2">0</td><td className="border border-slate-200 px-3 py-2 text-slate-500">位置参数（固定）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">n</td><td className="border border-slate-200 px-3 py-2">5, 10</td><td className="border border-slate-200 px-3 py-2 text-slate-500">样本量</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">δ</td><td className="border border-slate-200 px-3 py-2">[0.01, 0.50] 步长 0.01</td><td className="border border-slate-200 px-3 py-2 text-slate-500">搜索网格（50 个值）</td></tr>
              <tr><td className="border border-slate-200 px-3 py-2 font-mono">MC</td><td className="border border-slate-200 px-3 py-2">200</td><td className="border border-slate-200 px-3 py-2 text-slate-500">每组参数模拟次数</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 数据规模 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-2">数据规模</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <div className="text-xs text-green-600 mb-1">n=5 模型</div>
            <div className="text-lg font-black text-green-800">309 条</div>
            <div className="text-xs text-green-500">β=1: 125/200, β=2: 184/200</div>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <div className="text-xs text-green-600 mb-1">n=10 模型</div>
            <div className="text-lg font-black text-green-800">289 条</div>
            <div className="text-xs text-green-500">β=1: 119/200, β=2: 170/200</div>
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-2">
          注：部分样本的所有 δ 值均无解（MDM 返回 no_intersection），已过滤。
        </p>
      </div>

      {/* 数据格式 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-2">数据格式</h3>
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 font-mono text-xs text-slate-600">
          <p>n, t1, t2, t3, t4, t5, optimal_delta, best_mse</p>
          <p>5, 398.33, 520.32, 814.43, 921.33, 2344.04, 0.01, 253411.83</p>
          <p>5, 147.10, 358.04, 1291.80, 1559.25, 3439.88, 0.50, 205920.02</p>
        </div>
      </div>
    </div>
  )
}

function PlaygroundTab() {
  const [sampleInput, setSampleInput] = useState('')
  const [result, setResult] = useState<{ optimal_delta: number; model_n: number; confidence: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handlePredict = useCallback(async () => {
    setError('')
    setResult(null)

    // 解析输入
    const values = sampleInput
      .split(/[\n,\s]+/)
      .map(s => s.trim())
      .filter(s => s.length > 0)
      .map(Number)

    if (values.some(isNaN)) {
      setError('输入包含非数值，请检查')
      return
    }
    if (values.length < 3) {
      setError('样本量至少为 3')
      return
    }

    setLoading(true)
    try {
      const baseUrl = getApiBaseUrl()
      const res = await fetch(`${baseUrl}${API_ENDPOINTS.aiPredictDelta}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: values }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '请求失败' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }, [sampleInput])

  const confidenceMap: Record<string, { label: string; color: string }> = {
    high: { label: '高', color: 'text-green-600 bg-green-50' },
    medium: { label: '中', color: 'text-yellow-600 bg-yellow-50' },
    low: { label: '低', color: 'text-red-600 bg-red-50' },
  }

  return (
    <div className="prose prose-slate max-w-none space-y-6">
      <h2 className="text-lg font-bold text-slate-900">在线使用</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 输入区 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-slate-800">输入样本数据</h3>
          <p className="text-xs text-slate-400">
            输入排序后的失效时间，每行一个或用逗号/空格分隔。当前支持 n=5 和 n=10。
          </p>
          <textarea
            value={sampleInput}
            onChange={(e) => setSampleInput(e.target.value)}
            placeholder={"例如 (n=5):\n398.3\n520.3\n814.4\n921.3\n2344.0"}
            className="w-full h-40 p-3 border border-slate-200 rounded-lg text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
          <button
            onClick={handlePredict}
            disabled={loading}
            className={cn(
              "w-full py-2.5 rounded-lg text-sm font-bold text-white transition-all",
              loading
                ? "bg-purple-400 cursor-not-allowed"
                : "bg-purple-600 hover:bg-purple-700 active:bg-purple-800"
            )}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                AI 预测中...
              </span>
            ) : (
              'AI 预测最优 δ'
            )}
          </button>
        </div>

        {/* 输出区 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-slate-800">预测结果</h3>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {result && (
            <div className="space-y-3">
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <div className="text-xs text-purple-500 mb-1">AI 预测的最优偏移量</div>
                <div className="text-3xl font-black text-purple-700 font-mono">
                  δ = {result.optimal_delta}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-1">使用模型</div>
                  <div className="text-sm font-bold text-slate-700">n={result.model_n}</div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-1">置信度</div>
                  <span className={cn("px-2 py-0.5 rounded text-xs font-bold", confidenceMap[result.confidence]?.color)}>
                    {confidenceMap[result.confidence]?.label || result.confidence}
                  </span>
                </div>
              </div>
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
                <CheckCircle2 size={16} className="text-green-500 mt-0.5 shrink-0" />
                <p className="text-xs text-green-700">
                  将此 δ 值输入 MDM 方法的偏移量参数，即可运行参数估计。
                </p>
              </div>
            </div>
          )}

          {!result && !error && (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
              <Play size={32} className="mx-auto text-slate-300 mb-3" />
              <p className="text-sm text-slate-400">输入样本数据后点击"AI 预测最优 δ"</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function PerformanceTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-6">
      <h2 className="text-lg font-bold text-slate-900">性能展示</h2>

      {/* 模型指标 */}
      <div>
        <h3 className="text-base font-bold text-slate-800 mb-3">模型验证指标</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
            <div className="text-xs text-slate-400 mb-2">n=5 模型</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-slate-500">MSE</span><span className="font-mono font-bold">0.006824</span></div>
              <div className="flex justify-between"><span className="text-slate-500">MAE</span><span className="font-mono font-bold">0.036692</span></div>
              <div className="flex justify-between"><span className="text-slate-500">RMSE</span><span className="font-mono font-bold">0.082605</span></div>
            </div>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
            <div className="text-xs text-slate-400 mb-2">n=10 模型</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-slate-500">MSE</span><span className="font-mono font-bold">0.001352</span></div>
              <div className="flex justify-between"><span className="text-slate-500">MAE</span><span className="font-mono font-bold">0.020116</span></div>
              <div className="flex justify-between"><span className="text-slate-500">RMSE</span><span className="font-mono font-bold">0.036770</span></div>
            </div>
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-2">
          MAE 表示预测 δ 与真实最优 δ 的平均绝对误差。δ 范围为 [0.01, 0.50]。
        </p>
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
        <BarChart3 size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-400">更多可视化（热力图、箱型图等）待开发</p>
        <p className="text-xs text-slate-300 mt-1">将展示与传统固定 δ 的对比、适用范围分析等</p>
      </div>
    </div>
  )
}

function VerificationTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-4">
      <h2 className="text-lg font-bold text-slate-900">可信性验证</h2>
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
        <FlaskConical size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-400">可信性验证待完善</p>
        <p className="text-xs text-slate-300 mt-1">将展示已知参数验证案例、边界条件测试等</p>
      </div>
    </div>
  )
}

function CompareTab() {
  return (
    <div className="prose prose-slate max-w-none space-y-4">
      <h2 className="text-lg font-bold text-slate-900">方法对比</h2>
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
        <GitCompare size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="text-sm text-slate-400">方法对比待完善</p>
        <p className="text-xs text-slate-300 mt-1">将展示 AI 预测 δ vs 固定 δ 的蒙特卡洛对比</p>
      </div>
    </div>
  )
}

"use client"

import React, { useState, useEffect } from 'react'
import { Table2, Table, ChevronDown, BookOpen } from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts'

interface Case5ViewerProps {
  caseId: string
  onCaseChange?: (caseId: string) => void  // 案例切换回调
}

// 估计结果
interface EstimateResult {
  sample_id: string
  est_beta: number
  est_eta: number
  est_gamma: number
  bias_beta: number
  bias_eta: number
  bias_gamma: number
}

// 样本原始数据
interface SampleData {
  id: string
  values: number[]
}

// 梯度曲线点
interface GradientPoint {
  gamma: number
  gradient: number
  sigma_min?: number
  best_beta?: number
  best_eta?: number
}

// 样本曲线数据
interface SampleCurve {
  sample_id: string
  grad_gamma_curve: GradientPoint[]
}

// 统计摘要
interface Summary {
  n_samples: number
  true_params: {
    beta: number
    eta: number
    gamma: number
  }
  estimates: {
    beta_mean: number
    beta_std: number
    beta_min: number
    beta_max: number
    eta_mean: number
    eta_std: number
    eta_min: number
    eta_max: number
    gamma_mean: number
    gamma_std: number
    gamma_min: number
    gamma_max: number
  }
  bias: {
    beta_mean: number
    beta_std: number
    beta_min: number
    beta_max: number
    eta_mean: number
    eta_std: number
    eta_min: number
    eta_max: number
    gamma_mean: number
    gamma_std: number
    gamma_min: number
    gamma_max: number
  }
}

const OFFSET_VALUE = 0.1
const TRUE_GAMMA = 1000

// 硬编码数据
const HARDCODED_SUMMARY: Summary = {
  n_samples: 30,
  true_params: { beta: 2.0, eta: 1000.0, gamma: 1000.0 },
  estimates: {
    beta_mean: 1.7455275287124965,
    beta_std: 0.7534821472375753,
    beta_min: 0.6137084321317491,
    beta_max: 3.943287946776372,
    eta_mean: 826.0828283433111,
    eta_std: 333.4287498037288,
    eta_min: 313.8320365906693,
    eta_max: 1481.4598088197547,
    gamma_mean: 1136.9630660333337,
    gamma_std: 298.7344178425892,
    gamma_min: 517.1904356455614,
    gamma_max: 1620.546177954649
  },
  bias: {
    beta_mean: -0.25447247128750333,
    beta_std: 0.7534821472375753,
    beta_min: -1.386291567868251,
    beta_max: 1.9432879467763722,
    eta_mean: -173.91717165668882,
    eta_std: 333.4287498037288,
    eta_min: -686.1679634093307,
    eta_max: 481.4598088197547,
    gamma_mean: 136.9630660333336,
    gamma_std: 298.7344178425892,
    gamma_min: -482.80956435443863,
    gamma_max: 620.546177954649
  }
}

const HARDCODED_RESULTS: EstimateResult[] = [
  { sample_id: "Sample-1-1", est_beta: 1.241723221204818, est_eta: 660.4882125576095, est_gamma: 1291.480043009358, bias_beta: -0.7582767787951821, bias_eta: -339.5117874423905, bias_gamma: 291.48004300935804 },
  { sample_id: "Sample-1-2", est_beta: 1.1723964824076267, est_eta: 761.8933875752871, est_gamma: 1115.9795936403327, bias_beta: -0.8276035175923733, bias_eta: -238.10661242471292, bias_gamma: 115.97959364033272 },
  { sample_id: "Sample-1-3", est_beta: 1.7247283066394565, est_eta: 621.6447050256356, est_gamma: 1153.4131706238798, bias_beta: -0.27527169336054347, bias_eta: -378.35529497436437, bias_gamma: 153.41317062387975 },
  { sample_id: "Sample-1-4", est_beta: 1.8186732746145597, est_eta: 791.7210358058303, est_gamma: 1117.9917784305562, bias_beta: -0.18132672538544026, bias_eta: -208.2789641941697, bias_gamma: 117.99177843055622 },
  { sample_id: "Sample-1-5", est_beta: 1.5090324071805448, est_eta: 607.4949580912861, est_gamma: 1299.5130751993381, bias_beta: -0.49096759281945523, bias_eta: -392.5050419087139, bias_gamma: 299.5130751993381 },
  { sample_id: "Sample-2-1", est_beta: 2.2176609688662103, est_eta: 742.4329767303273, est_gamma: 1554.6893425312428, bias_beta: 0.21766096886621034, bias_eta: -257.56702326967275, bias_gamma: 554.6893425312428 },
  { sample_id: "Sample-2-2", est_beta: 1.5516598624465565, est_eta: 1132.7263034242221, est_gamma: 863.0862061364147, bias_beta: -0.4483401375534435, bias_eta: 132.72630342422212, bias_gamma: -136.91379386358528 },
  { sample_id: "Sample-2-3", est_beta: 1.3434319380705337, est_eta: 823.6022302706491, est_gamma: 1149.3136313262899, bias_beta: -0.6565680619294663, bias_eta: -176.3977697293509, bias_gamma: 149.31363132628985 },
  { sample_id: "Sample-2-4", est_beta: 2.5198199676095983, est_eta: 1423.5073738788926, est_gamma: 572.7855830172025, bias_beta: 0.5198199676095983, bias_eta: 423.5073738788926, bias_gamma: -427.2144169827975 },
  { sample_id: "Sample-2-5", est_beta: 1.1749513124084152, est_eta: 542.6250516940316, est_gamma: 1567.2937074268327, bias_beta: -0.8250486875915848, bias_eta: -457.37494830596836, bias_gamma: 567.2937074268327 },
  { sample_id: "Sample-3-1", est_beta: 2.3230604130348866, est_eta: 1439.3160430995886, est_gamma: 770.7680130271607, bias_beta: 0.32306041303488664, bias_eta: 439.31604309958857, bias_gamma: -229.2319869728393 },
  { sample_id: "Sample-3-2", est_beta: 1.0258169619864306, est_eta: 587.1660742812765, est_gamma: 1620.546177954649, bias_beta: -0.9741830380135694, bias_eta: -412.83392571872355, bias_gamma: 620.546177954649 },
  { sample_id: "Sample-3-3", est_beta: 1.2987096263179716, est_eta: 987.9215161536374, est_gamma: 1164.8865405566453, bias_beta: -0.7012903736820284, bias_eta: -12.078483846362587, bias_gamma: 164.8865405566453 },
  { sample_id: "Sample-3-4", est_beta: 0.9577468735314026, est_eta: 317.7761034701127, est_gamma: 1131.9131868919771, bias_beta: -1.0422531264685975, bias_eta: -682.2238965298873, bias_gamma: 131.91318689197715 },
  { sample_id: "Sample-3-5", est_beta: 3.3892440180253613, est_eta: 1481.4598088197547, est_gamma: 517.1904356455614, bias_beta: 1.3892440180253613, bias_eta: 481.4598088197547, bias_gamma: -482.80956435443863 },
  { sample_id: "Sample-4-1", est_beta: 2.017479713738604, est_eta: 584.63353273211, est_gamma: 1136.7125241056438, bias_beta: 0.01747971373860402, bias_eta: -415.36646726789, bias_gamma: 136.71252410564375 },
  { sample_id: "Sample-4-2", est_beta: 2.8822115861704236, est_eta: 1202.705086117702, est_gamma: 715.1464337437678, bias_beta: 0.8822115861704236, bias_eta: 202.70508611770197, bias_gamma: -284.85356625623217 },
  { sample_id: "Sample-4-3", est_beta: 3.943287946776372, est_eta: 901.4942627107515, est_gamma: 1008.5784152969138, bias_beta: 1.9432879467763722, bias_eta: -98.50573728924849, bias_gamma: 8.578415296913818 },
  { sample_id: "Sample-4-4", est_beta: 1.504790521650454, est_eta: 971.6520348242769, est_gamma: 945.1904565736515, bias_beta: -0.495209478349546, bias_eta: -28.34796517572306, bias_gamma: -54.809543426348455 },
  { sample_id: "Sample-4-5", est_beta: 1.6216452271947646, est_eta: 419.8894414078228, est_gamma: 1346.7660499378972, bias_beta: -0.37835477280523544, bias_eta: -580.1105585921772, bias_gamma: 346.76604993789715 },
  { sample_id: "Sample-5-1", est_beta: 1.7240856116828738, est_eta: 899.192225623945, est_gamma: 1265.0902624181483, bias_beta: -0.2759143883171262, bias_eta: -100.80777437605502, bias_gamma: 265.0902624181483 },
  { sample_id: "Sample-5-2", est_beta: 2.431161294670844, est_eta: 1284.23305702899, est_gamma: 717.9932029923416, bias_beta: 0.4311612946708441, bias_eta: 284.23305702899006, bias_gamma: -282.0067970076584 },
  { sample_id: "Sample-5-3", est_beta: 0.6137084321317491, est_eta: 316.0889499308345, est_gamma: 1557.782490585847, bias_beta: -1.386291567868251, bias_eta: -683.9110500691655, bias_gamma: 557.782490585847 },
  { sample_id: "Sample-5-4", est_beta: 1.5786891657862312, est_eta: 903.5110549897627, est_gamma: 944.1910873764377, bias_beta: -0.4213108342137688, bias_eta: -96.48894501023733, bias_gamma: -55.808912623562264 },
  { sample_id: "Sample-5-5", est_beta: 2.093924699968136, est_eta: 944.5025242417435, est_gamma: 989.3611394407485, bias_beta: 0.0939246999681358, bias_eta: -55.49747575825654, bias_gamma: -10.638860559251498 },
  { sample_id: "Sample-6-1", est_beta: 1.2694594641079668, est_eta: 687.7846585415188, est_gamma: 1298.0222176225957, bias_beta: -0.7305405358920332, bias_eta: -312.21534145848125, bias_gamma: 298.0222176225957 },
  { sample_id: "Sample-6-2", est_beta: 1.0828403847271348, est_eta: 516.5762626674857, est_gamma: 1555.5851988732522, bias_beta: -0.9171596152728652, bias_eta: -483.4237373325143, bias_gamma: 555.5851988732522 },
  { sample_id: "Sample-6-3", est_beta: 0.6318536366321733, est_eta: 313.8320365906693, est_gamma: 1422.513334373346, bias_beta: -1.3681463633678268, bias_eta: -686.1679634093307, bias_gamma: 422.51333437334597 },
  { sample_id: "Sample-6-4", est_beta: 1.8723726225790844, est_eta: 715.3193793263437, est_gamma: 1009.4352014755873, bias_beta: -0.12762737742091557, bias_eta: -284.68062067365634, bias_gamma: 9.435201475587291 },
  { sample_id: "Sample-6-5", est_beta: 1.8296599192137157, est_eta: 1199.2945626872377, est_gamma: 1305.6734807663881, bias_beta: -0.17034008078628426, bias_eta: 199.29456268723766, bias_gamma: 305.67348076638814 }
]

const HARDCODED_SAMPLES: SampleData[] = [
  { id: "Sample-1-1", values: [2169.404124, 1495.137639, 1611.636815, 1875.719873, 1396.679767, 2567.302436, 1970.930395] },
  { id: "Sample-1-2", values: [1328.582934, 1223.817680, 1980.678812, 2805.458535, 1883.434438, 1521.669168, 1773.679313] },
  { id: "Sample-1-3", values: [1349.386993, 1915.966836, 1699.266217, 1327.031945, 1734.944708, 1614.327472, 2255.595818] },
  { id: "Sample-1-4", values: [1804.452967, 1329.241943, 1810.107407, 1624.618302, 1524.371568, 2182.387254, 2348.660660] },
  { id: "Sample-1-5", values: [1422.728248, 1787.028878, 1589.722088, 1747.622659, 1651.642585, 2232.839744, 2365.464564] },
  { id: "Sample-2-1", values: [2247.514730, 2492.594913, 2362.543556, 1995.070696, 2008.012693, 2501.449476, 1798.145256] },
  { id: "Sample-2-2", values: [2632.155762, 1106.473293, 1901.528578, 2574.811431, 1559.860803, 1373.533968, 1726.372387] },
  { id: "Sample-2-3", values: [1809.507602, 1904.765756, 2962.360405, 1335.008787, 1310.772758, 2194.217695, 1704.967315] },
  { id: "Sample-2-4", values: [2350.853297, 1720.305536, 2244.556278, 2068.820183, 1153.892628, 1146.538468, 2118.146221] },
  { id: "Sample-2-5", values: [1785.506907, 1643.269185, 1756.341761, 2340.579693, 1892.022628, 2597.991610, 2311.230365] },
  { id: "Sample-3-1", values: [2275.971290, 1957.525490, 2312.039789, 2925.863843, 1666.129762, 1261.541933, 1816.125310] },
  { id: "Sample-3-2", values: [1747.945624, 1691.297521, 2655.932670, 1723.773700, 2105.238644, 2673.158335, 2549.073470] },
  { id: "Sample-3-3", values: [1629.281260, 1627.173605, 1318.518348, 3124.373755, 2993.898166, 1959.706577, 1686.712894] },
  { id: "Sample-3-4", values: [1344.406778, 1573.733957, 1262.822124, 1852.182489, 1194.202526, 1565.435399, 1162.550510] },
  { id: "Sample-3-5", values: [2023.538906, 1840.160429, 2161.873262, 1156.489813, 2293.419446, 1593.802593, 1851.663078] },
  { id: "Sample-4-1", values: [1472.210858, 1627.596083, 1485.711074, 1970.482526, 1313.032537, 1902.354056, 1742.820119] },
  { id: "Sample-4-2", values: [1888.377244, 1792.071145, 1687.535530, 1156.006466, 2526.955216, 1820.029861, 1632.235679] },
  { id: "Sample-4-3", values: [1826.702437, 1828.070594, 1831.303717, 1376.329852, 2223.170239, 1806.259817, 1925.571759] },
  { id: "Sample-4-4", values: [2218.361275, 2069.584423, 1321.257555, 1442.206573, 1154.886741, 2433.536992, 1827.322922] },
  { id: "Sample-4-5", values: [1697.721402, 1449.315711, 1766.821036, 1480.694786, 1695.458958, 1705.420987, 2214.695247] },
  { id: "Sample-5-1", values: [1505.789653, 2634.680211, 2352.897185, 1626.438579, 2268.106445, 2248.535789, 1689.728980] },
  { id: "Sample-5-2", values: [1726.207492, 2183.620600, 2177.319803, 2199.498897, 2123.015840, 1190.972095, 1289.042216] },
  { id: "Sample-5-3", values: [1610.301143, 1943.148021, 1820.229231, 1572.953512, 2861.187484, 1565.953003, 2221.235505] },
  { id: "Sample-5-4", values: [1183.130160, 2206.071191, 1993.480135, 2530.309873, 1898.577798, 1249.733946, 1214.208480] },
  { id: "Sample-5-5", values: [1748.489797, 1372.793773, 1877.440903, 2375.365736, 2174.031836, 1850.837483, 1308.095154] },
  { id: "Sample-6-1", values: [1855.196031, 1402.639591, 1630.665188, 2866.966565, 2288.512196, 1750.787516, 1597.611698] },
  { id: "Sample-6-2", values: [1682.034769, 2425.431836, 2444.196329, 1966.677668, 1779.608048, 1620.236808, 2141.265350] },
  { id: "Sample-6-3", values: [1430.724077, 2632.924529, 1463.409269, 1469.488488, 2019.967671, 1620.885368, 1811.277248] },
  { id: "Sample-6-4", values: [1804.037585, 1619.712375, 2066.630491, 1300.819231, 1871.706271, 1521.770559, 1220.792992] },
  { id: "Sample-6-5", values: [1924.142014, 2499.407874, 2449.594381, 2148.928657, 2355.329444, 3412.546390, 1617.626596] }
]

export default function Case5Viewer({ caseId, onCaseChange }: Case5ViewerProps) {
  const [curvesData, setCurvesData] = useState<SampleCurve[]>([])
  const [loading, setLoading] = useState(true)

  const results = HARDCODED_RESULTS
  const summary = HARDCODED_SUMMARY
  const samples = HARDCODED_SAMPLES

  useEffect(() => {
    const loadData = async () => {
      try {
        // 只加载曲线数据 - 使用新路径
        const curvesRes = await fetch('/case-studies/mdm/case5/curves.json')
        if (!curvesRes.ok) throw new Error('曲线数据加载失败')
        const curvesResJson = await curvesRes.json()
        // 对每个样本的梯度曲线进行裁剪，过滤超出[0, 0.6]范围的点
        const clippedSamples = curvesResJson.samples.map((sample: SampleCurve) => ({
          ...sample,
          grad_gamma_curve: sample.grad_gamma_curve
            .map((p: GradientPoint) => ({ ...p, gradient: Math.max(0, Math.min(0.6, p.gradient)) }))
            .filter((p: GradientPoint) => p.gradient >= 0 && p.gradient <= 0.6)
        }))
        setCurvesData(clippedSamples)
      } catch (err) {
        console.error('Failed to load case 5 curves:', err)
        // 如果加载失败，使用空数组，不影响其他数据显示
        setCurvesData([])
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  // 曲线颜色
  const curveColors = [
    '#ef4444', '#10b981', '#3b82f6', '#f59e0b', '#8b5cf6',
    '#06b6d4', '#ec4899', '#84cc16', '#6366f1', '#14b8a6',
    '#f97316', '#065f46', '#2563eb', '#7c3aed', '#00b894',
    '#e63946', '#fb8500', '#4ea8de', '#6c5ce7', '#a29bfe',
    '#ff006e', '#008000', '#008080', '#800080', '#800000',
    '#808000', '#808000', '#ff8040', '#ff80ff', '#80ffff'
  ]

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mb-4"></div>
          <p className="text-slate-600 font-bold">加载案例5数据中...</p>
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12">
        <p className="text-center text-slate-600">数据加载失败</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 案例选择下拉框 */}
      {onCaseChange && (
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-4">
            <BookOpen className="text-purple-600" size={20} />
            <label className="text-sm font-bold text-slate-600 whitespace-nowrap">切换案例：</label>
            <div className="relative flex-1 max-w-md">
              <select
                value={caseId}
                onChange={(e) => onCaseChange(e.target.value)}
                className="w-full appearance-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent cursor-pointer hover:bg-slate-100 transition-colors"
              >
                <option value="case-1">案例1: 多维度参数影响研究</option>
                <option value="case-2">案例2: 样本量与偏移量影响</option>
                <option value="case-3">案例3: 无交点梯度曲线研究 ★</option>
                <option value="case-4">案例4: 大样本性能验证</option>
                <option value="case-5">案例5: 30组实际样本分析 ★</option>
                <option value="case-6">案例6: 搜索步长对结果的影响 (c2数据)</option>
                <option value="case-7">案例7: 搜索步长对结果的影响 (实际样本) ★</option>
                <option value="case-8">案例8: β搜索方式对比 (β步长0.05) ★</option>
                <option value="case-9">案例9: β步长对估计结果的影响 ★</option>
                <option value="case-10">案例10: 中位秩方法对比研究 ★</option>
                <option value="case-11">案例11: 中位秩方法对比 (多样本量) ★</option>
                <option value="case-12">案例12: MDM vs WMLE 方法对比 ★</option>
                <option value="case-13">案例13: 中位秩方法对比 (多尺度参数) ★</option>
                <option value="case-14">案例14: MDM vs WMLE 方法对比 (多尺度参数) ★</option>
                <option value="case-15">案例15: MDM vs WMLE 方法对比 (精细步长) ★</option>
                <option value="case-16">案例16: MDM vs WMLE 方法对比 (精细步长+多尺度) ★</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={18} />
            </div>
          </div>
        </div>
      )}

      {/* 案例标题与说明 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h2 className="text-xl font-bold text-slate-800 mb-3">
          案例5: 30组实际样本的MDM估计分析
        </h2>
        <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
          <p className="text-sm text-blue-800 mb-2">
            <span className="font-bold">数据来源:</span> 30组真实失效数据，每组7个观测值，来自威布尔分布
          </p>
          <p className="text-sm text-blue-800">
            <span className="font-bold">真实参数:</span> β={summary.true_params.beta}, η={summary.true_params.eta}, γ={summary.true_params.gamma}
            <span className="ml-4 font-bold">样本量:</span> n=7
            <span className="ml-4 font-bold">偏移量:</span> δ={OFFSET_VALUE}
          </p>
        </div>
      </div>

      {/* 统计汇总表 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Table2 className="text-purple-600" size={20} />
          统计汇总表
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-lg border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-400">
                <th className="text-left py-3 px-4 font-bold text-slate-800">参数</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800">真实值</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800">估计均值</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800">估计范围</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800">偏差均值</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800">偏差范围</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800">偏差标准差</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-200">
                <td className="py-3 px-4 font-bold text-slate-800">β</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.true_params.beta.toFixed(1)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.estimates.beta_mean.toFixed(3)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">
                  [{summary.estimates.beta_min.toFixed(2)}, {summary.estimates.beta_max.toFixed(2)}]
                </td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.bias.beta_mean.toFixed(3)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">
                  [{summary.bias.beta_min.toFixed(2)}, {summary.bias.beta_max.toFixed(2)}]
                </td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.bias.beta_std.toFixed(3)}</td>
              </tr>
              <tr className="border-b border-slate-200 bg-slate-50">
                <td className="py-3 px-4 font-bold text-slate-800">η</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.true_params.eta.toFixed(0)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.estimates.eta_mean.toFixed(1)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">
                  [{summary.estimates.eta_min.toFixed(1)}, {summary.estimates.eta_max.toFixed(1)}]
                </td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.bias.eta_mean.toFixed(1)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">
                  [{summary.bias.eta_min.toFixed(1)}, {summary.bias.eta_max.toFixed(1)}]
                </td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.bias.eta_std.toFixed(1)}</td>
              </tr>
              <tr className="border-b border-slate-200">
                <td className="py-3 px-4 font-bold text-slate-800">γ</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.true_params.gamma.toFixed(0)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.estimates.gamma_mean.toFixed(1)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">
                  [{summary.estimates.gamma_min.toFixed(1)}, {summary.estimates.gamma_max.toFixed(1)}]
                </td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.bias.gamma_mean.toFixed(1)}</td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">
                  [{summary.bias.gamma_min.toFixed(1)}, {summary.bias.gamma_max.toFixed(1)}]
                </td>
                <td className="text-center py-3 px-4 font-mono text-slate-700">{summary.bias.gamma_std.toFixed(1)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 详细估计结果表 */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Table className="text-purple-600" size={20} />
          表1: 样本原始数据与估计结果
          <span className="text-sm font-normal text-slate-500">（共{results.length}条记录，{samples.length}个样本）</span>
        </h3>
        {samples.length === 0 && (
          <div className="text-red-600 mb-4">警告: 样本数据未加载</div>
        )}
        <div className="overflow-x-auto overflow-y-auto max-h-[900px]">
          <table className="w-full text-base border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-400 bg-slate-50 sticky top-0">
                <th className="text-center py-3 px-4 font-bold text-slate-800 border border-slate-300">样本编号</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800 border border-slate-300">t₁</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800 border border-slate-300">t₂</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800 border border-slate-300">t₃</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800 border border-slate-300">t₄</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800 border border-slate-300">t₅</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800 border border-slate-300">t₆</th>
                <th className="text-center py-3 px-4 font-bold text-slate-800 border border-slate-300">t₇</th>
                <th className="text-center py-3 px-4 font-bold text-blue-700 border border-slate-300">β̂</th>
                <th className="text-center py-3 px-4 font-bold text-blue-700 border border-slate-300">η̂</th>
                <th className="text-center py-3 px-4 font-bold text-blue-700 border border-slate-300">γ̂</th>
                <th className="text-center py-3 px-4 font-bold text-red-700 border border-slate-300">偏差(β)</th>
                <th className="text-center py-3 px-4 font-bold text-red-700 border border-slate-300">偏差(η)</th>
                <th className="text-center py-3 px-4 font-bold text-red-700 border border-slate-300">偏差(γ)</th>
              </tr>
            </thead>
            <tbody>
              {results.filter(r => r && r.sample_id && r.bias_gamma !== undefined).map((r, idx) => {
                const sample = samples.find(s => s.id === r.sample_id)
                return (
                  <tr key={r.sample_id} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                    <td className="text-center py-2 px-4 font-mono text-slate-700 border border-slate-200">{r.sample_id}</td>
                    {sample ? sample.values.map((val, i) => (
                      <td key={i} className="text-center py-2 px-4 font-mono text-slate-600 border border-slate-200">
                        {val.toFixed(1)}
                      </td>
                    )) : (
                      <>
                        <td className="text-center py-2 px-4 border border-slate-200 text-red-500">—</td>
                        <td className="text-center py-2 px-4 border border-slate-200 text-red-500">—</td>
                        <td className="text-center py-2 px-4 border border-slate-200 text-red-500">—</td>
                        <td className="text-center py-2 px-4 border border-slate-200 text-red-500">—</td>
                        <td className="text-center py-2 px-4 border border-slate-200 text-red-500">—</td>
                        <td className="text-center py-2 px-4 border border-slate-200 text-red-500">—</td>
                        <td className="text-center py-2 px-4 border border-slate-200 text-red-500">—</td>
                      </>
                    )}
                    <td className="text-center py-2 px-4 font-mono text-blue-700 border border-slate-200">{r.est_beta?.toFixed(3) ?? '—'}</td>
                    <td className="text-center py-2 px-4 font-mono text-blue-700 border border-slate-200">{r.est_eta?.toFixed(1) ?? '—'}</td>
                    <td className="text-center py-2 px-4 font-mono text-blue-700 border border-slate-200">{r.est_gamma?.toFixed(1) ?? '—'}</td>
                    <td className={`text-center py-2 px-4 font-mono border border-slate-200 ${
                      r.bias_beta > 0 ? 'text-red-600' : 'text-green-600'
                    }`}>{r.bias_beta > 0 ? '+' : ''}{r.bias_beta?.toFixed(3) ?? '—'}</td>
                    <td className={`text-center py-2 px-4 font-mono border border-slate-200 ${
                      r.bias_eta > 0 ? 'text-red-600' : 'text-green-600'
                    }`}>{r.bias_eta > 0 ? '+' : ''}{r.bias_eta?.toFixed(1) ?? '—'}</td>
                    <td className={`text-center py-2 px-4 font-mono border border-slate-200 ${
                      r.bias_gamma > 0 ? 'text-red-600' : 'text-green-600'
                    }`}>{r.bias_gamma > 0 ? '+' : ''}{r.bias_gamma?.toFixed(1) ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 图1: 梯度曲线簇 */}
      {curvesData.length > 0 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-lg font-bold text-slate-800">图1. 梯度曲线簇 - 位置参数梯度判据</h3>
              <p className="text-xs text-slate-500">30条样本的 ∇(γ) 与偏移值δ={OFFSET_VALUE} 比较</p>
            </div>
            <div className="w-3 h-3 bg-purple-500 rounded"></div>
          </div>
          <div className="w-full max-w-6xl" style={{ height: '600px' }}>
            <ResponsiveContainer width="100%">
              <LineChart margin={{ top: 20, right: 25, bottom: 40, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="gamma"
                  type="number"
                  domain={[200, 1800]}
                  tickFormatter={(v) => v.toFixed(0)}
                  tick={{ fontSize: 10 }}
                  tickLine={true}
                  stroke="#000"
                  strokeWidth={1}
                  label={{ value: '位置参数 γ', position: 'bottom', fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#000', strokeWidth: 1 }}
                />
                <YAxis
                  width={50}
                  domain={[0, 0.6]}
                  tick={{ fontSize: 10 }}
                  tickLine={true}
                  stroke="#000"
                  strokeWidth={1}
                  label={{ value: '梯度 ∇(γ)', angle: -90, position: 'insideLeft', fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#000', strokeWidth: 1 }}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  labelFormatter={(v) => `γ: ${Number(v).toFixed(0)}`}
                  formatter={(v: number, name: string) => [v.toFixed(4), name]}
                />
                <ReferenceLine y={OFFSET_VALUE} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'right', value: `δ=${OFFSET_VALUE}`, fill: '#10b981', fontSize: 10 }} />
                <ReferenceLine y={0} stroke="#cbd5e1" />
                {curvesData.slice(0, 30).map((sample, idx) => (
                  <Line
                    key={sample.sample_id}
                    data={sample.grad_gamma_curve}
                    type="monotone"
                    dataKey="gradient"
                    stroke={curveColors[idx % curveColors.length]}
                    strokeWidth={1.5}
                    dot={false}
                    name={sample.sample_id}
                    opacity={0.8}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      {curvesData.length === 0 && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm text-center text-slate-500">
          图表数据加载中...
        </div>
      )}

    </div>
  )
}
